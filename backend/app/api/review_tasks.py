import json
import hashlib
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, defer, joinedload
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models.scheme_review_task import (
    CompletenessStatus,
    HumanReviewStatus,
    ReviewConclusion,
    ReviewTaskStatus,
    SchemeReviewTask,
)
from app.models.review_governance import ReviewRound
from app.models.document_artifact import DocumentArtifact, OnlyofficeEditSession
from app.models.review_attachment import ReviewAttachment
from app.models.scheme_template import SchemeTemplate
from app.models.scheme_type import SchemeType
from app.models.user import User, UserRole
from app.schemas.onlyoffice_editor import OnlyofficeEditorConfigResponse
from app.schemas.review_task import (
    DebugPromptPublic,
    DocumentArtifactPublic,
    ReviewTaskCreateResponse,
    ReviewTaskPublic,
)
from app.schemas.template import DownloadUrlResponse
from app.services import minio_storage
from app.schemas.review_report import ReviewReportV1
from app.services.onlyoffice import (
    assert_onlyoffice_ready,
    build_editor_config,
    make_editor_token,
    make_file_access_token,
    verify_file_access_token,
)
from app.services.review_report_docx import build_audit_report_docx
from app.services.review_settings import DEFAULT_SYSTEM_NAME, get_or_create_review_settings
from app.services.scheme_readiness import assess_scheme_readiness
from app.services.scheme_workflow_profile import canonical_task_inputs, snapshot_task_workflow
from app.services.expert_review import ensure_round_for_task
from app.services.upload_validation import UploadValidationError, validate_docx_upload
from app.services.template_versioning import bind_task_template_snapshot
from app.services.attachment_validation import validate_supporting_attachment
from app.services.malware_scan import (
    MalwareDetectedError,
    MalwareScanError,
    scan_bytes as scan_upload_bytes,
)
from app.services.document_artifacts import (
    latest_document_artifact,
    record_document_artifact,
)

router = APIRouter(prefix="/review-tasks", tags=["review-tasks"])

MAX_UPLOAD_BYTES = 30 * 1024 * 1024
MAX_SUPPORTING_FILE_COUNT = 10
MAX_SITE_IMAGE_COUNT = 20
MAX_ALL_ATTACHMENTS_BYTES = 100 * 1024 * 1024


def _can_access_review_task(db: Session, task: SchemeReviewTask, user: User) -> bool:
    if task.user_id == user.id or user.role in (UserRole.admin, UserRole.review_admin):
        return True
    if user.role == UserRole.expert:
        return (
            db.query(ReviewRound.id)
            .filter(
                ReviewRound.task_id == task.id,
                ReviewRound.assigned_expert_id == user.id,
            )
            .first()
            is not None
        )
    return False


def _audit_report_filename(original_filename: str) -> str:
    raw = (original_filename or "").strip() or "document"
    base = re.sub(r"\.docx$", "", raw, flags=re.IGNORECASE).strip() or "document"
    safe = re.sub(r'[\\/:*?"<>|]', "_", base).strip() or "document"
    return f"{safe}_审核报告.docx"


def _safe_attachment_filename(filename: str | None) -> str:
    raw = (filename or "file").strip() or "file"
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", raw)
    return safe[-180:] or "file"


def _parse_review_report_json(raw: str | None) -> ReviewReportV1 | None:
    if not (raw or "").strip():
        return None
    try:
        return ReviewReportV1.model_validate(json.loads(raw))
    except Exception:
        return None


