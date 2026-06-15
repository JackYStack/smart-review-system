from app.core.issue_card import IssueCard, Severity


def grade_issue(issue: IssueCard) -> Severity:
    """Return an issue severity."""

    return issue.severity
