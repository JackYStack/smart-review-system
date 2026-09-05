from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.models.scheme_type import SchemeType
from app.models.user import User
from app.schemas.scheme_workflow_profile import (
    SchemeWorkflowProfilePublic,
    SchemeWorkflowProfileUpdate,
)
from app.services.scheme_workflow_profile import (
    get_scheme_workflow_profile,
    resolve_scheme_workflow_profile,
    upsert_scheme_workflow_profile,
    workflow_profile_public,
)
from app.services.expert_review import append_audit_event


router = APIRouter(prefix="/scheme-types", tags=["scheme-workflow-profiles"])


def _require_scheme(db: Session, scheme_type_id: int) -> SchemeType:
    row = db.get(SchemeType, scheme_type_id)
    if row is None:
        raise HTTPException(status_code=404, detail="方案类型不存在")
    return row


def _invalidate_publication(scheme: SchemeType) -> None:
    scheme.lifecycle_status = (
        "pending_validation" if scheme.lifecycle_status == "published" else "draft"
    )
    scheme.published_at = None
    scheme.published_by_id = None
    scheme.published_template_version_id = None


@router.get(
    "/{scheme_type_id}/dify-workflow-profile",
    response_model=SchemeWorkflowProfilePublic,
)
def get_workflow_profile(
    scheme_type_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> SchemeWorkflowProfilePublic:
    _require_scheme(db, scheme_type_id)
    config = resolve_scheme_workflow_profile(db, scheme_type_id)
    return workflow_profile_public(scheme_type_id, config)


@router.put(
    "/{scheme_type_id}/dify-workflow-profile",
    response_model=SchemeWorkflowProfilePublic,
)
def put_workflow_profile(
    scheme_type_id: int,
    body: SchemeWorkflowProfileUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> SchemeWorkflowProfilePublic:
    scheme = _require_scheme(db, scheme_type_id)
    try:
        upsert_scheme_workflow_profile(db, scheme_type_id, body)
        _invalidate_publication(scheme)
        append_audit_event(
            db,
            admin.id,
            "scheme_dify_workflow_profile",
            scheme_type_id,
            "updated",
            {
                "enabled": body.enabled,
                "base_url": body.base_url,
                "api_key_changed": bool((body.api_key or "").strip()),
                "api_key_cleared": body.clear_api_key,
                "timeout_seconds": body.timeout_seconds,
                "output_variable": body.output_variable,
                "output_format": body.output_format,
                "accept_partial": body.accept_partial,
                "continue_on_failure": body.continue_on_failure,
                "input_mapping": body.input_mapping,
            },
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    config = resolve_scheme_workflow_profile(db, scheme_type_id)
    return workflow_profile_public(scheme_type_id, config)


@router.delete(
    "/{scheme_type_id}/dify-workflow-profile",
    response_model=SchemeWorkflowProfilePublic,
)
def delete_workflow_profile(
    scheme_type_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> SchemeWorkflowProfilePublic:
    scheme = _require_scheme(db, scheme_type_id)
    row = get_scheme_workflow_profile(db, scheme_type_id)
    if row is not None:
        db.delete(row)
        _invalidate_publication(scheme)
        append_audit_event(
            db,
            admin.id,
            "scheme_dify_workflow_profile",
            scheme_type_id,
            "deleted",
            {},
        )
        db.commit()
    config = resolve_scheme_workflow_profile(db, scheme_type_id)
    return workflow_profile_public(scheme_type_id, config)
