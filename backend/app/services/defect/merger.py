from app.core.issue_card import IssueCard


def merge_duplicate_issues(issues: list[IssueCard]) -> list[IssueCard]:
    """Merge duplicate issues by title."""

    seen: set[str] = set()
    merged: list[IssueCard] = []
    for issue in issues:
        if issue.title in seen:
            continue
        seen.add(issue.title)
        merged.append(issue)
    return merged
