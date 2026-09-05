# Dify Workflow 全文审查对接

## 两种 Dify 密钥必须区分

- `DIFY_API_KEY`：Dataset API 密钥，用于列出知识库和检索规范片段；
- `DIFY_WORKFLOW_API_KEY`：`app-` 开头的应用密钥，用于上传方案并执行已发布 Workflow。

把 Workflow 应用密钥填入系统设置的“知识库密钥”会导致 `/datasets` 鉴权失败，因此本项目将两条链路完全分开。

## Workflow 调用过程

1. 后端将原始专项方案、辅助资料和现场图片逐一上传到 `POST /files/upload`；
2. 后端调用 `POST /workflows/run`，使用 streaming 模式等待长任务；
3. 标准输入为 `documents`、`site_images`、`project_name`、`project_region`、`risk_type`、`review_focus`；各方案类型可在设置页映射为对应 Web App 的真实变量名；
4. 读取 `succeeded` 或 `partial-succeeded` 完成事件中的 `outputs.report`；
5. 若 `report` 是约定 JSON，则转换为系统问题卡；
6. 若 `report` 仍是普通文本，则原文保留在“Dify Workflow 全文审查”步骤并标记为需人工确认；
7. Dify 不可用时，本地审查继续，但报告明确记录 Workflow 未完成，不会显示为全部通过。

`partial-succeeded` 表示 Dify 内部至少一个分支或节点异常，但结束节点仍可能生成有效 `report`。系统会保留该报告，同时增加“内部节点异常、需复核”的警告，而不是像旧客户端一样直接显示 `unknown` 并丢弃报告。

## 按方案类型配置（推荐）

管理员在“设置 → 方案类型 Workflow”中为每种方案绑定独立的 Base URL、`app-` 密钥、输出变量、JSON格式和输入映射。任务提交时系统会保存配置版本、加密配置快照、输入快照、Dify run ID 与 task ID；后续修改配置不会改变历史任务。

环境变量仍作为未建立类型专属配置时的兼容兜底：

```text
DIFY_WORKFLOW_ENABLED=true
DIFY_WORKFLOW_BASE_URL=http://DIFY主机/v1
DIFY_WORKFLOW_API_KEY=app-应用密钥
DIFY_WORKFLOW_USER_PREFIX=smart-review
DIFY_WORKFLOW_TIMEOUT_SECONDS=900
```

密钥只应写入被 Git 忽略的 `backend/.env` 或部署机的 `.env.docker`，不要写进前端代码。

## 推荐的 report JSON

为了让 Dify 问题直接进入筛选、报告和专家复核，最终输出变量 `report` 建议返回字符串化 JSON：

```json
{
  "passed": false,
  "summary": "发现 2 项问题",
  "issues": [
    {
      "severity": "error",
      "message": "问题说明",
      "evidence": "方案原文证据",
      "suggestions": ["明确、可执行的整改建议"],
      "anchor": {
        "title_path": ["六、施工安全保证措施", "6.2 连墙件设置"],
        "page_no": 18,
        "original_text": "方案中的原文摘录"
      },
      "related": {
        "standard_no": "JGJ 130-2011",
        "standard_name": "建筑施工扣件式钢管脚手架安全技术规范",
        "standard_version": "2011",
        "effect_status": "现行",
        "clause_no": "6.4.3",
        "clause_text": "检索命中的条款原文",
        "dataset_id": "法规库ID",
        "segment_id": "片段ID",
        "retrieval_score": 0.91
      }
    }
  ],
  "parameters": [
    {
      "parameter_name": "scaffold_height",
      "raw_value": "脚手架搭设高度24m",
      "numeric_value": 24,
      "unit": "m",
      "confidence": 0.96,
      "source": {
        "chapter_path": ["一、工程概况"],
        "page_no": 3,
        "original_text": "脚手架搭设高度24m"
      }
    }
  ]
}
```

在 Dify 的 LLM 提示词中只保留这一套 JSON 要求，并让结束节点把它作为 String 类型的 `report` 输出。网站会执行严格 Schema 校验；格式错误会作为技术失败/降级显示，不会把一整段文本伪装成结构化问题。

`parameters` 是可选字段。系统会把它保存为“LLM候选参数”，随后由确定性代码完成单位换算和公式计算；未经专家核验的参数即使触发阈值，也只会显示为疑似问题，不会直接判定正式违规。

每个问题只有同时具备方案原文定位、规范编号、条款号和条款原文时，才会标记为“证据链完整”。缺项自动降级为“疑似问题，待人工判断”。

## 联调命令

只检查网络、地址和密钥，不上传文件：

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\test_dify_workflow.py
```

网络可达后，可指定一份无敏感信息的测试方案执行完整上传与 Workflow：

```powershell
.\.venv\Scripts\python.exe scripts\test_dify_workflow.py --file "D:\测试方案.docx"
```