def _task_public(
    t: SchemeReviewTask,
    *,
    include_review_log: bool = True,
    include_result_json: bool = True,
    include_debug_prompts: bool = True,
    owner_username: str | None = None,
) -> ReviewTaskPublic:
    debug_prompts: list[DebugPromptPublic] | None = None
    if include_debug_prompts and include_result_json and (t.review_result_json or "").strip():
        try:
            parsed = json.loads(t.review_result_json or "{}")
            raw_prompts = parsed.get("debug_prompts")
            if isinstance(raw_prompts, list):
                rows: list[DebugPromptPublic] = []
                for it in raw_prompts:
                    if not isinstance(it, dict):
                        continue
                    rows.append(
                        DebugPromptPublic(
                            step_id=str(it.get("step_id") or ""),
                            template_node_id=str(it.get("template_node_id") or ""),
                            title_path=[str(x) for x in (it.get("title_path") or []) if str(x)],
                            prompt_text=str(it.get("prompt_text") or ""),
                            prompt_length=int(it.get("prompt_length") or 0),
                            created_at=str(it.get("created_at") or ""),
                        )
                    )
                debug_prompts = rows or None
        except Exception:
            debug_prompts = None

    st = t.scheme_type
    return ReviewTaskPublic(
        id=t.id,
        scheme_type_id=t.scheme_type_id,
        scheme_category=st.category if st else "",
        scheme_name=st.name if st else "",
        owner_username=owner_username,
        status=t.status,
        review_conclusion=t.review_conclusion,
        completeness_status=t.completeness_status,
        human_status=t.human_status,
        idempotency_key=t.idempotency_key,
        priority=t.priority,
        attempt_no=t.attempt_no,
        retry_of_task_id=t.retry_of_task_id,
        cancel_requested_at=t.cancel_requested_at,
        lease_expires_at=t.lease_expires_at,
        dify_workflow_profile_id=t.dify_workflow_profile_id,
        dify_workflow_profile_version=t.dify_workflow_profile_version,
        dify_workflow_run_id=t.dify_workflow_run_id,
        dify_workflow_task_id=t.dify_workflow_task_id,
        dify_workflow_status=t.dify_workflow_status,
        dify_workflow_output_format=t.dify_workflow_output_format,
        result_text=t.result_text,
        error_message=t.error_message,
        review_stage=t.review_stage,
        review_result_json=(t.review_result_json if include_result_json else None),
        output_object_key=t.output_object_key,
        started_at=t.started_at,
        finished_at=t.finished_at,
        duration_ms=t.duration_ms,
        input_tokens=t.input_tokens,
        output_tokens=t.output_tokens,
        total_tokens=t.total_tokens,
        review_log=(t.review_log if include_review_log else None),
        debug_prompts=debug_prompts if include_debug_prompts else None,
        original_filename=t.original_filename,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


@router.get("", response_model=list[ReviewTaskPublic])
def list_my_tasks(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = 100,
) -> list[ReviewTaskPublic]:
    opts = [
        joinedload(SchemeReviewTask.scheme_type),
        defer(SchemeReviewTask.review_log),
        defer(SchemeReviewTask.review_result_json),
    ]
    if user.role == UserRole.admin:
        opts.append(joinedload(SchemeReviewTask.user))
    q = db.query(SchemeReviewTask).options(*opts)
    if user.role != UserRole.admin:
        q = q.filter(SchemeReviewTask.user_id == user.id)
    q = q.order_by(SchemeReviewTask.id.desc())
    rows = q.limit(min(limit, 200)).all()
    return [
        _task_public(
            r,
            include_review_log=False,
            include_result_json=False,
            include_debug_prompts=False,
            owner_username=(r.user.username if user.role == UserRole.admin else None),
        )
        for r in rows
    ]


@router.get("/{task_id}", response_model=ReviewTaskPublic)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReviewTaskPublic:
    t = (
        db.query(SchemeReviewTask)
        .options(joinedload(SchemeReviewTask.scheme_type), joinedload(SchemeReviewTask.user))
        .filter(SchemeReviewTask.id == task_id)
        .first()
    )
    if t is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not _can_access_review_task(db, t, user):
        raise HTTPException(status_code=403, detail="无权查看该任务")
    return _task_public(t, owner_username=t.user.username)


@router.get("/{task_id}/artifacts", response_model=list[DocumentArtifactPublic])
def list_task_artifacts(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DocumentArtifact]:
    task = db.get(SchemeReviewTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not _can_access_review_task(db, task, user):
        raise HTTPException(status_code=403, detail="无权查看该任务文档版本")
    return (
        db.query(DocumentArtifact)
        .filter(DocumentArtifact.task_id == task_id)
        .order_by(DocumentArtifact.created_at, DocumentArtifact.id)
        .all()
    )


@router.get("/{task_id}/artifacts/{artifact_id}/download-url", response_model=DownloadUrlResponse)
def get_artifact_download_url(
    task_id: int,
    artifact_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DownloadUrlResponse:
    task = db.get(SchemeReviewTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not _can_access_review_task(db, task, user):
        raise HTTPException(status_code=403, detail="无权下载该任务文档版本")
    artifact = db.get(DocumentArtifact, artifact_id)
    if artifact is None or artifact.task_id != task_id:
        raise HTTPException(status_code=404, detail="文档版本不存在")
    return DownloadUrlResponse(
        url=minio_storage.presigned_get_url(
            artifact.object_key,
            expires_seconds=3600,
            download_filename=artifact.original_filename or "document.docx",
        ),
        expires_seconds=3600,
    )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    t = db.get(SchemeReviewTask, task_id)
    if t is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if t.user_id != user.id and user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="无权删除该任务")
    if t.status in (ReviewTaskStatus.pending, ReviewTaskStatus.processing):
        raise HTTPException(status_code=409, detail="排队或处理中的任务不能删除")
    if db.query(ReviewRound.id).filter(ReviewRound.task_id == t.id).first() is not None:
        # Review rounds, expert decisions and audit evidence are governance
        # records.  The FK intentionally prevents deletion; check before any
        # object-store mutation so a failed DELETE cannot orphan the task.
        raise HTTPException(status_code=409, detail="任务已进入复核与审计链，禁止删除")
    source_key = (t.object_key or "").strip()
    source_prefix = source_key.rsplit(".", maxsplit=1)[0] if "." in source_key else source_key
    if source_prefix:
        minio_storage.remove_objects_with_prefix(f"{source_prefix}/images/")
    minio_storage.remove_object_if_exists(t.object_key)
    if (t.output_object_key or "").strip():
        minio_storage.remove_object_if_exists(t.output_object_key.strip())
    db.delete(t)
    db.commit()


@router.get("/{task_id}/audit-report")
def download_audit_report(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    t = (
        db.query(SchemeReviewTask)
        .options(joinedload(SchemeReviewTask.scheme_type))
        .filter(SchemeReviewTask.id == task_id)
        .first()
    )
    if t is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not _can_access_review_task(db, t, user):
        raise HTTPException(status_code=403, detail="无权下载该任务报告")
    if t.status in (ReviewTaskStatus.pending, ReviewTaskStatus.processing):
        raise HTTPException(status_code=409, detail="任务尚未完成，暂无法导出审核报告")
    report = _parse_review_report_json(t.review_result_json)
    if report is None or not report.steps:
        raise HTTPException(status_code=404, detail="暂无审核报告数据")
    settings = get_or_create_review_settings(db)
    system_name = (settings.system_name or "").strip() or DEFAULT_SYSTEM_NAME
    content = build_audit_report_docx(t, report, system_name=system_name)
    filename = _audit_report_filename(t.original_filename)
    ascii_fallback = "audit-report.docx"
    encoded_name = quote(filename, safe="")
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_fallback}"; '
                f"filename*=UTF-8''{encoded_name}"
            )
        },
    )


