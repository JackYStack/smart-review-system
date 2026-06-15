from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ReportRequest(BaseModel):
    """Report export request."""

    task_id: str
    format: str = "pdf"


@router.post("/export")
async def export_report(request: ReportRequest) -> dict[str, str]:
    """Return a placeholder report export task."""

    return {
        "task_id": request.task_id,
        "format": request.format,
        "status": "queued",
    }
