import json

import httpx
import pytest

from app.services.dify_workflow_client import (
    DifyWorkflowClient,
    DifyWorkflowError,
    validate_dify_report,
)
from app.services.review_pipeline import dify_report_to_step


def test_workflow_uploads_file_and_reads_streaming_report() -> None:
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        assert request.headers["authorization"] == "Bearer test-app-key"
        if request.url.path == "/v1/files/upload":
            return httpx.Response(200, json={"id": "upload-1"})
        if request.url.path == "/v1/workflows/run":
            payload = json.loads(request.content)
            assert payload["inputs"]["documents"][0]["upload_file_id"] == "upload-1"
            assert payload["inputs"]["risk_type"] == "脚手架工程"
            event = {
                "event": "workflow_finished",
                "task_id": "task-1",
                "workflow_run_id": "run-1",
                "data": {
                    "status": "succeeded",
                    "outputs": {"report": "审查报告正文"},
                },
            }
            return httpx.Response(200, text=f"data: {json.dumps(event, ensure_ascii=False)}\n\n")
        return httpx.Response(404)

    client = DifyWorkflowClient(
        "http://dify.test/v1",
        "test-app-key",
        transport=httpx.MockTransport(handler),
    )
    result = client.run_review(
        file_name="脚手架方案.docx",
        file_content=b"docx",
        project_name="脚手架方案",
        project_region="",
        risk_type="脚手架工程",
        review_focus="检查缺陷",
        user="tester-1",
    )
    assert result.report == "审查报告正文"
    assert result.status == "succeeded"
    assert result.workflow_run_id == "run-1"
    assert seen_paths == ["/v1/files/upload", "/v1/workflows/run"]


