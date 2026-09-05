from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models.rule_engine import (
    CalculationResult,
    EvidenceSource,
    FormulaDefinition,
    ParameterValue,
    RuleDefinition,
)
from app.models.scheme_review_task import SchemeReviewTask
from app.models.review_governance import ReviewIssue, ReviewRound
from app.models.scheme_type import SchemeType
from app.models.user import User, UserRole
from app.schemas.rule_engine import (
    CalculationResultPublic,
    EvidenceSourceCreate,
    EvidenceSourcePublic,
    FormulaDefinitionCreate,
    FormulaDefinitionPublic,
    ParameterValuePublic,
    ParameterValueUpsert,
    RuleDefinitionCreate,
    RuleDefinitionPublic,
    RuleDefinitionUpdate,
    RuleRunResponse,
    validate_rule_configuration,
)
from app.services.expert_review import STAFF_ROLES, append_audit_event
from app.services.rule_engine import execute_rules_for_task, normalize_value


router = APIRouter(tags=["rules-and-formulas"])


def _invalidate_scheme_publication(db: Session, scheme_type_id: int) -> None:
    scheme = db.get(SchemeType, scheme_type_id)
    if scheme is None:
        return
    if scheme.lifecycle_status == "published":
        scheme.lifecycle_status = "pending_validation"
    elif scheme.lifecycle_status != "disabled":
        scheme.lifecycle_status = "draft"
    scheme.published_at = None
    scheme.published_by_id = None
    scheme.published_template_version_id = None


