from __future__ import annotations

import shutil
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models.integration_settings import IntegrationSettings
from app.services.secret_store import decrypt_secret


@dataclass(frozen=True)
class EffectiveWorkflowIntegration:
    enabled: bool
    base_url: str
    api_key: str
    user_prefix: str
    timeout_seconds: int
    output_variable: str
    output_format: str
    accept_partial: bool
    continue_on_failure: bool
    source: str


@dataclass(frozen=True)
class EffectiveDocumentIntegration:
    paddleocr_api_url: str
    paddleocr_api_key: str
    paddleocr_timeout_seconds: float
    convert_timeout_seconds: float
    libreoffice_bin: str
    source: str


def get_or_create_integration_settings(db: Session) -> IntegrationSettings:
    row = db.query(IntegrationSettings).order_by(IntegrationSettings.id).first()
    if row is None:
        row = IntegrationSettings()
        db.add(row)
        db.flush()
    return row


def _pick(row_value, env_value):
    return row_value if row_value is not None else env_value


def _source(*values) -> str:
    return "database" if any(value is not None for value in values) else "environment"


def resolve_workflow_integration(
    db: Session, settings: Settings | None = None
) -> EffectiveWorkflowIntegration:
    env = settings or get_settings()
    row = db.query(IntegrationSettings).order_by(IntegrationSettings.id).first()
    if row is None:
        return EffectiveWorkflowIntegration(
            enabled=bool(env.dify_workflow_enabled),
            base_url=env.dify_workflow_base_url.strip(),
            api_key=env.dify_workflow_api_key.strip(),
            user_prefix=env.dify_workflow_user_prefix.strip() or "smart-review",
            timeout_seconds=int(env.dify_workflow_timeout_seconds),
            output_variable="report",
            output_format="auto",
            accept_partial=True,
            continue_on_failure=True,
            source="environment",
        )
    tracked = (
        row.dify_workflow_enabled,
        row.dify_workflow_base_url,
        row.dify_workflow_api_key,
        row.dify_workflow_user_prefix,
        row.dify_workflow_timeout_seconds,
        row.dify_workflow_output_variable,
        row.dify_workflow_output_format,
        row.dify_workflow_accept_partial,
        row.dify_workflow_continue_on_failure,
    )
    return EffectiveWorkflowIntegration(
        enabled=bool(_pick(row.dify_workflow_enabled, env.dify_workflow_enabled)),
        base_url=str(_pick(row.dify_workflow_base_url, env.dify_workflow_base_url) or "").strip(),
        api_key=(
            decrypt_secret(row.dify_workflow_api_key, env)
            if row.dify_workflow_api_key is not None
            else env.dify_workflow_api_key.strip()
        ),
        user_prefix=str(
            _pick(row.dify_workflow_user_prefix, env.dify_workflow_user_prefix) or "smart-review"
        ).strip(),
        timeout_seconds=int(
            _pick(row.dify_workflow_timeout_seconds, env.dify_workflow_timeout_seconds)
        ),
        output_variable=str(_pick(row.dify_workflow_output_variable, "report") or "report").strip(),
        output_format=str(_pick(row.dify_workflow_output_format, "auto") or "auto").strip(),
        accept_partial=bool(_pick(row.dify_workflow_accept_partial, True)),
        continue_on_failure=bool(_pick(row.dify_workflow_continue_on_failure, True)),
        source=_source(*tracked),
    )


def resolve_document_integration(
    db: Session, settings: Settings | None = None
) -> EffectiveDocumentIntegration:
    env = settings or get_settings()
    row = db.query(IntegrationSettings).order_by(IntegrationSettings.id).first()
    if row is None:
        row_url = row_key = row_timeout = row_convert = None
    else:
        row_url = row.paddleocr_api_url
        row_key = row.paddleocr_api_key
        row_timeout = row.paddleocr_timeout_seconds
        row_convert = row.paddle_convert_timeout_seconds
    configured_bin = env.libreoffice_bin.strip()
    executable = configured_bin or shutil.which("soffice") or shutil.which("libreoffice") or ""
    return EffectiveDocumentIntegration(
        paddleocr_api_url=str(_pick(row_url, env.paddleocr_api_url) or "").strip(),
        paddleocr_api_key=(
            decrypt_secret(row_key, env) if row_key is not None else env.paddleocr_api_key.strip()
        ),
        paddleocr_timeout_seconds=float(_pick(row_timeout, env.paddleocr_timeout_seconds)),
        convert_timeout_seconds=float(_pick(row_convert, env.paddle_convert_timeout_seconds)),
        libreoffice_bin=executable,
        source=_source(row_url, row_key, row_timeout, row_convert),
    )
