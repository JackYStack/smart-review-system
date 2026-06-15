# 贡献指南

## 分支

- `main`：生产就绪分支
- `develop`：开发主线
- `feat/*`：功能开发
- `fix/*`：缺陷修复
- `data/*`：数据更新
- `docs/*`：文档更新
- `release/v*`：里程碑发布

## 提交信息

格式：

```text
<type>(<scope>): <description>
```

常用类型：`feat`、`fix`、`data`、`docs`、`test`、`refactor`、`deploy`、`chore`。

常用范围：`parse`、`review`、`rag`、`llm`、`rules`、`formula`、`defect`、`report`、`expert`、`frontend`、`data`、`deploy`。

## PR 要求

- 描述本次变更和影响范围。
- 标注变更类型和模块标签。
- 后端变更需要通过 `ruff`、`mypy` 和 `pytest`。
- 数据变更需要附带变更摘要和校验结果。
- 涉及 A 类红线问题的逻辑必须有人工复核入口。

## 数据规则

- 大文件优先放入 `corpus-and-data` 仓库。
- 入库数据必须脱敏，敏感字段统一替换为 `[REDACTED]`。
- JSONL 提交前运行 `python data_pipeline/quality_validator.py --check`。
