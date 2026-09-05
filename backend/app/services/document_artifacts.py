from __future__ import annotations

import hashlib

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.document_artifact import DocumentArtifact


DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ARTIFACT_KINDS = {"original", "ai_annotated", "expert_edit", "signed_report"}


def record_document_artifact(
    db: Session,
    *,
    task_id: int,
    artifact_kind: str,
    object_key: str,
    content: bytes,
    minio_bucket: str,
    original_filename: str,
    review_round_id: int | None = None,
    created_by_id: int | None = None,
    immutable: bool = True,
) -> DocumentArtifact:
    if artifact_kind not in ARTIFACT_KINDS:
        raise ValueError(f"未知文档成果类型: {artifact_kind}")
    previous = (
        db.query(DocumentArtifact)
        .filter(
            DocumentArtifact.task_id == task_id,
            DocumentArtifact.artifact_kind == artifact_kind,
        )
        .order_by(DocumentArtifact.version_no.desc())
        .first()
    )
    latest_version = int(previous.version_no) if previous is not None else int(
        db.query(func.max(DocumentArtifact.version_no))
        .filter(
            DocumentArtifact.task_id == task_id,
            DocumentArtifact.artifact_kind == artifact_kind,
        )
        .scalar()
        or 0
    )
    row = DocumentArtifact(
        task_id=task_id,
        review_round_id=review_round_id,
        artifact_kind=artifact_kind,
        version_no=latest_version + 1,
        original_filename=original_filename,
        minio_bucket=minio_bucket,
        object_key=object_key,
        sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
        content_type=DOCX_CONTENT_TYPE,
        immutable=immutable,
        supersedes_artifact_id=previous.id if previous is not None else None,
        created_by_id=created_by_id,
    )
    db.add(row)
    db.flush()
    return row


def latest_document_artifact(
    db: Session,
    task_id: int,
    artifact_kind: str,
) -> DocumentArtifact | None:
    return (
        db.query(DocumentArtifact)
        .filter(
            DocumentArtifact.task_id == task_id,
            DocumentArtifact.artifact_kind == artifact_kind,
        )
        .order_by(DocumentArtifact.version_no.desc())
        .first()
    )