def test_workflow_requires_report_output() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/files/upload"):
            return httpx.Response(200, json={"id": "upload-1"})
        event = {
            "event": "workflow_finished",
            "data": {"status": "succeeded", "outputs": {}},
        }
        return httpx.Response(200, text=f"data: {json.dumps(event)}\n\n")

    client = DifyWorkflowClient(
        "http://dify.test/v1",
        "test-app-key",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(DifyWorkflowError, match="required 'report' output"):
        client.run_review(
            file_name="方案.docx",
            file_content=b"docx",
            project_name="方案",
            project_region="",
            risk_type="危大工程",
            review_focus="",
            user="tester-1",
        )


def test_partial_success_keeps_available_report() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/files/upload"):
            return httpx.Response(200, json={"id": "upload-1"})
        event = {
            "event": "workflow_finished",
            "workflow_run_id": "run-partial",
            "data": {
                "status": "partial-succeeded",
                "outputs": {"report": "部分成功但已有报告"},
            },
        }
        return httpx.Response(200, text=f"data: {json.dumps(event, ensure_ascii=False)}\n\n")

    client = DifyWorkflowClient(
        "http://dify.test/v1",
        "test-app-key",
        transport=httpx.MockTransport(handler),
    )
    result = client.run_review(
        file_name="方案.docx",
        file_content=b"docx",
        project_name="方案",
        project_region="",
        risk_type="危大工程",
        review_focus="",
        user="tester-1",
    )
    assert result.status == "partial-succeeded"
    assert result.report == "部分成功但已有报告"


def test_custom_input_mapping_uses_profile_variable_names() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/files/upload"):
            return httpx.Response(200, json={"id": "upload-1"})
        payload = json.loads(request.content)
        assert set(payload["inputs"]) == {"scheme_files", "area", "focus"}
        assert payload["inputs"]["area"] == "南京市"
        assert payload["inputs"]["focus"] == "检查连墙件"
        event = {
            "event": "workflow_finished",
            "workflow_run_id": "run-mapped",
            "data": {"status": "succeeded", "outputs": {"report": "# 审查报告"}},
        }
        return httpx.Response(200, text=f"data: {json.dumps(event, ensure_ascii=False)}\n\n")

    client = DifyWorkflowClient(
        "http://dify.test/v1",
        "test-app-key",
        output_format="markdown",
        input_mapping={
            "documents": "scheme_files",
            "project_region": "area",
            "review_focus": "focus",
        },
        transport=httpx.MockTransport(handler),
    )
    result = client.run_review(
        file_name="方案.docx",
        file_content=b"docx",
        project_name="项目",
        project_region="南京市",
        risk_type="脚手架",
        review_focus="检查连墙件",
        user="tester-1",
    )
    assert result.workflow_run_id == "run-mapped"
    assert result.output_format == "markdown"


def test_multiple_documents_and_site_images_are_uploaded_and_mapped() -> None:
    uploaded = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal uploaded
        if request.url.path.endswith("/files/upload"):
            uploaded += 1
            return httpx.Response(200, json={"id": f"upload-{uploaded}"})
        payload = json.loads(request.content)
        assert [item["upload_file_id"] for item in payload["inputs"]["documents"]] == [
            "upload-1",
            "upload-2",
        ]
        assert payload["inputs"]["site_images"][0]["upload_file_id"] == "upload-3"
        event = {
            "event": "workflow_finished",
            "workflow_run_id": "run-multi",
            "data": {"status": "succeeded", "outputs": {"report": "# 完成"}},
        }
        return httpx.Response(200, text=f"data: {json.dumps(event)}\n\n")

    client = DifyWorkflowClient(
        "http://dify.test/v1",
        "test-app-key",
        output_format="markdown",
        input_mapping={"documents": "documents", "site_images": "site_images"},
        transport=httpx.MockTransport(handler),
    )
    result = client.run_review(
        file_name="主方案.docx",
        file_content=b"primary",
        document_files=[("主方案.docx", b"primary"), ("计算书.pdf", b"support")],
        site_image_files=[("现场.jpg", b"image")],
        project_name="项目",
        project_region="",
        risk_type="脚手架",
        review_focus="",
        user="tester-1",
    )
    assert uploaded == 3
    assert result.workflow_run_id == "run-multi"


def test_json_output_is_strictly_validated_and_normalized() -> None:
    report, detected = validate_dify_report(
        {
            "passed": False,
            "summary": "发现一项问题",
            "issues": [
                {
                    "severity": "error",
                    "message": "连墙件间距过大",
                    "evidence": "方案写明竖向三步",
                    "suggestions": ["按规范调整间距"],
                }
            ],
            "parameters": [
                {
                    "parameter_name": "scaffold_height",
                    "raw_value": "搭设高度24m",
                    "numeric_value": 24,
                    "unit": "m",
                    "confidence": 0.96,
                    "source": {
                        "chapter_path": ["工程概况"],
                        "page_no": 3,
                        "original_text": "本工程脚手架搭设高度24m",
                    },
                }
            ],
        },
        "json",
    )
    assert detected == "json"
    normalized = json.loads(report)
    assert normalized["issues"][0]["severity"] == "error"
    assert normalized["parameters"][0]["parameter_name"] == "scaffold_height"
    assert normalized["parameters"][0]["source"]["page_no"] == 3


def test_json_output_accepts_structured_evidence_from_published_workflow() -> None:
    report, detected = validate_dify_report(
        {
            "passed": False,
            "summary": "发现一项问题",
            "issues": [
                {
                    "severity": "error",
                    "message": "搭设高度前后不一致",
                    "evidence": {
                        "方案原文": "工程概况24m，施工工艺26m",
                        "法规依据": "应统一关键设计参数",
                    },
                    "suggestions": ["核实并统一搭设高度"],
                }
            ],
        },
        "json",
    )
    assert detected == "json"
    evidence = json.loads(report)["issues"][0]["evidence"]
    assert "方案原文：工程概况24m，施工工艺26m" in evidence
    assert "法规依据：应统一关键设计参数" in evidence


def test_json_output_missing_required_issue_evidence_is_rejected() -> None:
    with pytest.raises(DifyWorkflowError, match="schema validation failed"):
        validate_dify_report(
            json.dumps(
                {
                    "passed": False,
                    "summary": "存在问题",
                    "issues": [
                        {
                            "severity": "error",
                            "message": "缺少计算书",
                            "suggestions": ["补充计算书"],
                        }
                    ],
                }
            ),
            "json",
        )


def test_structured_dify_report_becomes_review_issues() -> None:
    step = dify_report_to_step(
        json.dumps(
            {
                "passed": False,
                "summary": "发现一项问题",
                "issues": [
                    {
                        "severity": "error",
                        "message": "连墙件设置间距过大",
                        "evidence": "竖向间距三步",
                        "suggestions": ["调整为规范允许间距"],
                    }
                ],
            },
            ensure_ascii=False,
        )
    )
    assert step.step_id == "dify_workflow"
    assert step.passed is False
    assert step.issues[0].message == "连墙件设置间距过大"
    assert step.issues[0].related["suggestions"] == ["调整为规范允许间距"]


def test_markdown_dify_report_is_split_into_individual_issues() -> None:
    step = dify_report_to_step(
        """# 审查报告

### 问题1：缺少计算书
- **风险等级**：高危
- **方案证据**：方案正文未检出计算书
- **审查依据**：GB 55023
- **整改建议**：补充计算书

### 问题2：搭设高度不一致
- **风险等级**：中危
- **方案证据**：工程概况24m，施工工艺26m
- **整改建议**：统一参数
""",
        output_format="markdown",
    )
    assert len(step.issues) == 2
    assert step.issues[0].message == "缺少计算书"
    assert step.issues[0].severity == "error"
    assert step.issues[1].message == "搭设高度不一致"


def test_text_dify_report_requires_manual_confirmation() -> None:
    step = dify_report_to_step("# 审查结论\n存在若干需要复核的问题")
    assert step.passed is False
    assert step.issues[0].severity == "info"
    assert "存在若干" in step.issues[0].evidence
