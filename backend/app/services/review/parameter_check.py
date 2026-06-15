from app.core.issue_card import IssueCard
from app.core.review_context import ReviewContext


async def check_parameters(context: ReviewContext) -> list[IssueCard]:
    """Check extracted parameters against configured thresholds."""

    return []
