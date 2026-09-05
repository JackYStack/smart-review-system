from __future__ import annotations

import json
import hashlib
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_current_user
from app.models.review_governance import (
    AuditEvent,
    DocumentRevision,
    ReviewIssue,
    ReviewRound,
)
from app.models.scheme_review_task import ReviewTaskStatus, SchemeReviewTask
from app.models.user import User, UserRole
from app.schemas.expert_review import (
    AuditEventPublic,
    IssueDecisionUpdate,
    ReviewIssuePublic,
    ReviewRoundAction,
    ReviewRoundDetail,
    ReviewRoundPublic,
    ReviewSourceDownload,
    SignedReportDownload,
)
from app.services import minio_storage
from app.services.expert_review import (
    REVIEW_MANAGER_ROLES,
    STAFF_ROLES,
    append_audit_event,
    assert_round_editor,
    build_signed_report,
    claim_round,
    ensure_round_for_task,
    record_decision,
    release_round,
    round_public,
    safe_json_dict,
    transition_round,
    update_issue_decision,
)
from app.services.review_settings import DEFAULT_SYSTEM_NAME, get_or_create_review_settings
from app.services.document_artifacts import record_document_artifact


router = APIRouter(prefix="/expert", tags=["expert-review"])


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


def _require_staff(user: User) -> None:
    if user.role not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="需要专家或复核管理权限")


def _round_query(db: Session):
    return db.query(ReviewRound).options(
        joinedload(ReviewRound.issues),
        joinedload(ReviewRound.decisions),
        joinedload(ReviewRound.assigned_expert),
        joinedload(ReviewRound.signed_by),
        joinedload(ReviewRound.document_revision).joinedload(DocumentRevision.project),
        joinedload(ReviewRound.task).joinedload(SchemeReviewTask.scheme_type),
        joinedload(ReviewRound.task).joinedload(SchemeReviewTask.user),
    )


def _load_round(db: Session, round_id: int, *, for_update: bool = False) -> ReviewRound:
    query = _round_query(db).filter(ReviewRound.id == round_id)
    if for_update:
        query = query.with_for_update()
    row = query.first()
    if row is None:
        raise HTTPException(status_code=404, detail="复核任务不存在")
    return row


def _sync_tasks(db: Session) -> int:
    tasks = (
        db.query(SchemeReviewTask)
        .options(joinedload(SchemeReviewTask.scheme_type), joinedload(SchemeReviewTask.user))
        .filter(
            SchemeReviewTask.status.in_(
                [
                    ReviewTaskStatus.pending,
                    ReviewTaskStatus.processing,
                    ReviewTaskStatus.succeeded,
                    ReviewTaskStatus.failed,
                    ReviewTaskStatus.canceled,
                ]
            )
        )
        .order_by(SchemeReviewTask.id)
        .all()
    )
    count = 0
    for task in tasks:
        before = db.query(ReviewRound.id).filter(ReviewRound.task_id == task.id).first()
        ensure_round_for_task(db, task)
        if before is None:
            count += 1
    db.commit()
    return count


@router.post("/review-rounds/sync")
def sync_review_rounds(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, int]:
    if user.role not in REVIEW_MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="需要复核管理员权限")
    return {"created": _sync_tasks(db)}


@router.get("/review-rounds", response_model=list[ReviewRoundPublic])
def list_review_rounds(
    round_status: str | None = Query(default=None, alias="status"),
    assigned_to_me: bool = False,
    available_only: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ReviewRoundPublic]:
    _require_staff(user)
    q = _round_query(db)
    if round_status:
        q = q.filter(ReviewRound.status == round_status)
    if assigned_to_me:
        q = q.filter(ReviewRound.assigned_expert_id == user.id)
    if available_only:
        q = q.filter(ReviewRound.status == "pending", ReviewRound.assigned_expert_id.is_(None))
    rows = q.order_by(ReviewRound.id.desc()).limit(limit).all()
    return [round_public(row) for row in rows]


