from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.models.basis_item import BasisItem
from app.models.rule_engine import FormulaDefinition, RuleDefinition
from app.models.scheme_template import SchemeTemplate
from app.models.scheme_type import SchemeType
from app.schemas.template import FullDocumentReviewConfig, ReviewWorkflowData
from app.schemas.rule_engine import FormulaDefinitionCreate, validate_rule_configuration
from app.services.dify_settings import get_dify_url_and_key
from app.services.doc_tree_utils import iter_nodes
from app.services.integration_settings import (
    resolve_document_integration,
)
from app.services.llm.resolve import (
    effective_deepseek,
    effective_default_provider,
    effective_minimax,
    effective_volcengine,
)
from app.services.scheme_workflow_profile import resolve_scheme_workflow_profile

ReadinessStatus = Literal["ready", "incomplete", "unavailable"]
_SUBSTANTIVE_STEPS = {
    "compilation_basis",
    "context_consistency",
    "content",
    "full_document",
}


@dataclass(frozen=True)
class SchemeReadinessResult:
    status: ReadinessStatus
    issues: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.status == "ready"


def _non_empty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _llm_configuration_issue(db: Session) -> str | None:
    provider = effective_default_provider(db)
    if not provider:
        return "尚未配置默认大模型，无法执行智能审核步骤"
    if provider == "volcengine":
        values = effective_volcengine(db)
    elif provider == "deepseek":
        values = effective_deepseek(db)
    else:
        values = effective_minimax(db)
    if not all(str(value or "").strip() for value in values):
        return f"默认大模型 {provider} 的地址、密钥或模型标识配置不完整"
    return None


