from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)
PREFIX = "enc:v1:"


def _fernet(settings: Settings | None = None) -> Fernet:
    cfg = settings or get_settings()
    material = (cfg.settings_encryption_key or "").strip() or cfg.jwt_secret
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str | None, settings: Settings | None = None) -> str:
    plain = (value or "").strip()
    if not plain:
        return ""
    if plain.startswith(PREFIX):
        return plain
    token = _fernet(settings).encrypt(plain.encode("utf-8")).decode("ascii")
    return f"{PREFIX}{token}"


def decrypt_secret(value: str | None, settings: Settings | None = None) -> str:
    stored = (value or "").strip()
    if not stored:
        return ""
    if not stored.startswith(PREFIX):
        # Backward compatibility for rows saved before encryption was introduced.
        return stored
    try:
        return _fernet(settings).decrypt(stored[len(PREFIX) :].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError):
        logger.error("A stored settings secret could not be decrypted")
        return ""


def is_encrypted(value: str | None) -> bool:
    return bool(value and value.startswith(PREFIX))


def encrypt_legacy_database_secrets(db) -> int:
    """Encrypt plaintext rows written by releases before settings encryption."""

    from app.models.integration_settings import IntegrationSettings
    from app.models.knowledge_base_settings import KnowledgeBaseSettings
    from app.models.model_provider_settings import ModelProviderSettings
    from app.models.onlyoffice_settings import OnlyofficeSettings

    changed = 0
    targets = (
        (db.query(IntegrationSettings).first(), ("dify_workflow_api_key", "paddleocr_api_key")),
        (db.query(KnowledgeBaseSettings).first(), ("dify_api_key",)),
        (
            db.query(ModelProviderSettings).first(),
            ("volcengine_api_key", "minimax_api_key", "deepseek_api_key"),
        ),
        (db.query(OnlyofficeSettings).first(), ("jwt_secret",)),
    )
    for row, fields in targets:
        if row is None:
            continue
        for field in fields:
            value = getattr(row, field, None)
            if value and not is_encrypted(value):
                setattr(row, field, encrypt_secret(value))
                changed += 1
    if changed:
        db.commit()
    return changed
