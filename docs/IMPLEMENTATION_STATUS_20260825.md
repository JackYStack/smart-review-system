# SmartReview 整改实施与验收记录（2026-08-25）

## 已完成

- 技术处理状态、审查结论、结果完整性、人工复核状态分离；缺少配置或依赖失败不得显示完整审查通过。
- OnlyOffice 回调增加 JWT、任务、文档 key、编辑会话、版本及来源地址校验；专家编辑保存为新版本，已签发文件禁止覆盖。
- 建立项目、文档修订、审查轮次、独立问题、专家决策、审计事件与不可变文档制品模型。
- 完成专家任务领取、释放、逐项处置、退回整改、复核、批准与签发接口和界面。
- 建立确定性规则与公式引擎、单位归一、参数与证据留痕、Excel 预览/导入脚本。
- Dify 改为按方案类型绑定 Workflow Profile，支持多附件、现场图片、项目地区、审查重点、严格 JSON Schema、运行信息与配置快照。
- 增加任务幂等、优先级、取消、重试、租约和方案类型 readiness/发布门禁。
- 增加 `/health/live`、`/health/ready`、CI、浏览器 E2E、日志/资源限制、HTTPS/ClamAV 叠加配置、MySQL/MinIO 成套备份恢复脚本。

## 真实验收结果

- Alembic：`029 (head)`。
- 后端：容器内 `107 passed`，仅有一项第三方 TestClient 弃用提示。
- 前端：ESLint、TypeScript、生产构建通过；Microsoft Edge 实际运行演示 E2E `2 passed`。
- 默认栈：MySQL、MinIO、OnlyOffice、PaddleOCR、Backend、Worker、Frontend 均为 healthy。
- 健康接口：liveness 与 readiness 均返回 200，数据库和对象存储状态为 ok。
- 历史数据：补录 4 条不可变文档记录。
- 备份：`smartreview-backup-20260825-081646` 已生成，manifest、文件大小和 SHA-256 校验通过。
- 网络：`http://127.0.0.1/` 与 `http://100.73.167.2/` 均实测返回 200。

## 尚不能由代码自动补齐的生产资料

- 另外五类危大工程的正式模板、法规条款、规则阈值、计算公式及专家确认结果。
- 六类方案每类至少 20 份标注样本及业务专家验收记录。
- 正式域名、HTTPS 证书、Tailscale ACL/防火墙范围和异地备份介质。
- 正式环境需使用不同的 MySQL root/业务账号和 MinIO root/应用账号，并轮换聊天中出现过的凭据。
- 接收不可信文件的生产环境需启用 `docker-compose.security.yml`，并完成 ClamAV 病毒库、容量和告警验收。

系统当前定位仍为“AI 辅助审查”；只有专家完成签发后，才形成正式人工结论。
