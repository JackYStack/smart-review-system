from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models.review_governance import DocumentRevision
from app.models.scheme_review_task import SchemeReviewTask
from app.models.scheme_type import SchemeType
from app.models.user import User
from app.schemas.scheme_type import (
    SchemeReadinessRead,
    SchemeLifecycleAction,
    SchemeTypeCreate,
    SchemeTypeRead,
    SchemeTypeUpdate,
)
from app.services.scheme_readiness import assess_scheme_readiness
from app.services.expert_review import append_audit_event
from app.services.template_versioning import latest_template_version, record_template_version

router = APIRouter(prefix="/scheme-types", tags=["scheme-types"])


def _scheme_public(db: Session, row: SchemeType) -> SchemeTypeRead:
    public = SchemeTypeRead.model_validate(row)
    readiness = assess_scheme_readiness(db, row)
    public.readiness_status = readiness.status
    public.readiness_issues = list(readiness.issues)
    return public


@router.get("", response_model=list[SchemeTypeRead])
def list_schemes(
    include_unpublished: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SchemeTypeRead]:
    query = db.query(SchemeType).options(joinedload(SchemeType.template))
    if user.role.value != "admin":
        query = query.filter(SchemeType.lifecycle_status == "published")
    rows = query.order_by(SchemeType.id).all()
    return [_scheme_public(db, row) for row in rows]


@router.post("", response_model=SchemeTypeRead, status_code=status.HTTP_201_CREATED)
def create_scheme(
    body: SchemeTypeCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> SchemeTypeRead:
    row = SchemeType(
        category=body.category,
        name=body.name,
        remark=body.remark,
        lifecycle_status="draft",
    )
    db.add(row)
    db.flush()
    append_audit_event(
        db,
        admin.id,
        "scheme_type",
        row.id,
        "created",
        {"category": row.category, "name": row.name},
    )
    db.commit()
    db.refresh(row)
    return _scheme_public(db, row)


@router.get("/{scheme_id}", response_model=SchemeTypeRead)
def get_scheme(
    scheme_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SchemeTypeRead:
    row = (
        db.query(SchemeType)
        .options(joinedload(SchemeType.template))
        .filter(SchemeType.id == scheme_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="方案类型不存在")
    return _scheme_public(db, row)


@router.get("/{scheme_id}/readiness", response_model=SchemeReadinessRead)
def get_scheme_readiness(
    scheme_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SchemeReadinessRead:
    row = (
        db.query(SchemeType)
        .options(joinedload(SchemeType.template))
        .filter(SchemeType.id == scheme_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="方案类型不存在")
    result = assess_scheme_readiness(db, row)
    return SchemeReadinessRead(
        scheme_type_id=row.id,
        readiness_status=result.status,
        readiness_issues=list(result.issues),
    )


@router.patch("/{scheme_id}", response_model=SchemeTypeRead)
def update_scheme(
    scheme_id: int,
    body: SchemeTypeUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> SchemeTypeRead:
    row = db.get(SchemeType, scheme_id)
    if row is None:
        raise HTTPException(status_code=404, detail="方案类型不存在")
    if body.category is not None:
        row.category = body.category
    if body.name is not None:
        row.name = body.name
    if body.remark is not None:
        row.remark = body.remark
    row.lifecycle_status = "draft"
    row.published_at = None
    row.published_by_id = None
    row.published_template_version_id = None
    append_audit_event(
        db,
        admin.id,
        "scheme_type",
        row.id,
        "updated_and_unpublished",
        body.model_dump(exclude_unset=True),
    )
    db.commit()
    db.refresh(row)
    return _scheme_public(db, row)


@router.post("/{scheme_id}/request-validation", response_model=SchemeTypeRead)
def request_scheme_validation(
    scheme_id: int,
    _: SchemeLifecycleAction,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> SchemeTypeRead:
    row = db.get(SchemeType, scheme_id)
    if row is None:
        raise HTTPException(status_code=404, detail="方案类型不存在")
    readiness = assess_scheme_readiness(db, row)
    row.lifecycle_status = "pending_validation"
    row.published_at = None
    row.published_by_id = None
    row.published_template_version_id = None
    append_audit_event(
        db,
        user.id,
        "scheme_type",
        row.id,
        "validation_requested",
        {"readiness_status": readiness.status, "issues": list(readiness.issues)},
    )
    db.commit()
    db.refresh(row)
    public = _scheme_public(db, row)
    public.readiness_issues = list(readiness.issues)
    return public


@router.post("/{scheme_id}/publish", response_model=SchemeTypeRead)
def publish_scheme(
    scheme_id: int,
    _: SchemeLifecycleAction,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> SchemeTypeRead:
    row = db.get(SchemeType, scheme_id)
    if row is None:
        raise HTTPException(status_code=404, detail="方案类型不存在")
    readiness = assess_scheme_readiness(db, row)
    if not readiness.ready:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "scheme_not_ready",
                "readiness_status": readiness.status,
                "readiness_issues": list(readiness.issues),
            },
        )
    row.lifecycle_status = "published"
    row.published_at = datetime.now(UTC)
    row.published_by_id = user.id
    template_version = latest_template_version(db, row.id)
    if template_version is None and row.template is not None:
        template_version = record_template_version(db, row.template, actor_id=user.id)
    if template_version is None:
        raise HTTPException(status_code=409, detail="缺少可发布的模板版本快照")
    row.published_template_version_id = template_version.id
    append_audit_event(
        db,
        user.id,
        "scheme_type",
        row.id,
        "published",
        {"template_version_id": template_version.id},
    )
    db.commit()
    db.refresh(row)
    return _scheme_public(db, row)


@router.post("/{scheme_id}/disable", response_model=SchemeTypeRead)
def disable_scheme(
    scheme_id: int,
    _: SchemeLifecycleAction,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> SchemeTypeRead:
    row = db.get(SchemeType, scheme_id)
    if row is None:
        raise HTTPException(status_code=404, detail="方案类型不存在")
    row.lifecycle_status = "disabled"
    row.published_at = None
    row.published_by_id = None
    row.published_template_version_id = None
    append_audit_event(db, user.id, "scheme_type", row.id, "disabled", {})
    db.commit()
    db.refresh(row)
    return _scheme_public(db, row)


@router.delete("/{scheme_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scheme(
    scheme_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> None:
    row = db.get(SchemeType, scheme_id)
    if row is None:
        raise HTTPException(status_code=404, detail="方案类型不存在")
    has_history = (
        db.query(SchemeReviewTask.id)
        .filter(SchemeReviewTask.scheme_type_id == scheme_id)
        .first()
        is not None
        or db.query(DocumentRevision.id)
        .filter(DocumentRevision.scheme_type_id == scheme_id)
        .first()
        is not None
    )
    if has_history:
        raise HTTPException(
            status_code=409,
            detail="该方案类型已有审核或项目版本历史，禁止硬删除；请改为停用",
        )
    append_audit_event(
        db,
        admin.id,
        "scheme_type",
        row.id,
        "deleted",
        {"category": row.category, "name": row.name},
    )
    db.delete(row)
    db.commit()
