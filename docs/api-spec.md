# API 规范

## Health

`GET /health`

## Parse

`POST /api/v1/parse`

请求：`multipart/form-data`

- `file`: DOCX 或 PDF
- `scenario`: 工程类型

## Review

`POST /api/v1/review`

```json
{
  "document_id": "doc_xxx",
  "scenario": "scaffold_landed",
  "summary": "方案结构化摘要"
}
```

## Knowledge Base

`POST /api/v1/kb/search`

## Expert

`GET /api/v1/expert/queue`

`POST /api/v1/expert/decision`

## Report

`POST /api/v1/report/export`
