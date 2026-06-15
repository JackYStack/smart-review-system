from app.core.issue_card import IssueCard
from app.core.review_context import ReviewContext


async def check_applicability(context: ReviewContext) -> list[IssueCard]:
    """Check whether clauses and rules apply to the project scenario."""

    return []
