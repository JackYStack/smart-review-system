from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models.scheme_review_task import SchemeReviewTask
from app.models.scheme_workflow_profile import SchemeDifyWorkflowProfile
from app.schemas.scheme_workflow_profile import (
    DEFAULT_INPUT_MAPPING,
    SchemeWorkflowProfilePublic,
    SchemeWorkflowProfileUpdate,
    validate_input_mapping,
)
from app.services.integration_settings import resolve_workflow_integration
from app.services.secret_store import decrypt_secret, encrypt_secret


ProfileSource = Literal["scheme_profile", "global"]


@dataclass(frozen=True)
class EffectiveSchemeWorkflowProfile:
    profile_id: int | None
    version: int | None
    source: ProfileSource
    enabled: bool
    base_url: str
    api_key: str
    user_prefix: str
    timeout_seconds: int
    output_variable: str
    output_format: str
    accept_partial: bool
    continue_on_failure: bool
    input_mapping: dict[str, str]


@dataclass(frozen=True)
class TaskWorkflowSnapshot:
    config: EffectiveSchemeWorkflowProfile
    inputs: dict[str, Any]


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _parse_mapping(value: str | None) -> dict[str, str]:
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        parsed = {}
    if not isinstance(parsed, dict) or not parsed:
        return dict(DEFAULT_INPUT_MAPPING)
    try:
        return validate_input_mapping(
            {str(key): str(target) for key, target in parsed.items()}
        )
    except ValueError:
        return dict(DEFAULT_INPUT_MAPPING)


def get_scheme_workflow_profile(
    db: Session, scheme_type_id: int
) -> SchemeDifyWorkflowProfile | None:
    return (
        db.query(SchemeDifyWorkflowProfile)
        .filter(SchemeDifyWorkflowProfile.scheme_type_id == scheme_type_id)
        .first()
    )


def resolve_scheme_workflow_profile(
    db: Session, scheme_type_id: int
) -> EffectiveSchemeWorkflowProfile:
    row = get_scheme_workflow_profile(db, scheme_type_id)
    if row is not None:
        return EffectiveSchemeWorkflowProfile(
            profile_id=row.id,
            version=row.version,
            source="scheme_profile",
            enabled=bool(row.enabled),
            base_url=(row.base_url or "").strip().rstrip("/"),
            api_key=decrypt_secret(row.api_key),
            user_prefix=(row.user_prefix or "smart-review").strip() or "smart-review",
            timeout_seconds=max(30, int(row.timeout_seconds or 900)),
            output_variable=(row.output_variable or "report").strip() or "report",
            output_format=(row.output_format or "json").strip() or "json",
            accept_partial=bool(row.accept_partial),
            continue_on_failure=bool(row.continue_on_failure),
            input_mapping=_parse_mapping(row.input_mapping),
        )

    global_cfg = resolve_workflow_integration(db)
    return EffectiveSchemeWorkflowProfile(
        profile_id=None,
        version=None,
        source="global",
        enabled=global_cfg.enabled,
        base_url=global_cfg.base_url,
        api_key=global_cfg.api_key,
        user_prefix=global_cfg.user_prefix,
        timeout_seconds=global_cfg.timeout_seconds,
        output_variable=global_cfg.output_variable,
        output_format=global_cfg.output_format,
        accept_partial=global_cfg.accept_partial,
        continue_on_failure=global_cfg.continue_on_failure,
        input_mapping=dict(DEFAULT_INPUT_MAPPING),
    )


def workflow_profile_public(
    scheme_type_id: int, config: EffectiveSchemeWorkflowProfile
) -> SchemeWorkflowProfilePublic:
    return SchemeWorkflowProfilePublic(
        scheme_type_id=scheme_type_id,
        profile_id=config.profile_id,
        version=config.version,
        configured=config.source == "scheme_profile",
        source=config.source,
        enabled=config.enabled,
        base_url=config.base_url,
        api_key_configured=bool(config.api_key),
        user_prefix=config.user_prefix,
        timeout_seconds=config.timeout_seconds,
        output_variable=config.output_variable,
        output_format=config.output_format,  # type: ignore[arg-type]
        accept_partial=config.accept_partial,
        continue_on_failure=config.continue_on_failure,
        input_mapping=config.input_mapping,
    )


def upsert_scheme_workflow_profile(
    db: Session,
    scheme_type_id: int,
    body: SchemeWorkflowProfileUpdate,
) -> SchemeDifyWorkflowProfile:
    row = get_scheme_workflow_profile(db, scheme_type_id)
    if row is None:
        row = SchemeDifyWorkflowProfile(scheme_type_id=scheme_type_id, version=1)
        db.add(row)
    else:
        row.version = int(row.version or 0) + 1

    row.enabled = body.enabled
    row.base_url = body.base_url.rstrip("/")
    row.user_prefix = body.user_prefix or "smart-review"
    row.timeout_seconds = body.timeout_seconds
    row.output_variable = body.output_variable
    row.output_format = body.output_format
    row.accept_partial = body.accept_partial
    row.continue_on_failure = body.continue_on_failure
    row.input_mapping = _json(body.input_mapping)
    if body.clear_api_key:
        row.api_key = None
    elif body.api_key is not None and body.api_key.strip():
        row.api_key = encrypt_secret(body.api_key)

    if row.enabled and (not row.base_url or not decrypt_secret(row.api_key)):
        raise ValueError("启用类型 Workflow 时必须配置 base_url 和 API key")
    db.flush()
    return row


