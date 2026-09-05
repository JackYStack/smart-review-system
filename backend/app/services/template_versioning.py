from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.scheme_review_task import SchemeReviewTask
from app.models.scheme_template import SchemeTemplate
from app.models.scheme_template_version import SchemeTemplateVersion
from app.services import minio_storage


@dataclass(frozen=True)
class FrozenTemplateConfiguration:
    parsed_structure: str | None
    review_workflow: str | None
    full_document_review_config: str | None


def _canonical_json(raw: str | None) -> Any:
    try:
        return json.loads(raw or "null")
    except (TypeError, json.JSONDecodeError):
        return raw or None


def configuration_sha256(template: SchemeTemplate) -> str:
    payload = {
        "parsed_structure": _canonical_json(template.parsed_structure),
        "review_workflow": _canonical_json(template.review_workflow),
        "full_document_review_config": _canonical_json(
            template.full_document_review_config
        ),
    }
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def latest_template_version(
    db: Session, scheme_type_id: int
) -> SchemeTemplateVersion | None:
    return (
        db.query(SchemeTemplateVersion)
        .filter(SchemeTemplateVersion.scheme_type_id == scheme_type_id)
        .order_by(SchemeTemplateVersion.version.desc())
        .first()
    )


def record_template_version(
    db: Session,
    template: SchemeTemplate,
    *,
    actor_id: int | None,
    content_bytes: bytes | None = None,
) -> SchemeTemplateVersion:
    previous = latest_template_version(db, template.scheme_type_id)
    if content_bytes is not None:
        content_digest = hashlib.sha256(content_bytes).hexdigest()
    elif previous is not None and previous.object_key == template.object_key:
        content_digest = previous.content_sha256
    else:
        content_digest = hashlib.sha256(
            minio_storage.get_object_bytes(template.object_key)
        ).hexdigest()
    maximum = (
        db.query(func.max(SchemeTemplateVersion.version))
        .filter(SchemeTemplateVersion.scheme_type_id == template.scheme_type_id)
        .scalar()
    )
    row = SchemeTemplateVersion(
        scheme_type_id=template.scheme_type_id,
        version=int(maximum or 0) + 1,
        object_key=template.object_key,
        original_filename=template.original_filename,
        content_sha256=content_digest,
        configuration_sha256=configuration_sha256(template),
        parsed_structure=template.parsed_structure,
        review_workflow=template.review_workflow,
        full_document_review_config=template.full_document_review_config,
        created_by_id=actor_id,
    )
    db.add(row)
    db.flush()
    return row


def bind_task_template_snapshot(
    db: Session,
    task: SchemeReviewTask,
    template: SchemeTemplate,
    *,
    actor_id: int | None,
) -> SchemeTemplateVersion:
    version = latest_template_version(db, template.scheme_type_id)
    if version is None or version.configuration_sha256 != configuration_sha256(template):
        version = record_template_version(db, template, actor_id=actor_id)
    task.template_version_id = version.id
    task.template_snapshot_json = json.dumps(
        {
            "schema_version": 1,
            "template_version_id": version.id,
            "template_version": version.version,
            "content_sha256": version.content_sha256,
            "configuration_sha256": version.configuration_sha256,
            "parsed_structure": _canonical_json(version.parsed_structure),
            "review_workflow": _canonical_json(version.review_workflow),
            "full_document_review_config": _canonical_json(
                version.full_document_review_config
            ),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return version


def resolve_task_template_snapshot(
    task: SchemeReviewTask, fallback: SchemeTemplate
) -> FrozenTemplateConfiguration:
    try:
        raw = json.loads(task.template_snapshot_json or "")
    except (TypeError, json.JSONDecodeError):
        raw = None
    if isinstance(raw, dict):
        return FrozenTemplateConfiguration(
            parsed_structure=json.dumps(
                raw.get("parsed_structure"), ensure_ascii=False, separators=(",", ":")
            ),
            review_workflow=json.dumps(
                raw.get("review_workflow"), ensure_ascii=False, separators=(",", ":")
            ),
            full_document_review_config=json.dumps(
                raw.get("full_document_review_config"),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
    return FrozenTemplateConfiguration(
        parsed_structure=fallback.parsed_structure,
        review_workflow=fallback.review_workflow,
        full_document_review_config=fallback.full_document_review_config,
    )
