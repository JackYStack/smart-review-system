from app.models.scheme_review_task import CompletenessStatus, ReviewConclusion
from app.schemas.review_report import ReportIssue, ReportStep, ReviewReportV1
from app.services.review_pipeline import _classify_issue_evidence, _derive_task_outcome


def test_complete_report_without_business_issues_passes() -> None:
    report = ReviewReportV1(
        steps=[ReportStep(step_id="structure", passed=True, issues=[])]
    )
    conclusion, completeness = _derive_task_outcome(report)
    assert conclusion == ReviewConclusion.passed
    assert completeness == CompletenessStatus.complete


def test_business_issue_is_not_confused_with_technical_failure() -> None:
    report = ReviewReportV1(
        steps=[
            ReportStep(
                step_id="structure",
                passed=False,
                issues=[ReportIssue(message="缺少应急预案章节")],
            )
        ]
    )
    conclusion, completeness = _derive_task_outcome(report)
    assert conclusion == ReviewConclusion.issues_found
    assert completeness == CompletenessStatus.complete


def test_optional_integration_failure_marks_partial_not_business_issue() -> None:
    report = ReviewReportV1(
        steps=[
            ReportStep(
                step_id="dify_workflow",
                passed=False,
                issues=[
                    ReportIssue(
                        severity="warning",
                        message="Dify未完成",
                        related={
                            "technical_error": True,
                            "completeness_impact": "partial",
                        },
                    )
                ],
            )
        ]
    )
    conclusion, completeness = _derive_task_outcome(report)
    assert conclusion == ReviewConclusion.not_reviewed
    assert completeness == CompletenessStatus.partial


def test_required_llm_failure_marks_unavailable_but_keeps_confirmed_findings() -> None:
    report = ReviewReportV1(
        steps=[
            ReportStep(
                step_id="structure",
                passed=False,
                issues=[ReportIssue(message="缺少计算书")],
            ),
            ReportStep(
                step_id="content",
                passed=False,
                issues=[
                    ReportIssue(
                        message="模型调用失败",
                        related={
                            "technical_error": True,
                            "completeness_impact": "unavailable",
                        },
                    )
                ],
            ),
        ]
    )
    conclusion, completeness = _derive_task_outcome(report)
    assert conclusion == ReviewConclusion.issues_found
    assert completeness == CompletenessStatus.unavailable


def test_formula_finding_without_parameter_source_is_pending_human_judgement() -> None:
    issue = ReportIssue(
        severity="error",
        message="搭设高度超过阈值",
        evidence="JGJ 130-2011 第6.1.2条",
        related={
            "standard_no": "JGJ 130-2011",
            "clause_no": "6.1.2",
            "clause_text": "脚手架参数应符合设计要求",
            "inputs": {
                "height": {
                    "value": "24",
                    "unit": "m",
                    "source": {},
                    "extraction_method": "llm",
                    "verified": False,
                }
            },
        },
    )
    report = ReviewReportV1(
        steps=[ReportStep(step_id="rules_and_formulas", passed=False, issues=[issue])]
    )
    _classify_issue_evidence(report)
    assert issue.related["formal_violation"] is False
    assert issue.related["requires_human_judgement"] is True


def test_formula_finding_with_traceable_parameter_can_be_verified() -> None:
    issue = ReportIssue(
        severity="error",
        message="搭设高度超过阈值",
        evidence="JGJ 130-2011 第6.1.2条",
        related={
            "standard_no": "JGJ 130-2011",
            "clause_no": "6.1.2",
            "clause_text": "脚手架参数应符合设计要求",
            "inputs": {
                "height": {
                    "value": "24",
                    "unit": "m",
                    "source": {"page_no": 8, "quote": "搭设高度24m"},
                    "extraction_method": "table",
                    "verified": False,
                }
            },
        },
    )
    report = ReviewReportV1(
        steps=[ReportStep(step_id="rules_and_formulas", passed=False, issues=[issue])]
    )
    _classify_issue_evidence(report)
    assert issue.related["formal_violation"] is True
    assert issue.related["requires_human_judgement"] is False
