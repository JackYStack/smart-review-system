# 危大工程专项施工方案智能审查系统

面向危大工程专项施工方案审查场景的智能辅助系统。项目采用“法规条款库 + 文档解析 + 规则引擎 + RAG 检索 + 大模型语义审查 + 公式验算 + 专家复核”的闭环架构，输出结构化审查建议、证据链和整改建议。

## 仓库结构

- `backend/`：FastAPI 后端、审查编排、解析、RAG、规则、公式和报告模块
- `frontend/`：React + Vite 审查工作台
- `data_pipeline/`：条款、参数、缺陷标签和知识库处理脚本
- `deploy/`：Docker Compose、Nginx、vLLM 和启动脚本
- `configs/`：工程类型、参数清单和严重性规则配置
- `docs/`：架构、API、数据 Schema 与会议纪要

## 快速启动

```powershell
cd Project\smart-review-system

# 后端
cd backend
pip install uv
uv sync
uv run uvicorn app.main:app --reload --port 8002

# 前端
cd ..\frontend
npm install
npm run dev
```

后端健康检查：`GET http://localhost:8002/health`

## 开发约定

- Python 使用 3.11+、Pydantic v2、FastAPI、SQLAlchemy 2.0。
- 提交信息遵循 Conventional Commits，例如 `feat(parse): 实现DOCX标题树抽取`。
- 功能分支从 `develop` 拉出，PR 合并回 `develop`。
- `main` 仅保留生产就绪版本。
- 每条审查结论必须包含方案证据、法规依据、严重性和复核状态。

## 当前状态

本仓库是项目初始代码框架，已包含 API 路由、核心数据模型、服务模块占位、前端工作台骨架、CI、部署配置与数据处理脚本。后续开发应优先补齐 DOCX/PDF 解析、规则包、RAG 入库和端到端审查链。
