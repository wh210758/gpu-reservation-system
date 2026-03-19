# 实验室 GPU/服务器算力预约与看板系统 - 需求与架构设计草案 (MVP)

## 1. 背景与目标

### 1.1 背景（受众痛点）

在高校或研究机构的实验室中，多人往往需要共用有限的 GPU 深度学习服务器。目前普遍缺乏透明的资源占用情况与排期机制。沟通成本极高，常通过微信群或口头询问“谁在用 XX 卡”，且极易发生抢占资源、误杀他人进程（Kill 错进程）或因显存溢出导致多方任务崩溃的冲突。

### 1.2 目标（核心价值）

开发一款轻量级、高透明度的【算力预约与监控看板系统】，实现：

- **资源透明化**：通过大屏或 Web 看板实时展示服务器 CPU、内存、GPU 占用及历史变动。
- **排班规范化**：提供可视化的日历/时间轴 UI，支持按需预约 GPU 资源，防冲突。
- **极简部署**：探针端要求极度轻量，不对原有服务器环境造成破坏或引入重度依赖。

### 1.3 非目标（Non-goals）

为保证 4 人学生团队在一个月内能顺利交付最小可用产品（MVP），本项目**明确不做**以下内容：

- **不涉及底层资源隔离**：不使用 Docker/Kubernetes 进行容器级显卡切分与硬隔离。
- **不干涉 OS 底层权限**：不自动强杀超时进程或接管 Linux User/Group 权限（依赖学生自觉遵守预约机制）。
- **不包含计费/财务模块**：仅记录使用时长和排班，不涉足算力计费与限额结算。
- **不包含复杂告警系统**：初期不接入邮件/短信/微信推送告警（可通过前端轮询实现简单通知）。

---

## 2. 核心架构与逻辑解耦设计

为满足不同编程能力成员的需求，且便于大模型生成代码，系统必须**高度解耦**。
推荐使用 **前端(Vue3/React) + 后端(FastAPI) + 数据库(SQLite) + 探针(纯Python)** 的轻量化技术栈。

### 2.1 分层架构设计

1. **Agent 探针端 (Python)**：
   - 部署在需要被监控的 GPU 服务器上。
   - 定时执行轻量级脚本，通过 `nvidia-smi` 和 `psutil` 收集系统信息。
   - 主动向 Backend 发送 HTTP POST 请求上报数据（Push 模式，避免后端穿透内网去拉取被动服务器）。
2. **Backend 后端 (Python FastAPI)**：
   - 负责处理预约逻辑、提供 RESTful API、处理 Agent 数据入库。
   - **AI 友好特性**：FastAPI 基于 Pydantic 自动生成 Swagger UI 文档，大模型可直接根据 OpenAPI 文档生成完美的前端调用代码，极大降低联调难度。
3. **Frontend 前端/看板端 (Vue3 或 React + TypeScript)**：
   - 纯静态 SPA（单页应用），负责渲染日历预约界面（如集成 FullCalendar）和状态监控看板（如集成 ECharts/Recharts）。

### 2.2 核心数据模型 (Schema) 建议

数据库初期建议使用内置的 **SQLite**，配置零门槛。

- `User` (用户表)：`id`, `username`, `role` (admin/student), `created_at`
- `Machine` (服务器表)：`id`, `hostname`, `ip_address`, `status`
- `GPU_Device` (显卡表)：`id`, `machine_id`, `gpu_index` (如 0, 1), `name` (如 RTX 3090)
- `Metric_Log` (监控日志表 - 可定期清理)：`id`, `gpu_id`, `utilization`, `memory_used`, `timestamp`
- `Reservation` (预约表)：`id`, `user_id`, `gpu_id`, `start_time`, `end_time`, `purpose`

### 2.3 通信协议建议

- **Agent -> Backend**：RESTful API (`POST /api/metrics`)。Agent 每 10 秒发起一次请求即可。
- **Frontend -> Backend**：RESTful API 提供 CRUD。监控看板的数据刷新采用 **HTTP 短轮询 (Short Polling)**（每 5-10 秒拉取一次最新状态），避免引入 WebSocket 增加前期的开发和调试负担。

---

## 3. 建议的项目结构（Git Repository目录树）

采用 **Monorepo（单体仓库）** 结构，方便 4 人团队共享一套代码库，同时向大模型提供全局上下文。

