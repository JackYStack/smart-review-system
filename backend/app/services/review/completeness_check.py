from app.core.issue_card import IssueCard
from app.core.review_context import ReviewContext


async def check_completeness(context: ReviewContext) -> list[IssueCard]:
    """Check required chapter completeness."""

    return []