@router.get("/{task_id}/output-download-url", response_model=DownloadUrlResponse)
def get_output_download_url(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DownloadUrlResponse:
    t = (
        db.query(SchemeReviewTask)
        .options(joinedload(SchemeReviewTask.scheme_type))
        .filter(SchemeReviewTask.id == task_id)
        .first()
    )
    if t is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not _can_access_review_task(db, t, user):
        raise HTTPException(status_code=403, detail="无权下载该任务文件")
    if t.status in (ReviewTaskStatus.pending, ReviewTaskStatus.processing):
        raise HTTPException(status_code=409, detail="任务尚未完成，暂无法导出")
    if t.status != ReviewTaskStatus.succeeded:
        raise HTTPException(status_code=409, detail="审核技术失败，没有可作为成果导出的文件")
    ai_artifact = latest_document_artifact(db, t.id, "ai_annotated")
    if not isinstance(ai_artifact, DocumentArtifact):
        ai_artifact = None
    object_key = (
        ai_artifact.object_key
        if ai_artifact is not None
        else (t.output_object_key or "").strip()
    )
    if not object_key:
        raise HTTPException(status_code=404, detail="审核已完成但结果文档缺失，请联系管理员")
    if ai_artifact is not None:
        url = minio_storage.presigned_get_url(
            object_key,
            expires_seconds=3600,
            download_filename=ai_artifact.original_filename,
        )
    else:
        url = minio_storage.presigned_get_url(object_key, expires_seconds=3600)
    return DownloadUrlResponse(url=url, expires_seconds=3600)


@router.get("/{task_id}/onlyoffice/editor-config", response_model=OnlyofficeEditorConfigResponse)
def get_onlyoffice_editor_config(
    task_id: int,
    mode: str = Query("edit", description="edit：可编辑；view：仅预览（人工审阅左侧对照）"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OnlyofficeEditorConfigResponse:
    t = (
        db.query(SchemeReviewTask)
        .options(joinedload(SchemeReviewTask.scheme_type))
        .filter(SchemeReviewTask.id == task_id)
        .first()
    )
    if t is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not _can_access_review_task(db, t, user):
        raise HTTPException(status_code=403, detail="无权编辑该任务文档")
    if t.status != ReviewTaskStatus.succeeded:
        raise HTTPException(status_code=409, detail="审核任务未成功完成，不能编辑不完整的结果文档")
    if not (t.output_object_key or "").strip():
        raise HTTPException(status_code=404, detail="审核结果文档尚未生成")
    normalized_mode = (mode or "edit").strip().lower()
    if normalized_mode not in ("edit", "view"):
        raise HTTPException(status_code=400, detail="mode 必须为 edit 或 view")
    is_signed = (
        db.query(ReviewRound.id)
        .filter(ReviewRound.task_id == t.id, ReviewRound.status == "signed")
        .first()
        is not None
    )
    view_only = normalized_mode == "view" or is_signed
    try:
        eff = assert_onlyoffice_ready(db)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    file_token = make_file_access_token(t.id)
    edit_session: OnlyofficeEditSession | None = None
    document_key: str | None = None
    if not view_only:
        document_key = secrets.token_hex(32)
        edit_session = OnlyofficeEditSession(
            task_id=t.id,
            document_key=document_key,
            source_object_key=t.output_object_key.strip(),
            current_object_key=t.output_object_key.strip(),
            created_by_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(hours=8),
        )
        db.add(edit_session)
        db.flush()
    config = build_editor_config(
        task=t,
        user=user,
        eff=eff,
        file_token=file_token,
        view_only=view_only,
        document_key=document_key,
        callback_session_id=edit_session.id if edit_session is not None else None,
    )
    oo_token = make_editor_token(config, eff.jwt_secret)
    if edit_session is not None:
        db.commit()
    docs_url = eff.docs_url.rstrip("/")
    return OnlyofficeEditorConfigResponse(docs_url=docs_url, config=config, token=oo_token)


@router.get("/{task_id}/onlyoffice/document")
def download_onlyoffice_document(
    task_id: int,
    db: Session = Depends(get_db),
    token: str = Query(..., min_length=1),
) -> StreamingResponse:
    tid = verify_file_access_token(token)
    if tid is None or tid != task_id:
        raise HTTPException(status_code=403, detail="无效或过期的访问令牌")
    t = db.get(SchemeReviewTask, task_id)
    if (
        t is None
        or t.status != ReviewTaskStatus.succeeded
        or not (t.output_object_key or "").strip()
    ):
        raise HTTPException(status_code=404, detail="文档不存在")
    content = minio_storage.get_object_bytes(t.output_object_key.strip())
    title = (t.original_filename or "document.docx").strip() or "document.docx"
    ascii_fallback = "document.docx"
    encoded_name = quote(title, safe="")
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_fallback}"; '
                f"filename*=UTF-8''{encoded_name}"
            )
        },
    )


