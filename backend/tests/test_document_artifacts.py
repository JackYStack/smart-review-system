from __future__ import annotations

import hashlib
from unittest.mock import MagicMock

from app.models.document_artifact import DocumentArtifact
from app.services.document_artifacts import record_document_artifact


def test_document_artifact_records_hash_and_next_version() -> None:
    previous = DocumentArtifact(
        id=8,
        task_id=3,
        artifact_kind="expert_edit",
        version_no=2,
        original_filename="专家修改版V2.docx",
        minio_bucket="review",
        object_key="reviews/expert-v2.docx",
        sha256="0" * 64,
        size_bytes=10,
        content_type="application/test",
        immutable=True,
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = previous
    content = b"immutable-version-three"

    row = record_document_artifact(
        db,
        task_id=3,
        artifact_kind="expert_edit",
        object_key="reviews/expert-v3.docx",
        content=content,
        minio_bucket="review",
        original_filename="专家修改版V3.docx",
        review_round_id=5,
        created_by_id=7,
    )

    assert row.version_no == 3
    assert row.supersedes_artifact_id == previous.id
    assert row.sha256 == hashlib.sha256(content).hexdigest()
    assert row.size_bytes == len(content)
    assert row.immutable is True
    db.add.assert_called_once_with(row)
    db.flush.assert_called_once_with()
