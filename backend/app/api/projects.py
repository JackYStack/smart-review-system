from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models.review_attachment import ReviewAttachment
from app.models.review_governance import DocumentRevision, Project, ReviewRound
from app.models.scheme_review_task import (
    CompletenessStatus,
    HumanReviewStatus,
    ReviewConclusion,
    ReviewTaskStatus,
    SchemeReviewTask,
)
from app.models.scheme_template import SchemeTemplate
from app.models.scheme_type import SchemeType
from app.models.user import User, UserRole
from app.schemas.expert_review import (
    DocumentRevisionPublic,
    ProjectCreate,
    ProjectPublic,
    ProjectUpdate,
    RevisionTaskCreateResponse,
)
from app.services import minio_storage
from app.services.attachment_validation import validate_supporting_attachment
from app.services.malware_scan import (
    MalwareDetectedError,
    MalwareScanError,
    scan_bytes as scan_upload_bytes,
)
from app.services.document_artifacts import record_document_artifact
from app.services.expert_review import append_audit_event, record_decision
from app.services.scheme_readiness import assess_scheme_readiness
from app.services.scheme_workflow_profile import snapshot_task_workflow
from app.services.upload_validation import UploadValidationError, validate_docx_upload
from app.services.template_versioning import bind_task_template_snapshot


router = APIRouter(prefix="/projects", tags=["projects"])

MAX_SUPPORTING_FILE_COUNT = 10
MAX_SITE_IMAGE_COUNT = 20
MAX_ALL_ATTACHMENTS_BYTES = 100 * 1024 * 1024


def _safe_attachment_filename(filename: str | None) -> str:
    raw = (filename or "file").strip() or "file"
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", raw)
    return safe[-180:] or "file"


def _can_manage_project(project: Project, user: User) -> bool:
    return user.role in (UserRole.admin, UserRole.review_admin) or project.created_by_id == user.id


def _load_project(db: Session, project_id: int) -> Project:
    row = db.get(Project, project_id)
    if row is None or row.archived_at is not None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return row


@router.get("", response_model=list[ProjectPublic])
def list_projects(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProjectPublic]:
    q = db.query(Project).filter(Project.archived_at.is_(None))
    if user.role not in (UserRole.admin, UserRole.review_admin, UserRole.expert):
        q = q.filter(Project.created_by_id == user.id)
    return q.order_by(Project.id.desc()).limit(500).all()