@router.post("", response_model=ReviewTaskCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    scheme_type_id: int = Form(...),
    project_name: str = Form(""),
    project_region: str = Form(""),
    review_focus: str = Form(""),
    idempotency_key: str = Form(""),
    priority: int = Form(0),
    file: UploadFile = File(...),
    supporting_files: list[UploadFile] | None = File(default=None, alias="attachments"),
    site_images: list[UploadFile] | None = File(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReviewTaskCreateResponse:
    # FastAPI resolves ``File`` defaults for HTTP requests, while a few service-level
    # tests (and internal callers) invoke this coroutine directly.  In that case the
    # unresolved parameter is a ``File`` descriptor rather than an upload list.
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
    if len(normalized_idempotency) > 64:
        raise HTTPException(status_code=400, detail="idempotency_key 最长64个字符")
    if normalized_idempotency:
        existing_task = (
            db.query(SchemeReviewTask)
            .options(
                joinedload(SchemeReviewTask.scheme_type),
                joinedload(SchemeReviewTask.user),
            )
            .filter(
                SchemeReviewTask.user_id == user.id,
                SchemeReviewTask.idempotency_key == normalized_idempotency,
            )
            .first()
        )
        if existing_task is not None:
            return ReviewTaskCreateResponse(
                task=_task_public(existing_task, owner_username=user.username),
                message="重复提交已返回原任务",
            )
    scheme = db.get(SchemeType, scheme_type_id)
    if scheme is None:
        raise HTTPException(status_code=404, detail="方案类型不存在")
    tmpl = db.query(SchemeTemplate).filter(SchemeTemplate.scheme_type_id == scheme_type_id).first()
    if tmpl is None:
        raise HTTPException(status_code=400, detail="该方案类型尚未上传模版，无法提交审核")
    readiness = assess_scheme_readiness(db, scheme)
    if not readiness.ready:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "scheme_not_ready",
                "readiness_status": readiness.status,
                "readiness_issues": list(readiness.issues),
            },
        )
    if getattr(scheme, "lifecycle_status", "draft") != "published":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "scheme_not_published",
                "readiness_status": readiness.status,
                "readiness_issues": ["方案类型尚未发布，管理员验证并发布后才可发起正式审核"],
            },
        )

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

    s = get_settings()
    object_key = f"reviews/{scheme_type_id}/{uuid.uuid4().hex}.docx"
    try:
        minio_storage.put_object(
            object_key,
            data,
            length=len(data),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"存储失败: {e!s}") from e

    uploaded_attachment_rows: list[ReviewAttachment] = []
    uploaded_attachment_keys: list[str] = []
    try:
        for kind, upload, payload, content_type, scan_status in pending_attachments:
            attachment_key = (
                f"reviews/{scheme_type_id}/attachments/{uuid.uuid4().hex}"
                f"_{_safe_attachment_filename(upload.filename)}"
            )
            minio_storage.put_object(
                attachment_key,
                payload,
                length=len(payload),
                content_type=content_type,
            )
            uploaded_attachment_keys.append(attachment_key)
            uploaded_attachment_rows.append(
                ReviewAttachment(
                    kind=kind,
                    original_filename=upload.filename or "attachment",
                    content_type=content_type,
                    minio_bucket=s.minio_bucket,
                    object_key=attachment_key,
                    sha256=hashlib.sha256(payload).hexdigest(),
                    size_bytes=len(payload),
                    scan_status=scan_status,
                )
            )
    except Exception as exc:
        minio_storage.remove_object_if_exists(object_key)
        for key in uploaded_attachment_keys:
            minio_storage.remove_object_if_exists(key)
        raise HTTPException(status_code=502, detail=f"附件存储失败: {exc!s}") from exc

    now = datetime.now(UTC)
    ts = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    row = SchemeReviewTask(
        scheme_type_id=scheme_type_id,
        user_id=user.id,
        status=ReviewTaskStatus.pending,
        review_conclusion=ReviewConclusion.not_reviewed,
        completeness_status=CompletenessStatus.unavailable,
        human_status=HumanReviewStatus.pending,
        idempotency_key=normalized_idempotency or None,
        priority=max(-10, min(10, priority if user.role == UserRole.admin else 0)),
        attempt_no=1,
        minio_bucket=s.minio_bucket,
        object_key=object_key,
        original_filename=file.filename or "scheme.docx",
        created_at=now,
        updated_at=now,
        review_log=(
            f"[{ts}] INFO 任务已提交，等待处理\n"
            f"[{ts}] INFO 输入文件安全扫描状态：{primary_scan.status}\n"
        ),
    )
    db.add(row)
    db.flush()
    for attachment in uploaded_attachment_rows:
        attachment.task_id = row.id
        db.add(attachment)
    db.flush()
    record_document_artifact(
        db,
        task_id=row.id,
        artifact_kind="original",
        object_key=object_key,
        content=data,
        minio_bucket=s.minio_bucket,
        original_filename=file.filename or "scheme.docx",
        created_by_id=user.id,
    )
    snapshot_task_workflow(
        db,
        row,
        scheme_category=scheme.category,
        scheme_name=scheme.name,
        project_name=project_name,
        project_region=project_region,
        review_focus=review_focus,
    )
    bind_task_template_snapshot(db, row, tmpl, actor_id=user.id)
    ensure_round_for_task(db, row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        minio_storage.remove_object_if_exists(object_key)
        for key in uploaded_attachment_keys:
            minio_storage.remove_object_if_exists(key)
        if normalized_idempotency:
            existing_task = (
                db.query(SchemeReviewTask)
                .options(
                    joinedload(SchemeReviewTask.scheme_type),
                    joinedload(SchemeReviewTask.user),
                )
                .filter(
                    SchemeReviewTask.user_id == user.id,
                    SchemeReviewTask.idempotency_key == normalized_idempotency,
                )
                .first()
            )
            if existing_task is not None:
                return ReviewTaskCreateResponse(
                    task=_task_public(existing_task, owner_username=user.username),
                    message="重复提交已返回原任务",
                )
        raise HTTPException(status_code=409, detail="任务提交冲突，请重试") from exc
    except Exception:
        db.rollback()
        minio_storage.remove_object_if_exists(object_key)
        for key in uploaded_attachment_keys:
            minio_storage.remove_object_if_exists(key)
        raise
    loaded = (
        db.query(SchemeReviewTask)
        .options(joinedload(SchemeReviewTask.scheme_type), joinedload(SchemeReviewTask.user))
        .filter(SchemeReviewTask.id == row.id)
        .first()
    )
    if loaded is None:
        raise HTTPException(status_code=500, detail="创建任务失败")

    return ReviewTaskCreateResponse(task=_task_public(loaded, owner_username=user.username))


@router.post("/{task_id}/cancel", response_model=ReviewTaskPublic)
def cancel_review_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReviewTaskPublic:
    task = (
        db.query(SchemeReviewTask)
        .options(joinedload(SchemeReviewTask.scheme_type), joinedload(SchemeReviewTask.user))
        .filter(SchemeReviewTask.id == task_id)
        .first()
    )
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.user_id != user.id and user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="无权取消该任务")
    if task.status not in (ReviewTaskStatus.pending, ReviewTaskStatus.processing):
        raise HTTPException(status_code=409, detail="仅排队或处理中的任务可取消")
    now = datetime.now(UTC)
    task.cancel_requested_at = now
    task.review_log = (task.review_log or "") + (
        f"[{now.strftime('%Y-%m-%d %H:%M:%S UTC')}] WARNING 用户请求取消任务\n"
    )
    if task.status == ReviewTaskStatus.pending:
        task.status = ReviewTaskStatus.canceled
        task.finished_at = now
        task.result_text = "任务已由用户取消，未形成审核结论。"
        task.error_message = None
        task.lease_owner = None
        task.lease_expires_at = None
        ensure_round_for_task(db, task)
    db.commit()
    return _task_public(task, owner_username=task.user.username)


