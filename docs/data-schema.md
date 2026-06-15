# 数据 Schema

## IssueCard

```json
{
  "issue_id": "doc_001-missing-height",
  "title": "缺少脚手架搭设高度信息",
  "description": "用于判断是否触发危大工程阈值。",
  "source_module": "parameter",
  "severity": "B",
  "evidence_chain": {
    "scheme_text": "方案摘要",
    "page_number": 5,
    "clause_id": "MOHURD-37-001",
    "clause_text": "专项方案应按规定编制和审查。"
  },
  "confidence": 0.65,
  "needs_human_review": true
}
```

## Knowledge Chunk

```json
{
  "chunk_id": "MOHURD-37-001",
  "source": "住建部令第37号",
  "text": "条文正文",
  "metadata": {
    "scenario": "scaffold_landed",
    "version": "v0.1"
  }
}
```
