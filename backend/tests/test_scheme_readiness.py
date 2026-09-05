import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.models.scheme_template import SchemeTemplate
from app.models.scheme_type import SchemeType
from app.models.rule_engine import FormulaDefinition, RuleDefinition
from app.services.scheme_readiness import assess_scheme_readiness


def _scheme(*, steps: list[str], review_prompt: str = "逐项检查") -> SchemeType:
    scheme = SchemeType(id=1, category="脚手架工程", name="落地式钢管脚手架")
    scheme.template = SchemeTemplate(
        scheme_type_id=1,
        minio_bucket="review",
        object_key="templates/1/template.docx",
        original_filename="template.docx",
        parsed_structure=json.dumps(
            {
                "nodes": [
                    {
                        "id": "n1",
                        "level": 1,
                        "title": "一、工程概况",
                        "content": [],
                        "children": [],
                        "review_prompt": review_prompt,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        review_workflow=json.dumps({"steps": steps}),
    )
    return scheme


def _document_integration(*, ready: bool = True):
    return SimpleNamespace(
        paddleocr_api_url="http://paddle/layout-parsing" if ready else "",
        libreoffice_bin="/usr/bin/soffice" if ready else "",
    )


def _workflow_integration():
    return SimpleNamespace(
        enabled=False,
        base_url="",
        api_key="",
        output_variable="report",
    )


def _ready_rule_db() -> MagicMock:
    db = MagicMock()
    rule = SimpleNamespace(
        id=9,
        rule_code="SCAFFOLD-FORMULA-001",
        rule_type="formula",
        config_json="{}",
        source_standard_no="TEST-001",
        source_clause="1.0.1",
        source_text="测试规则条文，仅用于单元测试。",
    )

    def query(model):
        q = MagicMock()
        filtered = q.filter.return_value
        if model is RuleDefinition:
            filtered.all.return_value = [rule]
        elif model is FormulaDefinition:
            filtered.count.return_value = 1
            filtered.all.return_value = [
                SimpleNamespace(
                    rule_id=9,
                    formula_code="CAPACITY",
                    version=1,
                    name="承载力验算",
                    expression="load / area",
                    variables_json=json.dumps(
                        {
                            "load": {"parameter": "load", "unit": "N"},
                            "area": {"parameter": "area", "unit": "m2"},
                        }
                    ),
                    result_unit="Pa",
                    comparator="<=",
                    threshold_value=1000,
                    threshold_parameter=None,
                    enabled=True,
                )
            ]
        return q

    db.query.side_effect = query
    return db


@patch("app.services.scheme_readiness._llm_configuration_issue", return_value=None)
@patch("app.services.scheme_readiness.resolve_scheme_workflow_profile", side_effect=lambda *_args: _workflow_integration())
@patch("app.services.scheme_readiness.resolve_document_integration", side_effect=lambda _db: _document_integration())
def test_content_scheme_with_real_prompt_is_ready(*_mocks) -> None:
    result = assess_scheme_readiness(
        _ready_rule_db(),
        _scheme(steps=["start", "structure", "content", "end"]),
    )
    assert result.status == "ready"
    assert result.issues == ()


@patch("app.services.scheme_readiness._llm_configuration_issue", return_value=None)
@patch("app.services.scheme_readiness.resolve_scheme_workflow_profile", side_effect=lambda *_args: _workflow_integration())
@patch("app.services.scheme_readiness.resolve_document_integration", side_effect=lambda _db: _document_integration())
def test_structure_only_demo_workflow_is_incomplete(*_mocks) -> None:
    result = assess_scheme_readiness(
        MagicMock(),
        _scheme(steps=["start", "structure", "end"]),
    )
    assert result.status == "incomplete"
    assert any("至少需要一个" in item for item in result.issues)


@patch("app.services.scheme_readiness._llm_configuration_issue", return_value=None)
@patch("app.services.scheme_readiness.resolve_scheme_workflow_profile", side_effect=lambda *_args: _workflow_integration())
@patch("app.services.scheme_readiness.resolve_document_integration", side_effect=lambda _db: _document_integration())
def test_enabled_content_step_without_prompt_is_incomplete(*_mocks) -> None:
    result = assess_scheme_readiness(
        MagicMock(),
        _scheme(
            steps=["start", "structure", "content", "end"],
            review_prompt="",
        ),
    )
    assert result.status == "incomplete"
    assert any("审核提示词" in item for item in result.issues)


@patch("app.services.scheme_readiness._llm_configuration_issue", return_value=None)
@patch("app.services.scheme_readiness.resolve_scheme_workflow_profile", side_effect=lambda *_args: _workflow_integration())
@patch("app.services.scheme_readiness.resolve_document_integration", side_effect=lambda _db: _document_integration(ready=False))
def test_missing_document_runtime_is_unavailable(*_mocks) -> None:
    result = assess_scheme_readiness(
        MagicMock(),
        _scheme(steps=["start", "structure", "content", "end"]),
    )
    assert result.status == "unavailable"
    assert any("PaddleOCR" in item for item in result.issues)
    assert any("LibreOffice" in item for item in result.issues)