@router.post("/{task_id}/retry", response_model=ReviewTaskCreateResponse, status_code=201)
def retry_review_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReviewTaskCreateResponse:
    source = (
        db.query(SchemeReviewTask)
        .options(
            joinedload(SchemeReviewTask.scheme_type),
            joinedload(SchemeReviewTask.user),
            joinedload(SchemeReviewTask.attachments),
        )
        .filter(SchemeReviewTask.id == task_id)
        .first()
    )
    if source is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if source.user_id != user.id and user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="无权重试该任务")
    if source.status not in (ReviewTaskStatus.failed, ReviewTaskStatus.canceled):
        raise HTTPException(status_code=409, detail="仅技术失败或已取消任务可重试")
    source_bytes = minio_storage.get_object_bytes(source.object_key)
    new_key = f"reviews/{source.scheme_type_id}/{uuid.uuid4().hex}.docx"
    minio_storage.put_object(
        new_key,
        source_bytes,
        length=len(source_bytes),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    now = datetime.now(UTC)
    task = SchemeReviewTask(
        scheme_type_id=source.scheme_type_id,
        user_id=source.user_id,
        status=ReviewTaskStatus.pending,
        review_conclusion=ReviewConclusion.not_reviewed,
        completeness_status=CompletenessStatus.unavailable,
        human_status=HumanReviewStatus.pending,
        priority=source.priority,
        attempt_no=int(source.attempt_no or 1) + 1,
        retry_of_task_id=source.id,
        minio_bucket=source.minio_bucket,
        object_key=new_key,
        original_filename=source.original_filename,
        template_version_id=source.template_version_id,
        template_snapshot_json=source.template_snapshot_json,
        dify_workflow_profile_id=source.dify_workflow_profile_id,
        dify_workflow_profile_version=source.dify_workflow_profile_version,
        dify_workflow_inputs_snapshot=source.dify_workflow_inputs_snapshot,
        dify_workflow_config_snapshot=source.dify_workflow_config_snapshot,
        created_at=now,
        updated_at=now,
        review_log=f"[{now.strftime('%Y-%m-%d %H:%M:%S UTC')}] INFO 从任务 #{source.id} 创建第 {int(source.attempt_no or 1) + 1} 次尝试\n",
    )
    try:
        db.add(task)
        db.flush()
        record_document_artifact(
            db,
            task_id=task.id,
            artifact_kind="original",
            object_key=new_key,
            content=source_bytes,
            minio_bucket=source.minio_bucket,
            original_filename=source.original_filename,
            created_by_id=user.id,
        )
    except Exception:
        db.rollback()
        minio_storage.remove_object_if_exists(new_key)
        raise
    copied_keys: list[str] = []
    try:
        for attachment in source.attachments:
            payload = minio_storage.get_object_bytes(attachment.object_key)
            if hashlib.sha256(payload).hexdigest() != attachment.sha256:
                raise ValueError(f"附件校验失败: {attachment.original_filename}")
            attachment_key = (
                f"reviews/{source.scheme_type_id}/attachments/{uuid.uuid4().hex}_"
                f"{_safe_attachment_filename(attachment.original_filename)}"
            )
            minio_storage.put_object(
                attachment_key,
                payload,
                length=len(payload),
                content_type=attachment.content_type,
            )
            copied_keys.append(attachment_key)
            copied_attachment = ReviewAttachment(
                    task_id=task.id,
                    kind=attachment.kind,
                    original_filename=attachment.original_filename,
                    content_type=attachment.content_type,
                    minio_bucket=attachment.minio_bucket,
                    object_key=attachment_key,
                    sha256=attachment.sha256,
                    size_bytes=attachment.size_bytes,
                    scan_status=attachment.scan_status,
                )
            db.add(copied_attachment)
            task.attachments.append(copied_attachment)
        db.flush()
        try:
            previous_inputs = json.loads(source.dify_workflow_inputs_snapshot or "{}")
        except json.JSONDecodeError:
            previous_inputs = {}
        refreshed_inputs = canonical_task_inputs(
            task,
            scheme_category=source.scheme_type.category if source.scheme_type else "",
            scheme_name=source.scheme_type.name if source.scheme_type else "",
            project_name=str(previous_inputs.get("project_name") or ""),
            project_region=str(previous_inputs.get("project_region") or ""),
            review_focus=str(previous_inputs.get("review_focus") or ""),
        )
        task.dify_workflow_inputs_snapshot = json.dumps(
            refreshed_inputs,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        ensure_round_for_task(db, task)
        db.commit()
    except Exception:
        db.rollback()
        minio_storage.remove_object_if_exists(new_key)
        for key in copied_keys:
            minio_storage.remove_object_if_exists(key)
        raise
    loaded = (
        db.query(SchemeReviewTask)
        .options(joinedload(SchemeReviewTask.scheme_type), joinedload(SchemeReviewTask.user))
        .filter(SchemeReviewTask.id == task.id)
        .first()
    )
    if loaded is None:
        raise HTTPException(status_code=500, detail="重试任务创建失败")
    return ReviewTaskCreateResponse(
        task=_task_public(loaded, owner_username=loaded.user.username),
        message="重试任务已创建",
    )
