"""Backfill immutable artifact indexes for tasks created before migration 028."""

from __future__ import annotations

import sys
from pathlib import Path

# Make ``python scripts/backfill_document_artifacts.py`` work both in the
# container's /app working directory and from a local backend checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.document_artifact import DocumentArtifact
from app.models.review_governance import ReviewRound
from app.models.scheme_review_task import SchemeReviewTask
from app.services import minio_storage
from app.services.document_artifacts import record_document_artifact


def _exists(db, task_id: int, kind: str, object_key: str) -> bool:
    return (
        db.query(DocumentArtifact.id)
        .filter(
            DocumentArtifact.task_id == task_id,
            DocumentArtifact.artifact_kind == kind,
            DocumentArtifact.object_key == object_key,
        )
        .first()
        is not None
    )


def main() -> int:
    created = 0
    skipped = 0
    with SessionLocal() as db:
        tasks = db.query(SchemeReviewTask).order_by(SchemeReviewTask.id).all()
        for task in tasks:
            candidates: list[tuple[str, str, str, int | None, int | None]] = [
                (
                    "original",
                    task.object_key,
                    task.original_filename or "scheme.docx",
                    None,
                    task.user_id,
                )
            ]
            output_key = (task.output_object_key or "").strip()
            if output_key:
                inferred_kind = (
                    "expert_edit" if "/onlyoffice/" in output_key else "ai_annotated"
                )
                candidates.append(
                    (
                        inferred_kind,
                        output_key,
                        task.original_filename or "review-result.docx",
                        None,
                        None,
                    )
                )
            rounds = db.query(ReviewRound).filter(ReviewRound.task_id == task.id).all()
            for review_round in rounds:
                if review_round.signed_report_object_key:
                    candidates.append(
                        (
                            "signed_report",
                            review_round.signed_report_object_key,
                            f"任务{task.id}_正式签发报告.docx",
                            review_round.id,
                            review_round.signed_by_id,
                        )
                    )
            for kind, object_key, filename, round_id, actor_id in candidates:
                if not object_key or _exists(db, task.id, kind, object_key):
                    skipped += 1
                    continue
                try:
                    content = minio_storage.get_object_bytes(object_key)
                    record_document_artifact(
                        db,
                        task_id=task.id,
                        review_round_id=round_id,
                        artifact_kind=kind,
                        object_key=object_key,
                        content=content,
                        minio_bucket=task.minio_bucket,
                        original_filename=filename,
                        created_by_id=actor_id,
                    )
                    db.commit()
                    created += 1
                except Exception as exc:
                    db.rollback()
                    skipped += 1
                    print(f"SKIP task={task.id} kind={kind} key={object_key}: {exc!s}")
    print(f"Artifact backfill complete: created={created}, skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
