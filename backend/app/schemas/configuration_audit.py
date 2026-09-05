from datetime import datetime

from pydantic import BaseModel


class ConfigurationAuditPublic(BaseModel):
    id: int
    section: str
    action: str
    actor_username: str
    changed_fields: list[str]
    created_at: datetime | None
    can_rollback: bool = True


class ConfigurationHistoryPublic(BaseModel):
    items: list[ConfigurationAuditPublic]

