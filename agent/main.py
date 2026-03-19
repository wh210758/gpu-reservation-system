import os
import subprocess
import time
import json
import threading
import sqlite3
import psutil
from http.server import BaseHTTPRequestHandler, HTTPServer

# 探针运行端口（公网服务器上需要放行此端口，或通过 SSH 端口转发）
PORT = 8001
POLL_INTERVAL = 10

# SQLite 缓冲库文件路径
DB_FILE = "buffer.db"
# 每条记录大概 150 字节。128MB / 150 字节 ≈ 85 万条记录。
# 为保证绝对不撑爆磁盘，设定硬上限为 50 万条（大约 75MB~100MB 极度安全）
MAX_ROWS = 500000

def init_db():
    """初始化 SQLite 数据库"""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gpu_id TEXT,
                gpu_name TEXT,
                utilization REAL,
                memory_used REAL,
                memory_total REAL,
                timestamp REAL
            )
        ''')
        # 创建索引加速删除和查询
        conn.execute('CREATE INDEX IF NOT EXISTS idx_id ON metrics(id)')
        conn.commit()

def save_to_db(metrics):
    """将采集到的数据安全存入本地 SQLite"""
    if not metrics:
        return
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            for m in metrics:
                cursor.execute('''
                    INSERT INTO metrics (gpu_id, gpu_name, utilization, memory_used, memory_total, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (m['gpu_id'], m['gpu_name'], m['utilization'], m['memory_used'], m['memory_total'], m['timestamp']))
            conn.commit()
            
            # 128MB 容量防爆锁：如果行数超限，只保留最新的，删除旧数据
            cursor.execute('SELECT COUNT(*) FROM metrics')
            count = cursor.fetchone()[0]
            if count > MAX_ROWS:
                delete_count = count - MAX_ROWS + 5000 # 多删 5000 条作为缓冲池
                cursor.execute(f'''
                    DELETE FROM metrics WHERE id IN (
                        SELECT id FROM metrics ORDER BY id ASC LIMIT ?
                    )
                ''', (delete_count,))
                conn.commit()
    except Exception as e:
        print(f"本地 SQLite 写入失败: {e}")

def get_metrics():
    """抓取系统及 GPU 信息"""
    metrics = []
    
    # 获取宿主机 CPU/内存 状态，作为特殊的 SYS 设备上报
    try:
        metrics.append({
            "gpu_id": "SYS",
            "gpu_name": "Host CPU & RAM",
            "utilization": psutil.cpu_percent(interval=None),
            "memory_used": round(psutil.virtual_memory().used / (1024 * 1024), 2),
            "memory_total": round(psutil.virtual_memory().total / (1024 * 1024), 2),
            "timestamp": time.time()
        })
    except Exception as e:
        print(f"抓取系统信息失败: {e}")
    
    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=index,name,utilization.gpu,memory.used,memory.total",
            "--format=csv,noheader,nounits"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 5:
                    metrics.append({
                        "gpu_id": parts[0],
                        "gpu_name": parts[1],
                        "utilization": float(parts[2]) if parts[2].isdigit() else 0.0,
                        "memory_used": float(parts[3]) if parts[3].isdigit() else 0.0,
                        "memory_total": float(parts[4]) if parts[4].isdigit() else 0.0,
                        "timestamp": time.time()
                    })
        else:
            print(f"执行 nvidia-smi 失败: {result.stderr}")
    except Exception as e:
        # 环境免疫：如果没装驱动，正常返回含 SYS 的列表，GPU 字段“优雅地”留空（只返回系统信息不崩溃）
        print(f"抓取 GPU 信息时发生错误 (可能未安装驱动): {e}")
        
    return metrics

def poll_hardware_loop():
    """后台线程：定时刷新硬件数据并落盘到 SQLite"""
    print(f"硬件监控线程已启动，数据将持续追加到 {DB_FILE} 缓冲池...")
    init_db()
    while True:
        try:
            metrics = get_metrics()
            save_to_db(metrics)
        except Exception as e:
            print(f"监控异常，已捕获: {e}")
        time.sleep(POLL_INTERVAL)

class MetricsHandler(BaseHTTPRequestHandler):
    """处理本地后端的拉取 (Pull) 和 确认清理 (ACK) 请求"""
    
    def do_GET(self):
        if self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            try:
                # 每次拉取最多提取 5000 条数据交予后端，避免 JSON 响应过大撑爆带宽
                with sqlite3.connect(DB_FILE) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute('SELECT * FROM metrics ORDER BY id ASC LIMIT 5000')
                    rows = cursor.fetchall()
                    
                data = [dict(row) for row in rows]
                last_id = data[-1]['id'] if data else 0
                
                # 包装一层协议，带上最高流水号 last_id，供后端 ACK 使用
                response_payload = {
                    "last_id": last_id,
                    "data": data
                }
                self.wfile.write(json.dumps(response_payload).encode('utf-8'))
            except Exception as e:
                print(f"查询缓冲数据失败: {e}")
                self.wfile.write(json.dumps({"last_id": 0, "data": []}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/metrics/ack':
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_response(400)
                self.end_headers()
                return
                
            post_data = self.rfile.read(content_length)
            try:
                payload = json.loads(post_data.decode('utf-8'))
                last_id = payload.get('last_id', 0)
                
                # 阅后即焚：删除 <= last_id 的所有已成功拉取的数据
                if last_id > 0:
                    with sqlite3.connect(DB_FILE) as conn:
                        cursor = conn.cursor()
                        cursor.execute('DELETE FROM metrics WHERE id <= ?', (last_id,))
                        conn.commit()
                        
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "deleted_up_to": last_id}).encode('utf-8'))
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                print(f"ACK 解析或清理失败: {e}")
        else:
            self.send_response(404)
            self.end_headers()
            
    # 屏蔽默认的日志输出，保持控制台清爽
    def log_message(self, format, *args):
        pass

def main():
    # 1. 启动硬件定时采集与 SQLite 物理落盘线程
    t = threading.Thread(target=poll_hardware_loop, daemon=True)
    t.start()
    
    # 2. 启动 HTTP 微型服务端接收拉取与清理命令
    server_address = ('0.0.0.0', PORT)
    httpd = HTTPServer(server_address, MetricsHandler)
    print("=" * 60)
    print(f"🚀 探针已启动 | 断网物理缓冲 128MB | 阅后即焚机制 (ACK)")
    print(f"📡 监听地址: 0.0.0.0:{PORT}")
    print(f"👉 提示: 请确保你使用了 `nohup python main.py >> ./agent.log 2>&1 &` 启动以避免写权限报错。")
    print("=" * 60)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nAgent 收到中断信号，停止运行")
        httpd.server_close()

if __name__ == "__main__":
    main()