@router.post("", response_model=ProjectPublic, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Project:
    row = Project(**body.model_dump(), created_by_id=user.id)
    db.add(row)
    db.flush()
    append_audit_event(db, user.id, "project", row.id, "created", body.model_dump())
    db.commit()
    db.refresh(row)
    return row


@router.get("/{project_id}", response_model=ProjectPublic)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Project:
    row = _load_project(db, project_id)
    if not _can_manage_project(row, user) and user.role != UserRole.expert:
        raise HTTPException(status_code=403, detail="无权查看该项目")
    return row


@router.patch("/{project_id}", response_model=ProjectPublic)
def update_project(
    project_id: int,
    body: ProjectUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Project:
    row = _load_project(db, project_id)
    if not _can_manage_project(row, user):
        raise HTTPException(status_code=403, detail="无权修改该项目")
    changes = body.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(row, key, value)
    append_audit_event(db, user.id, "project", row.id, "updated", changes)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    row = _load_project(db, project_id)
    if not _can_manage_project(row, user):
        raise HTTPException(status_code=403, detail="无权归档该项目")
    row.archived_at = datetime.now(UTC)
    append_audit_event(db, user.id, "project", row.id, "archived", {})
    db.commit()


@router.get("/{project_id}/revisions", response_model=list[DocumentRevisionPublic])
def list_revisions(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DocumentRevision]:
    project = _load_project(db, project_id)
    if not _can_manage_project(project, user) and user.role != UserRole.expert:
        raise HTTPException(status_code=403, detail="无权查看项目版本")
    return (
        db.query(DocumentRevision)
        .filter(DocumentRevision.project_id == project_id)
        .order_by(DocumentRevision.id.desc())
        .all()
    )


@router.post(
    "/{project_id}/revisions",
    response_model=RevisionTaskCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_revision_and_review(
    project_id: int,
    scheme_type_id: int = Form(...),
    version_label: str = Form("V1"),
    parent_revision_id: int | None = Form(None),
    review_focus: str = Form(""),
    idempotency_key: str = Form(""),
    priority: int = Form(0),
    file: UploadFile = File(...),
    supporting_files: list[UploadFile] | None = File(default=None, alias="attachments"),
    site_images: list[UploadFile] | None = File(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RevisionTaskCreateResponse:
    supporting_files = supporting_files if isinstance(supporting_files, list) else []
    site_images = site_images if isinstance(site_images, list) else []
    if len(supporting_files) > MAX_SUPPORTING_FILE_COUNT:
        raise HTTPException(
            status_code=400,
            detail=f"辅助资料一次最多上传{MAX_SUPPORTING_FILE_COUNT}个",
        )
    if len(site_images) > MAX_SITE_IMAGE_COUNT:
        raise HTTPException(
            status_code=400,
            detail=f"现场图片一次最多上传{MAX_SITE_IMAGE_COUNT}张",
        )
    normalized_idempotency = (
        idempotency_key.strip() if isinstance(idempotency_key, str) else ""
    )
    normalized_version_label = (
        version_label.strip() if isinstance(version_label, str) else "V1"
    )
    normalized_review_focus = (
        review_focus.strip() if isinstance(review_focus, str) else ""
    )
    normalized_parent_revision_id = (
        parent_revision_id if isinstance(parent_revision_id, int) else None
    )
    if len(normalized_idempotency) > 64:
        raise HTTPException(status_code=400, detail="idempotency_key 最长64个字符")
    project = _load_project(db, project_id)
    if not _can_manage_project(project, user):
        raise HTTPException(status_code=403, detail="无权提交该项目方案")
    if normalized_idempotency:
        existing_task = (
            db.query(SchemeReviewTask)
            .filter(
                SchemeReviewTask.user_id == user.id,
                SchemeReviewTask.idempotency_key == normalized_idempotency,
            )
            .first()
        )
        if existing_task is not None:
            existing_round = (
                db.query(ReviewRound)
                .filter(ReviewRound.task_id == existing_task.id)
                .first()
            )
            existing_revision = (
                db.get(DocumentRevision, existing_round.document_revision_id)
                if existing_round is not None and existing_round.document_revision_id is not None
                else None
            )
            if existing_round is None or existing_revision is None:
                raise HTTPException(
                    status_code=409,
                    detail="该幂等键已被非项目审核任务使用，请更换后重试",
                )
            if existing_revision.project_id != project_id:
                raise HTTPException(
                    status_code=409,
                    detail="该幂等键已用于其他项目，请更换后重试",
                )
            return RevisionTaskCreateResponse(
                revision=DocumentRevisionPublic.model_validate(existing_revision),
                task_id=existing_task.id,
                review_round_id=existing_round.id,
            )
    scheme = db.get(SchemeType, scheme_type_id)
    if scheme is None:
        raise HTTPException(status_code=404, detail="方案类型不存在")
    readiness = assess_scheme_readiness(db, scheme)
    if scheme.lifecycle_status != "published" or not readiness.ready:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "scheme_not_ready",
                "readiness_status": readiness.status,
                "readiness_issues": list(readiness.issues),
            },
        )
    template = (
        db.query(SchemeTemplate).filter(SchemeTemplate.scheme_type_id == scheme_type_id).first()
    )
    if template is None:
        raise HTTPException(status_code=409, detail="该方案类型尚未配置模板")
    if normalized_parent_revision_id is not None:
        parent = db.get(DocumentRevision, normalized_parent_revision_id)
        if parent is None or parent.project_id != project_id:
            raise HTTPException(status_code=400, detail="父版本不属于当前项目")
        if parent.scheme_type_id != scheme_type_id:
            raise HTTPException(status_code=400, detail="父版本与当前方案类型不一致")
    data = await file.read()
    try:
        validate_docx_upload(file.filename, data)
    except UploadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        primary_scan = scan_upload_bytes(data, filename=file.filename or "scheme.docx")
    except MalwareDetectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MalwareScanError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    pending_attachments: list[tuple[str, UploadFile, bytes, str, str]] = []
    attachments_total_bytes = 0
    for kind, uploads in (
        ("supporting_document", supporting_files),
        ("site_image", site_images),
    ):
        for upload in uploads:
            payload = await upload.read()
            attachments_total_bytes += len(payload)
            if attachments_total_bytes > MAX_ALL_ATTACHMENTS_BYTES:
                raise HTTPException(status_code=400, detail="全部附件合计不能超过100MB")
            try:
                validated = validate_supporting_attachment(
                    upload.filename, payload, kind=kind
                )
            except UploadValidationError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"附件 {upload.filename or '-'}: {exc!s}",
                ) from exc
            try:
                attachment_scan = scan_upload_bytes(
                    payload,
                    filename=upload.filename or "attachment",
                )
            except MalwareDetectedError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except MalwareScanError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            pending_attachments.append(
                (
                    kind,
                    upload,
                    payload,
                    validated.content_type,
                    attachment_scan.status,
                )
            )

    safe_version = (normalized_version_label or "V1")[:64] or "V1"
    object_key = f"projects/{project_id}/revisions/{uuid.uuid4().hex}.docx"
    digest = hashlib.sha256(data).hexdigest()
    storage_settings = get_settings()
    uploaded_attachment_keys: list[str] = []
    try:
        minio_storage.put_object(
            object_key,
            data,
            length=len(data),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        attachment_rows: list[ReviewAttachment] = []
        for kind, upload, payload, content_type, scan_status in pending_attachments:
            attachment_key = (
                f"projects/{project_id}/attachments/{uuid.uuid4().hex}"
                f"_{_safe_attachment_filename(upload.filename)}"
            )
            minio_storage.put_object(
                attachment_key,
                payload,
                length=len(payload),
                content_type=content_type,
            )
            uploaded_attachment_keys.append(attachment_key)
            attachment_rows.append(
                ReviewAttachment(
                    kind=kind,
                    original_filename=upload.filename or "attachment",
                    content_type=content_type,
                    minio_bucket=storage_settings.minio_bucket,
                    object_key=attachment_key,
                    sha256=hashlib.sha256(payload).hexdigest(),
                    size_bytes=len(payload),
                    scan_status=scan_status,
                )
            )
        revision = DocumentRevision(
            project_id=project_id,
            scheme_type_id=scheme_type_id,
            parent_revision_id=normalized_parent_revision_id,
            version_label=safe_version,
            original_filename=file.filename or "scheme.docx",
            minio_bucket=storage_settings.minio_bucket,
            object_key=object_key,
            sha256=digest,
            created_by_id=user.id,
        )
        db.add(revision)
        db.flush()
        now = datetime.now(UTC)
        task = SchemeReviewTask(
            scheme_type_id=scheme_type_id,
            user_id=user.id,
            status=ReviewTaskStatus.pending,
            review_conclusion=ReviewConclusion.not_reviewed,
            completeness_status=CompletenessStatus.unavailable,
            human_status=HumanReviewStatus.pending,
            idempotency_key=normalized_idempotency or None,
            priority=(
                max(-10, min(10, priority if isinstance(priority, int) else 0))
                if user.role in (UserRole.admin, UserRole.review_admin)
                else 0
            ),
            attempt_no=1,
            minio_bucket=storage_settings.minio_bucket,
            object_key=object_key,
            original_filename=file.filename or "scheme.docx",
            created_at=now,
            updated_at=now,
            review_log=(
                f"[{now.strftime('%Y-%m-%d %H:%M:%S UTC')}] INFO 项目版本已提交，等待处理\n"
                f"[{now.strftime('%Y-%m-%d %H:%M:%S UTC')}] INFO 输入文件安全扫描状态：{primary_scan.status}\n"
            ),
        )
        task.attachments.extend(attachment_rows)
        db.add(task)
        db.flush()
        record_document_artifact(
            db,
            task_id=task.id,
            artifact_kind="original",
            object_key=object_key,
            content=data,
            minio_bucket=storage_settings.minio_bucket,
            original_filename=file.filename or "scheme.docx",
            created_by_id=user.id,
        )
        snapshot_task_workflow(
            db,
            task,
            scheme_category=scheme.category,
            scheme_name=scheme.name,
            project_name=project.name,
            project_region=project.region,
            review_focus=normalized_review_focus,
        )
        bind_task_template_snapshot(db, task, template, actor_id=user.id)
        parent_round_id = None
        round_no = 1
        if normalized_parent_revision_id is not None:
            previous = (
                db.query(ReviewRound)
                .filter(ReviewRound.document_revision_id == normalized_parent_revision_id)
                .order_by(ReviewRound.round_no.desc())
                .first()
            )
            if previous:
                parent_round_id = previous.id
                round_no = previous.round_no + 1
        review_round = ReviewRound(
            document_revision_id=revision.id,
            task_id=task.id,
            parent_round_id=parent_round_id,
            round_no=round_no,
            status="pending_ai",
        )
        db.add(review_round)
        db.flush()
        record_decision(
            db,
            review_round,
            user.id,
            "revision_submitted",
            None,
            "pending_ai",
            f"项目版本 {safe_version} 已提交",
        )
        append_audit_event(
            db,
            user.id,
            "document_revision",
            revision.id,
            "submitted",
            {"task_id": task.id, "sha256": digest, "version_label": safe_version},
        )
        db.commit()
        db.refresh(revision)
    except IntegrityError as exc:
        db.rollback()
        minio_storage.remove_object_if_exists(object_key)
        for attachment_key in uploaded_attachment_keys:
            minio_storage.remove_object_if_exists(attachment_key)
        if normalized_idempotency:
            existing_task = (
                db.query(SchemeReviewTask)
                .filter(
                    SchemeReviewTask.user_id == user.id,
                    SchemeReviewTask.idempotency_key == normalized_idempotency,
                )
                .first()
            )
            existing_round = (
                db.query(ReviewRound)
                .filter(ReviewRound.task_id == existing_task.id)
                .first()
                if existing_task is not None
                else None
            )
            existing_revision = (
                db.get(DocumentRevision, existing_round.document_revision_id)
                if existing_round is not None and existing_round.document_revision_id is not None
                else None
            )
            if existing_task is not None and existing_round is not None and existing_revision is not None and existing_revision.project_id == project_id:
                return RevisionTaskCreateResponse(
                    revision=DocumentRevisionPublic.model_validate(existing_revision),
                    task_id=existing_task.id,
                    review_round_id=existing_round.id,
                )
        raise HTTPException(status_code=409, detail="项目中该方案类型的版本号已存在") from exc
    except Exception:
        db.rollback()
        minio_storage.remove_object_if_exists(object_key)
        for attachment_key in uploaded_attachment_keys:
            minio_storage.remove_object_if_exists(attachment_key)
        raise
    return RevisionTaskCreateResponse(
        revision=DocumentRevisionPublic.model_validate(revision),
        task_id=task.id,
        review_round_id=review_round.id,
    )
