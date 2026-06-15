from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ExpertDecision(BaseModel):
    """Expert review decision."""

    issue_id: str
    verdict: str
    comment: str | None = None


@router.get("/queue")
async def get_expert_queue() -> dict[str, list[dict[str, str]]]:
    """Return issues waiting for expert review."""

    return {"items": []}


@router.post("/decision")
async def submit_expert_decision(decision: ExpertDecision) -> dict[str, str]:
    """Persist an expert decision."""

    return {"issue_id": decision.issue_id, "status": "recorded"}
