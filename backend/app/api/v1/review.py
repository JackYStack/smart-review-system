from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.issue_card import IssueCard
from app.core.review_context import ReviewContext
from app.core.review_orchestrator import ReviewOrchestrator

router = APIRouter()


class ReviewRequest(BaseModel):
    """Review task request."""

    document_id: str
    scenario: str
    summary: str = Field(default="")


class ReviewResponse(BaseModel):
    """Review task response."""

    task_id: str
    status: str
    issues: list[IssueCard]


@router.post("", response_model=ReviewResponse)
async def run_review(request: ReviewRequest) -> ReviewResponse:
    """Run the scaffold review pipeline."""

    context = ReviewContext(
        document_id=request.document_id,
        scenario=request.scenario,
        summary=request.summary,
    )
    issues = await ReviewOrchestrator().run(context)
    return ReviewResponse(
        task_id=f"review_{request.document_id}",
        status="completed",
        issues=issues,
    )
