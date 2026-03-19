# 实验室 GPU/服务器算力预约与看板系统

本仓库是我们 4 人小组“软件工程/大模型辅助开发”课程大作业的主干代码库。本项目旨在解决实验室算力资源使用不透明、排班沟通成本高以及容易引发多方抢占进程冲突的痛点。

本项目采用了极简且易于维护的 **前后端分离 + 轻量级探针** 架构：
- **前端**：采用 Vue3 / React 构建，提供直观的日历预约大屏与资源走势监控图。
- **后端**：采用 FastAPI 构建，提供 RESTful 接口与防重叠预约校验引擎，并对大模型极其友好。
- **探针端**：基于纯 Python 构建，零干扰定时采集 `nvidia-smi` 状态并上报。

---

## 项目文档索引目录

为了避免所有人都需要阅读厚重的长篇文档，我们对团队规范与指导手册进行了模块化拆分。请根据你的角色或需要解决的问题，点击查看对应的专栏文档：

1. **[《架构设计与大模型 Prompt 编写指南》](./GPU_Reservation_System_Design.md)**
   - **适用人员**：全体成员。
   - **内容简介**：定义了数据库表结构(Schema)、核心通信协议、系统需求范围(MVP)，并重点给出了如何指导 AI 编写 Vue 日历组件和 Python 探针的有效 Prompt 技巧。
2. **[《团队 Git 常用命令速查表》](./GIT_CHEATSHEET.md)**
   - **适用人员**：全体成员，尤其是对 Git 分支与撤销操作不熟悉的同学。
   - **内容简介**：日常高频拉取/提交命令、合并代码方法、发生代码覆盖时的“后悔药”指令等。
3. **[《QA 全链路验收与联调指南》](./QA_ACCEPTANCE_GUIDE.md)**
   - **适用人员**：项目负责人 (PM / 测试验收人员)。
   - **内容简介**：如何在自己电脑上同时跑通前、中、后三端，以及刁钻的致命测试用例（如帕金森连击、时间重叠测试、探针拔网线测试），并提供了最终答辩的演示剧本。

---

## 快速开发与环境配置指引 (保姆级)

请根据你负责的部分，直接跳转到对应的环境配置步骤：

### 1. 前端开发环境配置 (Frontend)
（负责目录：frontend/）

前置依赖：请确保你的电脑上安装了 Node.js (建议下载 v18 或 v20 的 LTS 版本)。

无障碍启动步骤：
1. 打开终端（VSCode 可以按 Ctrl + ` 打开终端）。
2. 进入前端目录：
   ```bash
   cd frontend
   ```
3. 使用 Vite 初始化前端骨架（如果你是首次启动且目录为空）：
   ```bash
   npm create vite@latest . -- --template vue-ts
   ```
4. 安装基础依赖包：
   ```bash
   npm install
   ```
5. 启动本地开发服务器：
   ```bash
   npm run dev
   ```
6. 终端会输出一个类似 http://localhost:5173 的本地地址，Ctrl + 鼠标左击打开即可。

---

### 2. 后端开发环境配置 (Backend)
（负责目录：backend/）

前置依赖：Python 3.9+。

无障碍启动步骤：
1. 进入后端目录：
   ```bash
   cd backend
   ```
2. 创建并激活虚拟环境（防止包冲突的核心步骤）：
   - Windows / PowerShell:
     ```bash
     python -m venv venv
     .\venv\Scripts\activate
     ```
   - Mac / Linux:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
   (激活成功后，你的命令行最前面会出现 (venv) 的标志)
3. 安装依赖包：
   ```bash
   pip install fastapi uvicorn pydantic sqlalchemy
   # 冻结依赖
   pip freeze > requirements.txt
   ```
4. 启动后端服务：
   ```bash
   # 进入 backend 目录执行
   uvicorn app.main:app --reload
   ```
   提示：打开浏览器访问 http://127.0.0.1:8000/docs 即可查看自动生成的 Swagger 接口文档。

---

### 3. 探针端环境配置 (Agent)
（负责目录：agent/）

前置依赖：Python 3.8+。

无障碍启动步骤：
1. 进入探针目录：
   ```bash
   cd agent
   ```
2. 创建并激活虚拟环境：
   - Windows: python -m venv venv 然后 .\venv\Scripts\activate
   - Mac/Linux: python3 -m venv venv 然后 source venv/bin/activate
3. 安装依赖：
   ```bash
   pip install requests psutil
   pip freeze > requirements.txt
   ```
4. 运行探针：
   ```bash
   python main.py
   ```

---

## Git 协作防坑五步曲

请永远基于 `dev` 分支创建你自己的新功能分支（如 `feat/xxx`），完成开发后再合并。严禁直接在 `main` 提交代码！

```bash
# 1. 更新主干
git checkout dev
git pull origin dev

# 2. 开辟个人战线
git checkout -b feat/your-feature-name

# 3. 编写代码...

# 4. 提交成果
git add .
git commit -m "feat(模块): 完成了xxx功能"

# 5. 推送并请项目负责人 Review
git push origin feat/your-feature-name
