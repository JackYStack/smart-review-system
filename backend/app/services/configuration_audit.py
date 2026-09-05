from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.configuration_audit import ConfigurationAudit
from app.models.integration_settings import IntegrationSettings
from app.models.user import User

INTEGRATION_FIELDS = (
    "dify_workflow_enabled",
    "dify_workflow_base_url",
    "dify_workflow_api_key",
    "dify_workflow_user_prefix",
    "dify_workflow_timeout_seconds",
    "dify_workflow_output_variable",
    "dify_workflow_output_format",
    "dify_workflow_accept_partial",
    "dify_workflow_continue_on_failure",
    "paddleocr_api_url",
    "paddleocr_api_key",
    "paddleocr_timeout_seconds",
    "paddle_convert_timeout_seconds",
)


def integration_snapshot(row: IntegrationSettings) -> dict[str, Any]:
    return {name: getattr(row, name) for name in INTEGRATION_FIELDS}


def changed_fields(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    return [name for name in INTEGRATION_FIELDS if before.get(name) != after.get(name)]


def apply_integration_snapshot(row: IntegrationSettings, snapshot: dict[str, Any]) -> None:
    for name in INTEGRATION_FIELDS:
        if name in snapshot:
            setattr(row, name, snapshot[name])


def record_integration_audit(
    db: Session,
    *,
    user: User,
    action: str,
    before: dict[str, Any],
    after: dict[str, Any],
) -> ConfigurationAudit:
    audit = ConfigurationAudit(
        section="integrations",
        action=action,
        actor_user_id=user.id,
        actor_username=user.username,
        changed_fields_json=json.dumps(changed_fields(before, after), ensure_ascii=False),
        rollback_snapshot_json=json.dumps(before, ensure_ascii=False),
    )
    db.add(audit)
    return audit