def canonical_task_inputs(
    task: SchemeReviewTask,
    *,
    scheme_category: str,
    scheme_name: str,
    project_name: str = "",
    project_region: str = "",
    review_focus: str = "",
) -> dict[str, Any]:
    filename_stem = re.sub(r"\.[^.]+$", "", task.original_filename or "").strip()
    resolved_project_name = project_name.strip() or filename_stem or f"审查任务-{task.id or 'pending'}"
    resolved_focus = review_focus.strip() or (
        "对危大工程专项施工方案进行全文审查，重点识别强制性条文违反、关键参数矛盾、"
        "缺项漏项、计算与措施不一致及不可执行的安全措施。"
    )
    supporting = [
        {
            "file_name": attachment.original_filename,
            "object_key": attachment.object_key,
            "content_type": attachment.content_type,
        }
        for attachment in (task.attachments or [])
        if attachment.kind == "supporting_document"
    ]
    site_images = [
        {
            "file_name": attachment.original_filename,
            "object_key": attachment.object_key,
            "content_type": attachment.content_type,
        }
        for attachment in (task.attachments or [])
        if attachment.kind == "site_image"
    ]
    return {
        "documents": [
            {
                "file_name": task.original_filename,
                "object_key": task.object_key,
                "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            },
            *supporting,
        ],
        "site_images": site_images,
        "project_name": resolved_project_name,
        "project_region": project_region.strip(),
        "risk_type": " / ".join(
            item for item in (scheme_category.strip(), scheme_name.strip()) if item
        ),
        "review_focus": resolved_focus,
    }


def snapshot_task_workflow(
    db: Session,
    task: SchemeReviewTask,
    *,
    scheme_category: str,
    scheme_name: str,
    project_name: str = "",
    project_region: str = "",
    review_focus: str = "",
) -> TaskWorkflowSnapshot:
    config = resolve_scheme_workflow_profile(db, task.scheme_type_id)
    inputs = canonical_task_inputs(
        task,
        scheme_category=scheme_category,
        scheme_name=scheme_name,
        project_name=project_name,
        project_region=project_region,
        review_focus=review_focus,
    )
    config_payload = {
        "schema_version": 1,
        "source": config.source,
        "enabled": config.enabled,
        "base_url": config.base_url,
        # Snapshot the credential for reproducibility, but never store plaintext.
        "api_key_ciphertext": encrypt_secret(config.api_key),
        "user_prefix": config.user_prefix,
        "timeout_seconds": config.timeout_seconds,
        "output_variable": config.output_variable,
        "output_format": config.output_format,
        "accept_partial": config.accept_partial,
        "continue_on_failure": config.continue_on_failure,
        "input_mapping": config.input_mapping,
    }
    task.dify_workflow_profile_id = config.profile_id
    task.dify_workflow_profile_version = config.version
    task.dify_workflow_inputs_snapshot = _json(inputs)
    task.dify_workflow_config_snapshot = _json(config_payload)
    return TaskWorkflowSnapshot(config=config, inputs=inputs)


def resolve_task_workflow_snapshot(
    db: Session,
    task: SchemeReviewTask,
    *,
    scheme_category: str,
    scheme_name: str,
) -> TaskWorkflowSnapshot:
    try:
        raw_config = json.loads(task.dify_workflow_config_snapshot or "")
        raw_inputs = json.loads(task.dify_workflow_inputs_snapshot or "")
    except (TypeError, json.JSONDecodeError):
        raw_config = raw_inputs = None

    if isinstance(raw_config, dict) and isinstance(raw_inputs, dict):
        mapping_raw = raw_config.get("input_mapping")
        mapping = (
            _parse_mapping(_json(mapping_raw))
            if isinstance(mapping_raw, dict)
            else dict(DEFAULT_INPUT_MAPPING)
        )
        source = str(raw_config.get("source") or "global")
        if source not in {"scheme_profile", "global"}:
            source = "global"
        config = EffectiveSchemeWorkflowProfile(
            profile_id=task.dify_workflow_profile_id,
            version=task.dify_workflow_profile_version,
            source=source,  # type: ignore[arg-type]
            enabled=bool(raw_config.get("enabled")),
            base_url=str(raw_config.get("base_url") or "").strip().rstrip("/"),
            api_key=decrypt_secret(str(raw_config.get("api_key_ciphertext") or "")),
            user_prefix=str(raw_config.get("user_prefix") or "smart-review").strip()
            or "smart-review",
            timeout_seconds=max(30, int(raw_config.get("timeout_seconds") or 900)),
            output_variable=str(raw_config.get("output_variable") or "report").strip()
            or "report",
            output_format=str(raw_config.get("output_format") or "json").strip() or "json",
            accept_partial=bool(raw_config.get("accept_partial", True)),
            continue_on_failure=bool(raw_config.get("continue_on_failure", True)),
            input_mapping=mapping,
        )
        return TaskWorkflowSnapshot(config=config, inputs=raw_inputs)

    # Compatibility for tasks created before workflow snapshots were introduced.
    config = resolve_scheme_workflow_profile(db, task.scheme_type_id)
    inputs = canonical_task_inputs(
        task,
        scheme_category=scheme_category,
        scheme_name=scheme_name,
    )
    return TaskWorkflowSnapshot(config=config, inputs=inputs)