def assess_scheme_readiness(db: Session, scheme: SchemeType) -> SchemeReadinessResult:
    """Validate that a scheme can perform a substantive, reproducible review.

    ``incomplete`` means the scheme/template still needs business configuration.
    ``unavailable`` means a required runtime integration is not configured.
    The function deliberately performs no external network calls; transient service
    failures remain execution-time failures rather than changing publication state.
    """

    configuration_issues: list[str] = []
    availability_issues: list[str] = []
    template = scheme.template
    if template is None:
        template = (
            db.query(SchemeTemplate)
            .filter(SchemeTemplate.scheme_type_id == scheme.id)
            .first()
        )

    nodes: list[dict] = []
    if template is None:
        configuration_issues.append("尚未上传并解析Word方案模板")
    else:
        try:
            parsed = json.loads(template.parsed_structure or "")
        except (json.JSONDecodeError, TypeError):
            parsed = None
        raw_nodes = parsed.get("nodes") if isinstance(parsed, dict) else None
        if not isinstance(raw_nodes, list) or not raw_nodes:
            configuration_issues.append("模板解析结构为空或损坏")
        else:
            nodes = [item for item in iter_nodes(raw_nodes) if isinstance(item, dict)]
            ids = [str(item.get("id") or "").strip() for item in nodes]
            if any(not item for item in ids) or len(ids) != len(set(ids)):
                configuration_issues.append("模板节点ID存在空值或重复，无法稳定绑定审核配置")
            if any(not _non_empty(item.get("title")) for item in nodes):
                configuration_issues.append("模板存在无标题节点")

    workflow: ReviewWorkflowData | None = None
    if template is not None:
        try:
            workflow = ReviewWorkflowData.model_validate(
                json.loads(template.review_workflow or "")
            )
        except Exception:
            configuration_issues.append("审核工作流尚未配置或格式无效")
    active_steps = (
        [step for step in workflow.steps if step not in {"start", "end"}]
        if workflow is not None
        else []
    )
    substantive_steps = [step for step in active_steps if step in _SUBSTANTIVE_STEPS]
    if workflow is not None and not substantive_steps:
        configuration_issues.append("工作流至少需要一个编制依据、一致性、内容或通篇审核步骤")

    node_ids = {str(item.get("id") or "").strip() for item in nodes}
    uses_dataset = False
    if "compilation_basis" in active_steps:
        enabled = [item for item in nodes if bool(item.get("compilation_basis_audit_enabled"))]
        if not enabled:
            configuration_issues.append("编制依据审核已启用，但模板没有配置审核节点")
        basis_count = (
            db.query(BasisItem)
            .filter(
                (BasisItem.scheme_type_id == scheme.id)
                | (
                    (BasisItem.scheme_type_id.is_(None))
                    & (BasisItem.scheme_category == scheme.category)
                    & (BasisItem.scheme_name == scheme.name)
                ),
            )
            .count()
        )
        if basis_count < 1:
            configuration_issues.append("编制依据审核已启用，但该方案类型没有编制依据数据")

    if "context_consistency" in active_steps:
        configured_pairs = 0
        for item in nodes:
            refs = item.get("context_consistency_ref_node_ids")
            if not isinstance(refs, list) or not refs:
                continue
            configured_pairs += 1
            current_id = str(item.get("id") or "").strip()
            bad_refs = [
                str(ref).strip()
                for ref in refs
                if not str(ref).strip()
                or str(ref).strip() not in node_ids
                or str(ref).strip() == current_id
            ]
            if bad_refs:
                configuration_issues.append(
                    f"一致性审核节点 {current_id or '-'} 包含无效或自引用的对照节点"
                )
        if configured_pairs < 1:
            configuration_issues.append("上下文一致性审核已启用，但没有配置有效章节对照关系")

    if "content" in active_steps:
        content_nodes = [item for item in nodes if _non_empty(item.get("review_prompt"))]
        if not content_nodes:
            configuration_issues.append("内容审核已启用，但模板没有配置章节审核提示词")
        uses_dataset = uses_dataset or any(
            _non_empty(item.get("dify_dataset_id")) for item in content_nodes
        )

    if "full_document" in active_steps:
        full_config: FullDocumentReviewConfig | None = None
        try:
            raw_full = json.loads(template.full_document_review_config or "") if template else None
            if isinstance(raw_full, dict):
                full_config = FullDocumentReviewConfig.model_validate(raw_full)
        except Exception:
            full_config = None
        if full_config is None or not full_config.review_prompt.strip():
            configuration_issues.append("通篇审核已启用，但没有配置通篇审核提示词")
        elif (full_config.dify_dataset_id or "").strip():
            uses_dataset = True

    if substantive_steps:
        llm_issue = _llm_configuration_issue(db)
        if llm_issue:
            availability_issues.append(llm_issue)

    if uses_dataset and not all(get_dify_url_and_key(db)):
        availability_issues.append("模板引用了法规知识库，但Dataset API地址或密钥未配置")

    document = resolve_document_integration(db)
    if not document.paddleocr_api_url:
        availability_issues.append("PaddleOCR服务地址未配置")
    if not document.libreoffice_bin:
        availability_issues.append("LibreOffice不可用，Word无法转换为PDF")

    external_workflow = resolve_scheme_workflow_profile(db, scheme.id)
    if external_workflow.enabled and (
        not external_workflow.base_url
        or not external_workflow.api_key
        or not external_workflow.output_variable
    ):
        availability_issues.append("Dify Workflow已启用，但API地址、应用密钥或输出变量配置不完整")
    if external_workflow.enabled and external_workflow.output_format != "json":
        configuration_issues.append(
            "正式发布要求Dify Workflow统一输出JSON；auto/markdown仅可用于历史兼容与调试"
        )

    deterministic_rules = (
        db.query(RuleDefinition)
        .filter(
            RuleDefinition.scheme_type_id == scheme.id,
            RuleDefinition.enabled.is_(True),
        )
        .all()
    )
    if not deterministic_rules:
        configuration_issues.append("尚未配置带法规证据的确定性规则")
    else:
        for rule in deterministic_rules:
            if not (
                rule.source_standard_no.strip()
                and rule.source_clause.strip()
                and rule.source_text.strip()
            ):
                configuration_issues.append(f"规则 {rule.rule_code} 缺少规范编号、条款号或条款原文")
            try:
                raw_config = json.loads(rule.config_json or "{}")
                if not isinstance(raw_config, dict):
                    raise ValueError("规则配置不是JSON对象")
                validate_rule_configuration(rule.rule_type, raw_config)
            except Exception as exc:
                configuration_issues.append(f"规则 {rule.rule_code} 配置无效：{exc!s}")
        formula_rule_ids = [rule.id for rule in deterministic_rules if rule.rule_type == "formula"]
        if not formula_rule_ids:
            configuration_issues.append("尚未配置公式验算规则")
        else:
            formula_count = (
                db.query(FormulaDefinition)
                .filter(
                    FormulaDefinition.rule_id.in_(formula_rule_ids),
                    FormulaDefinition.enabled.is_(True),
                )
                .count()
            )
            if formula_count < 1:
                configuration_issues.append("公式规则没有已启用的公式定义")
            else:
                formulas = (
                    db.query(FormulaDefinition)
                    .filter(
                        FormulaDefinition.rule_id.in_(formula_rule_ids),
                        FormulaDefinition.enabled.is_(True),
                    )
                    .all()
                )
                for formula in formulas:
                    try:
                        variables = json.loads(formula.variables_json or "{}")
                        FormulaDefinitionCreate(
                            rule_id=formula.rule_id,
                            formula_code=formula.formula_code,
                            version=formula.version,
                            name=formula.name,
                            expression=formula.expression,
                            variables=variables,
                            result_unit=formula.result_unit,
                            comparator=formula.comparator,
                            threshold_value=formula.threshold_value,
                            threshold_parameter=formula.threshold_parameter,
                            enabled=formula.enabled,
                        )
                    except Exception as exc:
                        configuration_issues.append(
                            f"公式 {formula.formula_code} 配置无效：{exc!s}"
                        )

    issues = tuple(dict.fromkeys([*configuration_issues, *availability_issues]))
    if availability_issues:
        status: ReadinessStatus = "unavailable"
    elif configuration_issues:
        status = "incomplete"
    else:
        status = "ready"
    return SchemeReadinessResult(status=status, issues=issues)
