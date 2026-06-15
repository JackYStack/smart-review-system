from pydantic import BaseModel, Field


class SealEntity(BaseModel):
    """Structured seal and signature recognition result."""

    seal_id: str
    organization_name: str | None = None
    ocr_text: str | None = None
    ocr_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    page_number: int | None = None
    has_signature: bool = False


def detect_seals_placeholder() -> list[SealEntity]:
    """Return placeholder seal detection output."""

    return []