```text
gpu-reservation-system/
├── README.md               # 项目介绍与快速启动指南 (供组内对齐)
├── agent/                  # 探针端代码
│   ├── requirements.txt
│   ├── main.py             # 探针主轮询逻辑
│   └── hardware.py         # nvidia-smi 解析与系统状态抓取
├── backend/                # FastAPI 后端代码
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py         # 路由注册与入口
│   │   ├── models.py       # 数据库 ORM 模型
│   │   ├── schemas.py      # Pydantic 进出参数据校验模型
│   │   └── crud.py         # 数据库具体操作逻辑
│   └── gpu_db.sqlite       # 本地开发数据库
└── frontend/               # 前端看板与UI代码
    ├── package.json
    ├── src/
    │   ├── components/     # UI 组件 (Calendar日历, Chart图表)
    │   ├── views/          # 页面视图 (Dashboard, Reservation)
    │   └── api/            # Axios 接口封装层
```

---

## 4. 小组分工与 Git 协同策略（针对 4 人）

### 4.1 角色分配

- **A同学 (Frontend Dev - 前端工程师)**：负责 `frontend/` 目录。聚焦日历预约界面的交互实现、可视化图表（ECharts）的接入。
- **B同学 (Backend Dev - 后端工程师)**：负责 `backend/` 目录。使用 FastAPI 编写 RESTful 接口，设计 Pydantic 校验模型，对接前后端数据交互。
- **C同学 (Agent & DB Dev - 探针与数据工程师)**：负责 `agent/` 的轻量级脚本编写，以及设计后端数据库的关系模型，确保数据解析的健壮性。
- **D同学 (Scrum Master / PM / QA - 敏捷教练兼测试)**：负责全局统筹。撰写针对大模型的 Prompt 模板分发给组员，测试前后端接口联调，负责合并分支解决冲突，验收系统 DoD 标准。

### 4.2 Git 协同策略 (基于特性的 Feature Branch Workflow)

- **主分支 `main`**：永远保持可运行的稳定版本（只能由 `dev` 合并）。
- **开发分支 `dev`**：日常集成测试的分支。
- **特性分支 `feat/xxx`** 或 `fix/xxx`：组员开发功能（如 `feat/calendar-ui`）。
- **协作流**：成员在 `feat` 分支完成开发 $\rightarrow$ 发起 Pull Request 到 `dev` $\rightarrow$ D同学借助大模型进行 Code Review $\rightarrow$ 测试无误后合并入 `dev`。

---

## 5. 演进里程碑（Milestones）

针对一个月的时间盒（Timebox），拆解为 4 个紧凑的 Sprint（冲刺）：

- **Sprint 1 (第1周)：基础设施搭建与 Mock 数据联调**
  - *产出*：打通前后端骨架。后端提供返回假数据 (Mock) 的 API；前端能利用静态数据渲染出完整的日历 UI 和仪表盘框架。
- **Sprint 2 (第2周)：真实数据上报与监控看板流转**
  - *产出*：打通硬件数据流。Agent 探针能在服务器稳定运行并抓取状态上报；后端入库成功；前端图表能每 10 秒刷新并展示真实的显存/算力波动曲线。
- **Sprint 3 (第3周)：日历预约核心逻辑与防冲突打通**
  - *产出*：前端日历支持点击/拖拽选择时间段；后端实现硬核逻辑校验（同一张显卡不可时间重叠）；成功预约后多端同步展示“已占用”。
- **Sprint 4 (第4周)：系统健壮性测试、UI 适配与交付**
  - *产出*：完成异常测试（断网断联、越权篡改测试）；UI 适配（支持笔记本小屏查看）；完成大作业答辩 PPT 和演示视频的录制。

---

## 6. 详细验收标准（Definition of Done, DoD）（核心指标！）

> **请团队成员严格按照以下标准检验开发结果，也可直接将此标准喂给大模型以生成针对性强的单元测试。**

### 6.1 前端日历预约模块 (Frontend)

1. **多端分辨率响应式**：在 1920x1080 (PC大屏) 和 1280x720 (小屏笔记本) 分辨率下，日历组件均不得出现横向滚动条或文本重叠溢出。
2. **交互防呆机制**：点击“提交预约”请求后，必须弹出 Loading 遮罩层，防止用户在网络延迟时疯狂连击导致重复提交。成功/失败需弹出明确的 Toast 通知。
3. **视觉冲突隔离**：在日历视图中，已经被他人占用的时间块必须置灰且完全不可点击，确保用户无法在前端甚至发起重叠的排班请求。

