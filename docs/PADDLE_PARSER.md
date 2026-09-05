# PaddleOCR 文档解析配置

本项目整体架构、前端、数据库、异步 Worker、知识库、模型配置、OnlyOffice 与报告流程均沿用
SmartReview 设计；文档内容解析已替换为 PaddleOCR PP-StructureV3。

## 解析链路

1. 用户上传 DOCX；
2. 后端使用 LibreOffice 将 DOCX 渲染为 PDF；
3. PDF 以 Base64 发送到 PP-StructureV3 的 `POST /layout-parsing`；
4. PaddleOCR 返回包含标题、正文、表格和公式的 Markdown；
5. 后端将 Markdown 转换为 SmartReview 标题树；
6. 原始 DOCX 只用于把 Paddle 标题映射回 Word 段落位置，以便写入审查批注。

系统不会在 PaddleOCR 失败时回退到 `python-docx` 文本解析，避免展示环境与生产环境得到不同结果。

## PaddleOCR 服务

按照 PaddleOCR 官方 PP-StructureV3 服务化部署文档启动服务，默认端点：

```text
http://127.0.0.1:8080/layout-parsing
```

### 与主系统一起用 Docker 启动

仓库提供了 `docker-compose.paddle.yml`。安装 Docker Desktop 并准备好 `.env.docker` 后，在仓库根目录执行：

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.paddle.yml up -d --build
```

它会额外构建 `smartreview-paddleocr`，以官方 PaddlePaddle 3.0 镜像运行 PP-StructureV3。CPU 首次启动需要下载多个模型，通常比主系统启动慢很多；正式服务器可在 `.env.docker` 中将 `PADDLEOCR_DEVICE` 调整为匹配硬件的设备。

如果团队已经单独部署 PaddleOCR 服务，则只使用主 `docker-compose.yml`，并把 `PADDLEOCR_API_URL` 指向团队服务即可。

本地开发在 `backend/.env` 中配置：

```text
PADDLEOCR_API_URL=http://127.0.0.1:8080/layout-parsing
PADDLEOCR_API_KEY=
PADDLEOCR_TIMEOUT_SECONDS=600
PADDLE_CONVERT_TIMEOUT_SECONDS=180
LIBREOFFICE_BIN=C:\Program Files\LibreOffice\program\soffice.exe
```

Docker 部署默认从容器访问宿主机：

```text
PADDLEOCR_API_URL=http://host.docker.internal:8080/layout-parsing
```

后端镜像已经安装 LibreOffice Writer 与中文字体，无需另外安装 DOCX 转换依赖。

## 验收标准

- 模板上传后，`parsed_structure.parser.engine` 为 `PaddleOCR PP-StructureV3`；
- 审查日志中不再出现 Word 文本解析器；
- 表格和公式以 Paddle Markdown 内容进入章节审查上下文；
- Paddle 服务不可用时，任务明确失败并显示 PaddleOCR 错误，不生成伪解析结果。
