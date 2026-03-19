from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import time
from datetime import datetime, timezone, timedelta
import sqlite3

import os
import requests

app = FastAPI(title="GPU Reservation System API")

# 从环境变量中读取探针在公网服务器暴露的 IP:Port，默认指向本地 8001 SSH隧道映射端口
REMOTE_AGENT_URL = os.getenv("REMOTE_AGENT_URL", "http://127.0.0.1:8001/metrics")
RESERVATIONS_DB = "gpu_db.sqlite"

# 初始化数据库建表
def init_db():
    with sqlite3.connect(RESERVATIONS_DB) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                gpu_id TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                purpose TEXT NOT NULL
            )
        ''')
        conn.commit()

init_db()

# 配置跨域，允许前端调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 内存数据库（仅作为 MVP 演示使用，真实环境推荐使用 SQLite/MySQL）
metrics_db = []

class GPUMetric(BaseModel):
    gpu_id: str
    gpu_name: str
    utilization: float
    memory_used: float
    memory_total: float
    timestamp: float

class Reservation(BaseModel):
    id: int
    user_id: str
    gpu_id: str
    start_time: str
    end_time: str
    purpose: str

class ReservationCreate(BaseModel):
    user_id: str
    gpu_id: str
    start_time: str
    end_time: str
    purpose: str

@app.post("/api/metrics")
async def report_metrics(metrics: List[GPUMetric]):
    global metrics_db
    # 存入数据，为支持 8 卡更长的历史，提升容量至 10000 条
    metrics_db.extend(metrics)
    if len(metrics_db) > 10000:
        metrics_db = metrics_db[-10000:]
    return {"status": "success", "recorded": len(metrics)}

@app.get("/api/metrics", response_model=List[GPUMetric])
async def get_metrics():
    global metrics_db
    
    # 【新增 Debug 日志】打印当前配置的探针地址
    print(f"[DEBUG] 当前配置的 REMOTE_AGENT_URL 为: '{REMOTE_AGENT_URL}'")
    
    # 如果配置了远程公网探针，则本地后端主动向服务器“拉取”数据
    if REMOTE_AGENT_URL:
        try:
            # 【新增 Debug 日志】打印拉取动作
            print(f"[DEBUG] 正在尝试向 {REMOTE_AGENT_URL} 发起拉取请求...")
            
            # 向公网服务器的探针发请求获取最新的 GPU 数据
            resp = requests.get(REMOTE_AGENT_URL, timeout=3.0)
            print(f"[DEBUG] 拉取请求 HTTP 状态码: {resp.status_code}")

            if resp.status_code == 200:
                payload = resp.json()
                
                # 兼容新型带 ACK 机制的 Agent 协议：{"last_id": 123, "data": [...]}
                if isinstance(payload, dict) and "data" in payload:
                    remote_data = payload["data"]
                    last_id = payload.get("last_id", 0)
                    
                    if remote_data:
                        metrics_db.extend(remote_data)
                        if len(metrics_db) > 10000:
                            metrics_db = metrics_db[-10000:]
                            
                        # 如果有有效数据被成功吞吐到本地，则向探针发送 ACK 指令，指挥其销毁这些数据
                        if last_id > 0:
                            ack_url = REMOTE_AGENT_URL + "/ack"  # 例如 http://127.0.0.1:8001/metrics/ack
                            try:
                                requests.post(ack_url, json={"last_id": last_id}, timeout=3.0)
                            except Exception as ack_err:
                                print(f"发送 ACK 销毁指令失败 (下一次拉取仍可重试): {ack_err}")
                
                # 兼容旧版本或 Mock 数组结构
                elif isinstance(payload, list) and len(payload) > 0:
                    metrics_db.extend(payload)
                    if len(metrics_db) > 10000:
                        metrics_db = metrics_db[-10000:]
                        
        except Exception as e:
            print(f"尝试拉取公网探针数据失败: {e}")

    # 如果没有任何数据，返回空列表
    if not metrics_db:
        return []
    return metrics_db

@app.get("/api/reservations", response_model=List[Reservation])
async def get_reservations():
    with sqlite3.connect(RESERVATIONS_DB) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM reservations')
        rows = cursor.fetchall()
    return [dict(row) for row in rows]

@app.post("/api/reservations", response_model=Reservation)
async def create_reservation(res: ReservationCreate):
    # 时序合理性校验
    try:
        # 兼容 ISO 格式的解析 (去掉时区和毫秒可能存在的部分)
        start_dt = datetime.fromisoformat(res.start_time.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(res.end_time.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=400, detail="时间格式不正确，需符合ISO格式")

    if start_dt >= end_dt:
        raise HTTPException(status_code=400, detail="预约开始时间必须早于结束时间")

    # 历史时间校验（早于当前时间5分钟）
    now_dt = datetime.now(start_dt.tzinfo if start_dt.tzinfo else timezone.utc)
    if start_dt < now_dt - timedelta(minutes=5):
        raise HTTPException(status_code=400, detail="不能预约早于当前时间（允许5分钟容差）")

    with sqlite3.connect(RESERVATIONS_DB) as conn:
        cursor = conn.cursor()
        
        # 核心逻辑校验：同一张显卡不可时间重叠
        # 逻辑：欲预约开始时间 < 已有结束时间 AND 欲预约结束时间 > 已有开始时间
        cursor.execute('''
            SELECT user_id, start_time, end_time FROM reservations 
            WHERE gpu_id = ? AND start_time < ? AND end_time > ?
        ''', (res.gpu_id, res.end_time, res.start_time))
        
        conflict = cursor.fetchone()
        if conflict:
            raise HTTPException(
                status_code=409, 
                detail=f"冲突！该卡的此时段已被 {conflict[0]} 占用 ({conflict[1]} 至 {conflict[2]})"
            )
            
        cursor.execute('''
            INSERT INTO reservations (user_id, gpu_id, start_time, end_time, purpose)
            VALUES (?, ?, ?, ?, ?)
        ''', (res.user_id, res.gpu_id, res.start_time, res.end_time, res.purpose))
        
        res_id = cursor.lastrowid
        conn.commit()
        
    return {
        "id": res_id,
        "user_id": res.user_id,
        "gpu_id": res.gpu_id,
        "start_time": res.start_time,
        "end_time": res.end_time,
        "purpose": res.purpose
    }

@app.delete("/api/reservations/{res_id}")
async def delete_reservation(res_id: int):
    with sqlite3.connect(RESERVATIONS_DB) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM reservations WHERE id = ?', (res_id,))
        conn.commit()
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    # 启动命令: python main.py 或者 uvicorn app.main:app --reload
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)