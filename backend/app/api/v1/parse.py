from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, UploadFile
from pydantic import BaseModel, Field

router = APIRouter()


class ParseTaskResponse(BaseModel):
    """Response returned after a document is accepted for parsing."""

    document_id: str
    file_name: str
    file_type: str
    status: str = Field(default="queued")
    scenario: str | None = None


@router.post("", response_model=ParseTaskResponse)
async def submit_parse_task(
    file: UploadFile | None = None,
    scenario: str | None = None,
) -> ParseTaskResponse:
    """Accept a document parsing task.

    The current scaffold returns a task envelope. Real parsing workers will persist the file,
    route by document type, and emit StructuredDocument JSON.
    """

    file_name = file.filename if file and file.filename else "unknown"
    suffix = Path(file_name).suffix.removeprefix(".").lower() or "unknown"
    return ParseTaskResponse(
        document_id=f"doc_{uuid4().hex[:12]}",
        file_name=file_name,
        file_type=suffix,
        scenario=scenario,
    )


@router.get("/{document_id}")
async def get_parse_result(document_id: str) -> dict[str, str]:
    """Return parse task status."""

    return {"document_id": document_id, "status": "pending"}
