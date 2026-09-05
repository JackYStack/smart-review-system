# SmartReview 设置中心设计方案

状态：已确认；第一、二阶段核心功能已于 2026-08-24 完成部署验证。

## 目标

将业务管理员需要维护的外部服务与审核运行配置集中到设置中心，并提供配置来源、连接测试、状态诊断与明确的生效范围。业务运行配置采用“数据库覆盖、环境变量兜底”；数据库、JWT、Docker 端口等启动级配置保留在部署层，避免网页误操作导致系统失联。

## 信息架构

1. **服务状态**：Dify Workflow、Dify Dataset、大模型、PaddleOCR、LibreOffice、OnlyOffice、MinIO、MySQL、Worker 的配置与连接状态。
2. **AI 与知识库**：Dify Workflow、Dify Dataset、火山引擎、MiniMax、DeepSeek。
3. **文档处理**：PaddleOCR、LibreOffice、OnlyOffice，以及文档处理链路测试。
4. **审核运行**：审核超时、并发、Prompt 调试、Dify 失败策略与输出格式。
5. **系统与品牌**：名称、Logo、favicon、报告展示与看板刷新。
6. **部署与诊断**：MySQL、MinIO、容器与 Worker 的只读状态、版本和脱敏诊断信息。

## 配置分层

| 层级 | 示例 | 生效方式 |
| --- | --- | --- |
| 部署启动配置 | MySQL、JWT、Docker 端口、宿主机地址 | 环境文件修改后重启/重建 |
| 全局运行时配置 | Dify、模型、PaddleOCR、OnlyOffice、超时 | 保存后对新任务生效 |
| 方案类型配置 | Prompt、知识库 ID、规则、公式 | 对对应类型的新任务生效 |

页面展示每项配置的来源：`设置页覆盖`、`环境变量兜底`、`尚未配置`。

## Dify Workflow

- 启用开关、API 地址、Workflow 应用密钥、用户前缀和超时。
- 输出变量名（默认 `report`）与输出格式（JSON/Markdown）。
- 是否接受 `partial-succeeded`、Dify 失败时是否保留本地结果。
- 测试连接时显示应用名称、API 状态、耗时和错误。
- Workflow 应用密钥与 Dataset API 密钥必须明确分区，不可混用。

## 文档处理

- PaddleOCR：服务地址、API 密钥、解析超时和连接测试。
- LibreOffice：可用性、版本、转换超时；可执行路径属于部署配置。
- OnlyOffice：Document Server 地址、回调地址、JWT 和语言，增加连接测试。
- MinIO：首阶段只读展示连接状态、Bucket 和错误；基础设施凭据仍由部署环境管理。

## 安全与生效

- 设置接口仅管理员可用。
- 密钥不回显，仅显示“已配置”；空输入不修改，替换与清除分开操作。
- 日志与错误不得包含密钥。
- URL 需要协议与目标校验，同时允许明确授权的 Docker 内网与 Tailscale 地址。
- 配置保存后仅用于新任务；运行中任务保持其提交时的配置语义。
- 页面明确标注“立即生效”“仅对新任务生效”或“需要重启”。

## 实施顺序

### 第一阶段

1. Dify Workflow 设置 UI 与数据库运行时覆盖。
2. PaddleOCR/LibreOffice 设置 UI 与数据库运行时覆盖。
3. 统一服务状态与连接测试。
4. 配置来源、生效范围和错误提示。
5. JSON/Markdown 输出模式设置及解析契约提示。

### 第二阶段

1. 密钥加密。
2. 配置审计、版本与回滚。
3. MinIO 与部署诊断增强。
4. 脱敏诊断报告。

## 实施结果

- 已新增服务状态、Dify Workflow与文档处理设置界面。
- 已实现数据库运行时覆盖、配置来源与新任务生效提示。
- 已实现Dify JSON/Markdown自动解析和独立问题拆分。
- 已实现Dify、PaddleOCR、LibreOffice、OnlyOffice、MinIO连接测试。
- 已实现API密钥与OnlyOffice JWT的服务端加密，并兼容旧明文数据迁移。
- 已实现集成配置的操作人、变更字段、历史快照与回滚。
- 已实现Worker心跳和脱敏JSON诊断报告。
- MySQL、MinIO根凭据、JWT主密钥和Docker端口保持部署层管理。
