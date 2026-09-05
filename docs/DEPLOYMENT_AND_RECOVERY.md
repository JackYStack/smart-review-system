# SmartReview 部署、健康检查与灾难恢复

本文说明本仓库已经具备的部署安全基线。正式上线仍需由部署人员提供域名、有效 HTTPS 证书、备份介质和防火墙策略。

## 1. 网络边界

默认 Compose 只把 `frontend` 的一个 HTTP 端口发布到宿主机。MySQL、MinIO、OnlyOffice、后端、Worker 和 PaddleOCR 仅在 Docker 网络中通信：

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.paddle.yml up -d --build
```

浏览器经同一个入口访问：

- 网站：`http://HOST_IP/`；
- API：`http://HOST_IP/api/`；
- OnlyOffice：`http://HOST_IP/office/`；
- MinIO 文件：由以 Bucket 名开头的签名地址经前端网关转发。

仅在本机维护时，可临时增加回环地址端口。它们不会被局域网或 Tailscale 上的其他电脑直接访问：

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.paddle.yml -f docker-compose.admin.yml up -d
```

不要在正式服务器上使用 `docker-compose.admin.yml`。MySQL 使用 `MYSQL_USER` 指定的业务账号；`MYSQL_ROOT_PASSWORD` 只用于初始化、备份和恢复。MinIO 同样使用 `MINIO_APP_ACCESS_KEY`/`MINIO_APP_SECRET_KEY` 指定的 Bucket 级账号，root 凭据只交给一次性初始化、备份与恢复流程。已有旧数据卷会分别由 `mysql-app-user` 和 `minio-app-user` 建立或更新应用账号。若日志出现“MinIO application account equals root”，说明仍在兼容旧配置，正式上线前必须改成两套不同凭据。

## 2. 健康检查

- `GET /api/health/live`：只检查 API 进程是否存活，不访问外部依赖，正常返回 200。
- `GET /api/health/ready`：检查 MySQL 与配置的 MinIO Bucket。全部可用返回 200；任一失败返回 503，并给出不含凭据的结构化依赖状态。

快速核查：

```powershell
Invoke-RestMethod http://127.0.0.1/api/health/live
Invoke-WebRequest http://127.0.0.1/api/health/ready -UseBasicParsing
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.paddle.yml ps
```

Compose 还为 MySQL、MinIO、OnlyOffice、API、前端、Worker 和 PaddleOCR 配置了健康探针、启动宽限期、日志轮转、CPU、内存与进程数上限。限制值均可通过 `.env.docker` 覆盖。

## 3. HTTPS 生产入口

1. 配置 `.env.docker` 中的 `PUBLIC_HOSTNAME=review.example.com`。
2. 把证书链放到 `deploy/certs/fullchain.pem`，私钥放到 `deploy/certs/privkey.pem`。
3. 确保域名的内外网 DNS 都能解析到该服务器，容器访问该域名时也应回到 HTTPS 网关。
4. 启动生产叠加配置：

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.paddle.yml -f docker-compose.production.yml up -d --build
```

该配置移除前端自身的宿主机端口，仅由 TLS 网关公开 80/443；80 会永久重定向至 443。防火墙应只允许所需来源访问 443，远程运维建议再叠加 Tailscale ACL。

正式接收不可信项目文件时，还应叠加恶意文件扫描配置：

```powershell
docker compose --env-file .env.docker `
  -f docker-compose.yml `
  -f docker-compose.paddle.yml `
  -f docker-compose.security.yml `
  -f docker-compose.production.yml up -d --build
```

该叠加配置启用私网 ClamAV，并把 API 设为“扫描失败即拒绝上传”。DOCX 还会独立执行 OOXML结构、解压尺寸、条目数量、路径和异常压缩比检查。ClamAV 的 3310 端口不会发布到宿主机；正式部署需为病毒库卷预留空间，并监控更新和内存占用。

## 4. MySQL 与 MinIO 成套备份

备份脚本在同一时间窗口导出数据库并镜像 MinIO Bucket，随后为每个文件写入大小和 SHA-256 到 `manifest.json`：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\backup-smartreview.ps1 -BackupRoot D:\SmartReviewBackups
```

脚本拒绝把磁盘根目录或用户主目录当作目标，也不会覆盖已有备份目录。为保持数据库记录与 MinIO 文档一致，默认会在导出期间短暂停顿 API 和 Worker，并在成功或失败后自动恢复；确实无法暂停业务时可显式传入 `-AllowOnlineWrites`，但这种在线备份只能视为尽力一致。备份包含原始方案和审核成果，必须放在受控介质，并额外复制一份到异机或离线存储。

恢复具有覆盖性，必须显式传入 `-ConfirmRestore`。脚本会先逐文件校验清单中的长度与 SHA-256；校验失败时不会开始恢复：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\restore-smartreview.ps1 `
  -BackupPath D:\SmartReviewBackups\smartreview-backup-20260824-220000 `
  -VerifyOnly

powershell -ExecutionPolicy Bypass -File .\scripts\restore-smartreview.ps1 `
  -BackupPath D:\SmartReviewBackups\smartreview-backup-20260824-220000 `
  -ConfirmRestore
```

正式恢复期间 API 与 Worker 会被短暂停顿，数据库和 Bucket 恢复后会执行迁移并重启 API、Worker 和前端。应选择维护窗口执行；`-VerifyOnly` 只校验文件，不中断服务。

恢复完成后必须执行：

```powershell
Invoke-WebRequest http://127.0.0.1/api/health/ready -UseBasicParsing
docker compose --env-file .env.docker exec backend alembic current
```

并人工抽查项目、方案原件、AI 批注版、专家版和签发报告。建议每月至少在全新空环境进行一次恢复演练，记录耗时、数据量、清单哈希和验收人。

从 027 或更早版本升级到 029 后，可执行一次历史文档索引补录。脚本会读取 MinIO 内容计算 SHA-256，不会改写原文件；无法读取的对象只记录 `SKIP`：

```powershell
docker compose --env-file .env.docker exec backend python scripts/backfill_document_artifacts.py
```

新任务会自动分别登记原始方案、AI批注版、每次专家编辑版和正式签发报告；已签发成果及其哈希不可覆盖。

仓库提供了不发布任何端口的恢复演练叠加配置。务必使用独立项目名，验收后只销毁该测试项目：

```powershell
docker compose -p smartreview-recovery-drill --env-file .env.docker `
  -f docker-compose.yml -f deploy/recovery-smoke.compose.yml up -d --no-build

powershell -ExecutionPolicy Bypass -File .\scripts\restore-smartreview.ps1 `
  -BackupPath D:\SmartReviewBackups\smartreview-backup-20260824-220000 `
  -ProjectName smartreview-recovery-drill -ConfirmRestore

docker compose -p smartreview-recovery-drill --env-file .env.docker `
  -f docker-compose.yml exec backend alembic current

docker compose -p smartreview-recovery-drill --env-file .env.docker `
  -f docker-compose.yml -f deploy/recovery-smoke.compose.yml down -v
```

## 5. CI 和上线门禁

`.github/workflows/ci.yml` 会执行：

- 前端依赖锁定安装、lint、TypeScript 与生产构建；
- 后端依赖安装、源码编译、真实 MySQL 上的 Alembic 升级和 pytest；
- 本地、回环维护和 HTTPS 三套 Compose 配置校验。

CI 通过只表示代码与迁移基线可部署。正式发布仍应执行真实 MinIO、PaddleOCR、OnlyOffice、Dify 的集成测试，以及备份恢复演练。