### 6.2 后端 API 模块 (Backend)

1. **性能基线**：除了复杂的历史统计查询接口，其余常规 CRUD 接口响应时间必须 `< 200ms`。
2. **严苛的防冲突算法 (核心)**：`POST /api/reservations` 接口必须在数据库执行时间重叠校验（逻辑：`欲预约开始时间 < 已有结束时间 AND 欲预约结束时间 > 已有开始时间`）。若发现重叠，必须返回 HTTP 状态码 `409 Conflict`，并明确返回冲突对象的姓名。
3. **时序合理性校验**：API 必须阻挡 `start_time >= end_time` 的畸形请求，且拒绝预约“早于当前时间”的历史时间段（允许 5 分钟的客户端时钟容差）。

### 6.3 Agent 探针模块 (Agent)

1. **进程永生机制（断线重连）**：若服务器突然断网或后端 API 崩溃，探针代码必须捕获异常（try-except），记录本地错误日志，并在下一个 10 秒周期安静地重试，**绝对禁止因为网络波动导致 Python 进程闪退退出**。
2. **环境免疫机制**：如果宿主机没有安装显卡驱动（`nvidia-smi` 命令未找到），脚本不能崩溃，必须正常上报 CPU/内存 状态，并在 GPU 字段优雅地返回空列表 `[]`。
3. **轻量化保障**：Agent 进程自身长期运行占用的内存不得超过 50MB，CPU 占用率低于 1%。

---

## 7. 大模型辅助开发策略（AI-Assisted Dev Guide）

针对编程能力差异较大的团队，合理使用 Prompt 可以弥补代码硬实力。

### 7.1 如何让 AI 生成复杂的日历 UI 组件？

❌ **错误姿势**：“帮我写一个预约日历。”（AI 生成的代码你可能连依赖都跑不起来）。
✅ **正确姿势**：明确提供技术栈、数据结构与交互期望。

> **Prompt 示例**：“你是一个前端专家。请使用 Vue3 (`<script setup>` 语法)、TailwindCSS 和 FullCalendar 库，帮我写一个 `GPUCalendar.vue` 预约组件。
> 要求：
> 
> 1. 接收一个 prop `events`，数据结构为 `[{ id: 1, title: '张三占用', start: '2023-10-01T10:00:00', end: '2023-10-01T15:00:00' }]`。
> 2. 支持点击空白时间段触发 `@date-select` 事件，点击已有事件块触发 `@event-click` 事件。
> 3. 不要有残缺的伪代码，请直接给出可以直接粘贴运行的完整代码，并列出所需的 npm 安装命令。”

### 7.2 如何让 AI 写出健壮的 `nvidia-smi` 解析代码？

❌ **错误姿势**：让 AI 去写复杂的正则表达式解析原生的 `nvidia-smi` 纯文本表格，格式一旦变动立马报错。
✅ **正确姿势**：利用内置格式化参数。

> **Prompt 示例**：“你是一个 Python 运维开发工程师。请使用 `subprocess` 模块调用命令 `nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits`。
> 要求：
> 
> 1. 将逗号分隔的输出安全地解析为一个 Python 字典列表。
> 2. 加入完整的 `try-except` 异常捕获块，如果命令执行失败或超时（设为3秒超时），返回空列表，禁止抛出异常。
> 3. 给代码加上详细的中文注释，方便新手阅读。”

### 7.3 遇到 Bug 时，如何向 AI 提问调试？

永远不要只发一句“报错了怎么办”。请遵循 **[预期行为] + [实际表现] + [完整报错信息] + [相关代码片段]** 的提问公式。

> **Prompt 示例**：“后端 FastAPI 的预约接口报错了。
> 预期：检测到时间冲突返回 409。
> 实际：直接抛出了 HTTP 500 Internal Server Error。
> 终端完整报错堆栈如下：(粘贴完整的 Traceback...)
> 我的 `crud.py` 相关校验代码如下：(粘贴代码...)
> 请作为一名资深工程师，先一步步分析导致 500 的根本原因，然后给出针对性修复后的完整代码。”