@router.get("/review-rounds/{round_id}", response_model=ReviewRoundDetail)
def get_review_round(
    round_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReviewRoundDetail:
    _require_staff(user)
    row = _load_round(db, round_id, for_update=True)
    return round_public(row, detail=True)  # type: ignore[return-value]


@router.post("/review-rounds/{round_id}/claim", response_model=ReviewRoundDetail)
def claim_review_round(
    round_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReviewRoundDetail:
    row = _load_round(db, round_id, for_update=True)
    try:
        claim_round(db, row, user)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise _http_error(exc) from exc
    return round_public(_load_round(db, round_id), detail=True)  # type: ignore[return-value]


@router.post("/review-rounds/{round_id}/release", response_model=ReviewRoundDetail)
def release_review_round(
    round_id: int,
    body: ReviewRoundAction,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReviewRoundDetail:
    row = _load_round(db, round_id, for_update=True)
    try:
        release_round(db, row, user, body.comment)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise _http_error(exc) from exc
    return round_public(_load_round(db, round_id), detail=True)  # type: ignore[return-value]


@router.patch(
    "/review-rounds/{round_id}/issues/{issue_id}", response_model=ReviewIssuePublic
)
def decide_review_issue(
    round_id: int,
    issue_id: int,
    body: IssueDecisionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReviewIssuePublic:
    row = _load_round(db, round_id)
    issue = (
        db.query(ReviewIssue).with_for_update()
        .filter(ReviewIssue.id == issue_id, ReviewIssue.review_round_id == round_id)
        .first()
    )
    if issue is None:
        raise HTTPException(status_code=404, detail="问题不存在")
    try:
        update_issue_decision(
            db,
            row,
            issue,
            user,
            disposition=body.disposition,
            reviewer_comment=body.reviewer_comment,
            final_severity=body.final_severity,
        )
        db.commit()
        db.refresh(issue)
    except Exception as exc:
        db.rollback()
        raise _http_error(exc) from exc
    return ReviewIssuePublic(
        id=issue.id,
        review_round_id=issue.review_round_id,
        issue_key=issue.issue_key,
        source_issue_id=issue.source_issue_id,
        step_id=issue.step_id,
        severity=issue.severity,
        message=issue.message,
        evidence=issue.evidence,
        anchor=safe_json_dict(issue.anchor_json),
        related=safe_json_dict(issue.related_json),
        disposition=issue.disposition,
        reviewer_comment=issue.reviewer_comment,
        final_severity=issue.final_severity,
        reviewed_by_id=issue.reviewed_by_id,
        reviewed_at=issue.reviewed_at,
        created_at=issue.created_at,
        updated_at=issue.updated_at,
    )


@router.post("/review-rounds/{round_id}/request-changes", response_model=ReviewRoundDetail)
def request_changes(
    round_id: int,
    body: ReviewRoundAction,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReviewRoundDetail:
    row = _load_round(db, round_id, for_update=True)
    try:
        transition_round(
            db,
            row,
            user,
            action="request_changes",
            comment=body.comment,
            conclusion=body.conclusion,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise _http_error(exc) from exc
    return round_public(_load_round(db, round_id), detail=True)  # type: ignore[return-value]


@router.post("/review-rounds/{round_id}/approve", response_model=ReviewRoundDetail)
def approve_review_round(
    round_id: int,
    body: ReviewRoundAction,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReviewRoundDetail:
    row = _load_round(db, round_id, for_update=True)
    try:
        transition_round(
            db,
            row,
            user,
            action="approve",
            comment=body.comment,
            conclusion=body.conclusion,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise _http_error(exc) from exc
    return round_public(_load_round(db, round_id), detail=True)  # type: ignore[return-value]


@router.post("/review-rounds/{round_id}/sign", response_model=ReviewRoundDetail)
def sign_review_round(
    round_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReviewRoundDetail:
    if user.role not in REVIEW_MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="需要复核管理员权限")
    row = _load_round(db, round_id, for_update=True)
    if row.status != "approved":
        raise HTTPException(status_code=409, detail="仅已批准的复核任务可签发")
    if row.task.status != ReviewTaskStatus.succeeded or row.task.completeness_status == "unavailable":
        raise HTTPException(status_code=409, detail="AI审核结果不可用，禁止签发")
    if row.signed_report_object_key:
        raise HTTPException(status_code=409, detail="该任务已经签发，禁止覆盖")
    if not (row.task.review_result_json or "").strip():
        raise HTTPException(status_code=409, detail="缺少AI审核报告，无法签发")
    row.signed_by_id = user.id
    row.signed_by = user
    row.signed_at = datetime.now(UTC)
    settings = get_or_create_review_settings(db)
    system_name = (settings.system_name or "").strip() or DEFAULT_SYSTEM_NAME
    object_key: str | None = None
    try:
        content, digest = build_signed_report(row, system_name=system_name)
        object_key = f"signed-reports/{row.id}/{uuid.uuid4().hex}.docx"
        minio_storage.put_object(
            object_key,
            content,
            length=len(content),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        previous = row.status
        row.status = "signed"
        row.signed_report_object_key = object_key
        row.signed_report_sha256 = digest
        record_document_artifact(
            db,
            task_id=row.task_id,
            review_round_id=row.id,
            artifact_kind="signed_report",
            object_key=object_key,
            content=content,
            minio_bucket=row.task.minio_bucket,
            original_filename=f"任务{row.task_id}_正式签发报告.docx",
            created_by_id=user.id,
        )
        record_decision(db, row, user.id, "signed", previous, row.status, "")
        append_audit_event(
            db,
            user.id,
            "review_round",
            row.id,
            "signed",
            {"report_sha256": digest, "object_key": object_key},
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        if object_key:
            minio_storage.remove_object_if_exists(object_key)
        raise HTTPException(status_code=502, detail=f"签发报告生成失败: {exc!s}") from exc
    return round_public(_load_round(db, round_id), detail=True)  # type: ignore[return-value]


@router.get("/review-rounds/{round_id}/signed-report", response_model=SignedReportDownload)
def signed_report_download(
    round_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SignedReportDownload:
    _require_staff(user)
    row = _load_round(db, round_id)
    if not row.signed_report_object_key or not row.signed_report_sha256:
        raise HTTPException(status_code=404, detail="暂无已签发报告")
    return SignedReportDownload(
        url=minio_storage.presigned_get_url(
            row.signed_report_object_key,
            expires_seconds=3600,
            download_filename=f"任务{row.task_id}_正式签发报告.docx",
        ),
        sha256=row.signed_report_sha256,
    )


@router.get("/review-rounds/{round_id}/source-download", response_model=ReviewSourceDownload)
def source_document_download(
    round_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReviewSourceDownload:
    row = _load_round(db, round_id)
    if user.role not in REVIEW_MANAGER_ROLES and row.assigned_expert_id != user.id:
        raise HTTPException(status_code=403, detail="请先领取该复核任务")
    object_key = (row.task.object_key or "").strip()
    if not object_key:
        raise HTTPException(status_code=404, detail="原始方案不存在")
    if row.document_revision is not None:
        digest = row.document_revision.sha256
    else:
        digest = hashlib.sha256(minio_storage.get_object_bytes(object_key)).hexdigest()
    filename = (row.task.original_filename or "scheme.docx").strip() or "scheme.docx"
    return ReviewSourceDownload(
        url=minio_storage.presigned_get_url(
            object_key,
            expires_seconds=3600,
            download_filename=filename,
        ),
        sha256=digest,
        filename=filename,
    )


@router.get("/audit-events", response_model=list[AuditEventPublic])
def list_audit_events(
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AuditEventPublic]:
    if user.role not in REVIEW_MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="需要复核管理员权限")
    q = db.query(AuditEvent)
    if entity_type:
        q = q.filter(AuditEvent.entity_type == entity_type)
    if entity_id:
        q = q.filter(AuditEvent.entity_id == entity_id)
    rows = q.order_by(AuditEvent.id.desc()).limit(limit).all()
    return [
        AuditEventPublic(
            id=row.id,
            actor_id=row.actor_id,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            action=row.action,
            data=safe_json_dict(row.data_json),
            created_at=row.created_at,
        )
        for row in rows
    ]
