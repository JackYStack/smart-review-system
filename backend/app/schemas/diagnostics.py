from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DiagnosticReportPublic(BaseModel):
    generated_at: datetime
    system: dict[str, Any]
    deployment: dict[str, Any]
    integrations: dict[str, Any]
    review_runtime: dict[str, Any]
    services: list[dict[str, Any]]