def _json_dict(raw: str | None) -> dict:
    try:
        value = json.loads(raw or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _json_list(raw: str | None) -> list:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return value if isinstance(value, list) else []


def _rule_public(row: RuleDefinition) -> RuleDefinitionPublic:
    return RuleDefinitionPublic(
        id=row.id,
        scheme_type_id=row.scheme_type_id,
        rule_code=row.rule_code,
        version=row.version,
        name=row.name,
        rule_type=row.rule_type,
        severity=row.severity,
        enabled=row.enabled,
        config=_json_dict(row.config_json),
        source_standard_no=row.source_standard_no,
        source_standard_name=row.source_standard_name,
        source_version=row.source_version,
        source_clause=row.source_clause,
        source_text=row.source_text,
        created_by_id=row.created_by_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _formula_public(row: FormulaDefinition) -> FormulaDefinitionPublic:
    return FormulaDefinitionPublic(
        id=row.id,
        rule_id=row.rule_id,
        formula_code=row.formula_code,
        version=row.version,
        name=row.name,
        expression=row.expression,
        variables=_json_dict(row.variables_json),
        result_unit=row.result_unit,
        comparator=row.comparator,
        threshold_value=row.threshold_value,
        threshold_parameter=row.threshold_parameter,
        enabled=row.enabled,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _parameter_public(row: ParameterValue) -> ParameterValuePublic:
    return ParameterValuePublic(
        id=row.id,
        task_id=row.task_id,
        parameter_name=row.parameter_name,
        raw_value=row.raw_value,
        numeric_value=row.numeric_value,
        unit=row.unit,
        normalized_value=row.normalized_value,
        normalized_unit=row.normalized_unit,
        source=_json_dict(row.source_json),
        extraction_method=row.extraction_method,
        confidence=row.confidence,
        verified_by_id=row.verified_by_id,
        verified_at=row.verified_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _result_public(row: CalculationResult) -> CalculationResultPublic:
    return CalculationResultPublic(
        id=row.id,
        task_id=row.task_id,
        rule_id=row.rule_id,
        formula_id=row.formula_id,
        passed=row.passed,
        calculated_value=row.calculated_value,
        result_unit=row.result_unit,
        inputs=_json_dict(row.inputs_json),
        steps=_json_list(row.steps_json),
        expected=_json_dict(row.expected_json),
        message=row.message,
        error_message=row.error_message,
        created_at=row.created_at,
    )


def _task_for_user(db: Session, task_id: int, user: User) -> SchemeReviewTask:
    task = db.get(SchemeReviewTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.user_id != user.id and user.role not in (UserRole.admin, UserRole.review_admin):
        assigned = (
            user.role == UserRole.expert
            and db.query(ReviewRound.id)
            .filter(
                ReviewRound.task_id == task.id,
                ReviewRound.assigned_expert_id == user.id,
            )
            .first()
            is not None
        )
        if not assigned:
            raise HTTPException(status_code=403, detail="无权访问该任务")
    return task


@router.get("/rules", response_model=list[RuleDefinitionPublic])
def list_rules(
    scheme_type_id: int | None = None,
    enabled_only: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[RuleDefinitionPublic]:
    q = db.query(RuleDefinition)
    if scheme_type_id is not None:
        q = q.filter(RuleDefinition.scheme_type_id == scheme_type_id)
    if enabled_only:
        q = q.filter(RuleDefinition.enabled.is_(True))
    return [_rule_public(row) for row in q.order_by(RuleDefinition.id.desc()).limit(2000).all()]


@router.post("/rules", response_model=RuleDefinitionPublic, status_code=status.HTTP_201_CREATED)
def create_rule(
    body: RuleDefinitionCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> RuleDefinitionPublic:
    if db.get(SchemeType, body.scheme_type_id) is None:
        raise HTTPException(status_code=404, detail="方案类型不存在")
    row = RuleDefinition(
        scheme_type_id=body.scheme_type_id,
        rule_code=body.rule_code.strip(),
        version=body.version,
        name=body.name.strip(),
        rule_type=body.rule_type,
        severity=body.severity,
        enabled=body.enabled,
        config_json=json.dumps(body.config, ensure_ascii=False, separators=(",", ":")),
        source_standard_no=body.source_standard_no.strip(),
        source_standard_name=body.source_standard_name.strip(),
        source_version=body.source_version.strip(),
        source_clause=body.source_clause.strip(),
        source_text=body.source_text.strip(),
        created_by_id=admin.id,
    )
    db.add(row)
    try:
        db.flush()
        _invalidate_scheme_publication(db, body.scheme_type_id)
        append_audit_event(db, admin.id, "rule_definition", row.id, "created", body.model_dump(mode="json"))
        db.commit()
        db.refresh(row)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="相同方案类型、规则编号和版本已存在") from exc
    return _rule_public(row)


@router.patch("/rules/{rule_id}", response_model=RuleDefinitionPublic)
def update_rule(
    rule_id: int,
    body: RuleDefinitionUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> RuleDefinitionPublic:
    row = db.get(RuleDefinition, rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="规则不存在")
    changes = body.model_dump(exclude_unset=True)
    if "config" in changes:
        config = changes.pop("config")
        try:
            validate_rule_configuration(row.rule_type, config)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        row.config_json = json.dumps(config, ensure_ascii=False, separators=(",", ":"))
    for key, value in changes.items():
        setattr(row, key, value)
    _invalidate_scheme_publication(db, row.scheme_type_id)
    append_audit_event(db, admin.id, "rule_definition", row.id, "updated", body.model_dump(exclude_unset=True, mode="json"))
    db.commit()
    db.refresh(row)
    return _rule_public(row)


@router.get("/formulas", response_model=list[FormulaDefinitionPublic])
def list_formulas(
    rule_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[FormulaDefinitionPublic]:
    q = db.query(FormulaDefinition)
    if rule_id is not None:
        q = q.filter(FormulaDefinition.rule_id == rule_id)
    return [_formula_public(row) for row in q.order_by(FormulaDefinition.id.desc()).limit(2000).all()]


@router.post("/formulas", response_model=FormulaDefinitionPublic, status_code=status.HTTP_201_CREATED)
def create_formula(
    body: FormulaDefinitionCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> FormulaDefinitionPublic:
    rule = db.get(RuleDefinition, body.rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="规则不存在")
    row = FormulaDefinition(
        rule_id=body.rule_id,
        formula_code=body.formula_code.strip(),
        version=body.version,
        name=body.name.strip(),
        expression=body.expression.strip(),
        variables_json=json.dumps(body.variables, ensure_ascii=False, separators=(",", ":")),
        result_unit=body.result_unit.strip(),
        comparator=body.comparator,
        threshold_value=body.threshold_value,
        threshold_parameter=body.threshold_parameter,
        enabled=body.enabled,
    )
    db.add(row)
    try:
        db.flush()
        _invalidate_scheme_publication(db, rule.scheme_type_id)
        append_audit_event(db, admin.id, "formula_definition", row.id, "created", body.model_dump(mode="json"))
        db.commit()
        db.refresh(row)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="相同规则、公式编号和版本已存在") from exc
    return _formula_public(row)


@router.get("/review-tasks/{task_id}/parameters", response_model=list[ParameterValuePublic])
def list_task_parameters(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ParameterValuePublic]:
    _task_for_user(db, task_id, user)
    rows = db.query(ParameterValue).filter(ParameterValue.task_id == task_id).order_by(ParameterValue.id).all()
    return [_parameter_public(row) for row in rows]


@router.put("/review-tasks/{task_id}/parameters", response_model=list[ParameterValuePublic])
def upsert_task_parameters(
    task_id: int,
    body: list[ParameterValueUpsert],
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ParameterValuePublic]:
    _task_for_user(db, task_id, user)
    if len(body) > 500:
        raise HTTPException(status_code=400, detail="一次最多提交500个参数")
    if any(item.verified for item in body) and user.role not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="只有专家或管理员可以验证参数")
    now = datetime.now(UTC)
    for item in body:
        row = (
            db.query(ParameterValue)
            .filter(ParameterValue.task_id == task_id, ParameterValue.parameter_name == item.parameter_name)
            .first()
        )
        if row is None:
            row = ParameterValue(task_id=task_id, parameter_name=item.parameter_name)
            db.add(row)
        row.raw_value = item.raw_value
        row.numeric_value = item.numeric_value
        row.unit = item.unit
        row.source_json = json.dumps(item.source, ensure_ascii=False, separators=(",", ":"))
        row.extraction_method = item.extraction_method
        row.confidence = item.confidence
        if item.numeric_value is not None:
            try:
                row.normalized_value, row.normalized_unit = normalize_value(item.numeric_value, item.unit)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"参数{item.parameter_name}: {exc!s}") from exc
        else:
            row.normalized_value = None
            row.normalized_unit = ""
        if item.verified:
            row.verified_by_id = user.id
            row.verified_at = now
        else:
            # Any value change invalidates the previous verification.  Without
            # this reset, an owner could edit a verified number while the UI
            # continued to show the old expert's verification badge.
            row.verified_by_id = None
            row.verified_at = None
    append_audit_event(db, user.id, "review_task", task_id, "parameters_upserted", {"count": len(body)})
    db.commit()
    rows = db.query(ParameterValue).filter(ParameterValue.task_id == task_id).order_by(ParameterValue.id).all()
    return [_parameter_public(row) for row in rows]


@router.post("/review-tasks/{task_id}/rules/run", response_model=RuleRunResponse)
def run_task_rules(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RuleRunResponse:
    task = _task_for_user(db, task_id, user)
    results = execute_rules_for_task(db, task)
    append_audit_event(db, user.id, "review_task", task_id, "rules_executed", {"count": len(results)})
    db.commit()
    public = [_result_public(row) for row in results]
    return RuleRunResponse(
        task_id=task_id,
        total=len(public),
        passed=sum(1 for row in public if row.passed and not row.error_message),
        failed=sum(1 for row in public if not row.passed and not row.error_message),
        errors=sum(1 for row in public if row.error_message),
        results=public,
    )


@router.get("/review-tasks/{task_id}/rule-results", response_model=list[CalculationResultPublic])
def list_rule_results(
    task_id: int,
    latest_only: bool = True,
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CalculationResultPublic]:
    _task_for_user(db, task_id, user)
    rows = (
        db.query(CalculationResult)
        .filter(CalculationResult.task_id == task_id)
        .order_by(CalculationResult.id.desc())
        .limit(limit)
        .all()
    )
    if latest_only:
        seen: set[int] = set()
        rows = [row for row in rows if row.rule_id not in seen and not seen.add(row.rule_id)]
    return [_result_public(row) for row in rows]


@router.post(
    "/review-tasks/{task_id}/evidence",
    response_model=EvidenceSourcePublic,
    status_code=status.HTTP_201_CREATED,
)
def create_evidence_source(
    task_id: int,
    body: EvidenceSourceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EvidenceSourcePublic:
    _task_for_user(db, task_id, user)
    if user.role not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="需要专家或管理员权限")
    if body.review_issue_id is not None:
        issue = db.get(ReviewIssue, body.review_issue_id)
        if issue is None:
            raise HTTPException(status_code=404, detail="复核问题不存在")
        issue_task_id = (
            db.query(ReviewRound.task_id)
            .filter(ReviewRound.id == issue.review_round_id)
            .scalar()
        )
        if issue_task_id != task_id:
            raise HTTPException(status_code=400, detail="复核问题不属于当前审核任务")
    row = EvidenceSource(
        task_id=task_id,
        review_issue_id=body.review_issue_id,
        source_kind=body.source_kind,
        standard_no=body.standard_no,
        standard_name=body.standard_name,
        standard_version=body.standard_version,
        effect_status=body.effect_status,
        clause_no=body.clause_no,
        clause_text=body.clause_text,
        page_no=body.page_no,
        dataset_id=body.dataset_id,
        segment_id=body.segment_id,
        retrieval_score=body.retrieval_score,
        scheme_quote=body.scheme_quote,
        location_json=json.dumps(body.location, ensure_ascii=False, separators=(",", ":")),
    )
    db.add(row)
    db.flush()
    append_audit_event(db, user.id, "evidence_source", row.id, "created", body.model_dump(mode="json"))
    db.commit()
    db.refresh(row)
    return EvidenceSourcePublic(id=row.id, task_id=row.task_id, created_at=row.created_at, **body.model_dump())


@router.get("/review-tasks/{task_id}/evidence", response_model=list[EvidenceSourcePublic])
def list_evidence_sources(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[EvidenceSourcePublic]:
    _task_for_user(db, task_id, user)
    rows = db.query(EvidenceSource).filter(EvidenceSource.task_id == task_id).order_by(EvidenceSource.id).all()
    return [
        EvidenceSourcePublic(
            id=row.id,
            task_id=row.task_id,
            review_issue_id=row.review_issue_id,
            source_kind=row.source_kind,
            standard_no=row.standard_no,
            standard_name=row.standard_name,
            standard_version=row.standard_version,
            effect_status=row.effect_status,
            clause_no=row.clause_no,
            clause_text=row.clause_text,
            page_no=row.page_no,
            dataset_id=row.dataset_id,
            segment_id=row.segment_id,
            retrieval_score=row.retrieval_score,
            scheme_quote=row.scheme_quote,
            location=_json_dict(row.location_json),
            created_at=row.created_at,
        )
        for row in rows
    ]
