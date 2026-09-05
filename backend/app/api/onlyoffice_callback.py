import logging
import hmac
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.scheme_review_task import ReviewTaskStatus, SchemeReviewTask
from app.models.document_artifact import OnlyofficeEditSession
from app.models.review_governance import ReviewRound
from app.schemas.onlyoffice_editor import OnlyofficeCallbackPayload
from app.services import minio_storage
from app.services.onlyoffice import (
    extract_bearer_token,
    pull_callback_file,
    verify_callback_token,
)
from app.services.onlyoffice_settings import get_effective_onlyoffice
from app.services.document_artifacts import record_document_artifact

router = APIRouter(tags=["onlyoffice"])
logger = logging.getLogger(__name__)


@router.post("/onlyoffice/callback")
async def onlyoffice_callback(
    payload: OnlyofficeCallbackPayload,
    task_id: int = Query(...),
    session_id: int = Query(...),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> dict:
    logger.info(
        "onlyoffice callback received: task_id=%s status=%s has_url=%s key=%s",
        task_id,
        payload.status,
        bool(payload.url),
        payload.key,
    )
    eff = get_effective_onlyoffice(db)
    if not eff.jwt_secret or not eff.docs_url:
        raise HTTPException(status_code=503, detail="OnlyOffice JWT 或 Document Server 地址未配置")
    try:
        token = extract_bearer_token(authorization)
        verify_callback_token(
            token,
            eff.jwt_secret,
            key=payload.key,
            status=payload.status,
            url=payload.url,
        )
    except ValueError as exc:
        logger.warning("onlyoffice callback authentication failed: task_id=%s", task_id)
        raise HTTPException(status_code=401, detail="OnlyOffice 回调签名无效") from exc

    t = db.get(SchemeReviewTask, task_id)
    if t is None:
        logger.warning("onlyoffice callback task not found: task_id=%s", task_id)
        return {"error": 1, "message": "task not found"}
    if t.status != ReviewTaskStatus.succeeded:
        logger.warning("onlyoffice callback task is not successful: task_id=%s", task_id)
        return {"error": 1, "message": "task is not editable"}
    if not (t.output_object_key or "").strip():
        logger.warning("onlyoffice callback no output object key: task_id=%s", task_id)
        return {"error": 1, "message": "no output"}
    review_round = (
        db.query(ReviewRound)
        .filter(ReviewRound.task_id == t.id)
        .order_by(ReviewRound.id.desc())
        .first()
    )
    if review_round is not None and review_round.status == "signed":
        logger.warning("onlyoffice callback rejected for signed task: task_id=%s", task_id)
        raise HTTPException(status_code=409, detail="已签发文档禁止覆盖或继续编辑")
    edit_session = db.get(OnlyofficeEditSession, session_id)
    if edit_session is None or edit_session.task_id != t.id:
        raise HTTPException(status_code=403, detail="OnlyOffice 编辑会话与任务不匹配")
    expires_at = edit_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if edit_session.closed_at is not None or expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=403, detail="OnlyOffice 编辑会话已关闭或过期")
    if not hmac.compare_digest(payload.key, edit_session.document_key):
        logger.warning("onlyoffice callback document key mismatch: task_id=%s", task_id)
        raise HTTPException(status_code=403, detail="文档 key 与任务不匹配")
    if not hmac.compare_digest(
        (t.output_object_key or "").strip(),
        edit_session.current_object_key,
    ):
        raise HTTPException(status_code=409, detail="文档版本已被其他会话更新，请重新打开后编辑")

    if payload.status not in {2, 6} or not payload.url:
        if payload.status == 4:
            edit_session.closed_at = datetime.now(UTC)
            db.commit()
        logger.info(
            "onlyoffice callback ignored: task_id=%s status=%s has_url=%s",
            task_id,
            payload.status,
            bool(payload.url),
        )
        return {"error": 0}

    try:
        content = await pull_callback_file(payload.url, eff.docs_url)
    except Exception:
        logger.exception("onlyoffice callback download failed: task_id=%s", task_id)
        return {"error": 1, "message": "download failed"}

    saved_at = datetime.now(UTC)
    key = (
        f"reviews/{t.scheme_type_id}/onlyoffice/{t.id}/"
        f"{saved_at:%Y%m%dT%H%M%S%fZ}_{uuid.uuid4().hex}.docx"
    )
    try:
        minio_storage.put_object(
            key,
            content,
            length=len(content),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except Exception:
        logger.exception("onlyoffice callback storage failed: task_id=%s key=%s", task_id, key)
        return {"error": 1, "message": "storage failed"}

    try:
        t.output_object_key = key
        t.updated_at = saved_at
        edit_session.current_object_key = key
        if payload.status == 2:
            edit_session.closed_at = saved_at
        record_document_artifact(
            db,
            task_id=t.id,
            review_round_id=review_round.id if review_round is not None else None,
            artifact_kind="expert_edit",
            object_key=key,
            content=content,
            minio_bucket=t.minio_bucket,
            original_filename=(t.original_filename or "document.docx").replace(
                ".docx", "_专家修改版.docx"
            ),
            created_by_id=(
                review_round.assigned_expert_id if review_round is not None else None
            ),
        )
        db.add(t)
        db.commit()
    except Exception:
        db.rollback()
        minio_storage.remove_object_if_exists(key)
        logger.exception("onlyoffice callback database persist failed: task_id=%s", task_id)
        return {"error": 1, "message": "database persist failed"}
    logger.info("onlyoffice callback persisted: task_id=%s key=%s bytes=%s", task_id, key, len(content))
    return {"error": 0}
