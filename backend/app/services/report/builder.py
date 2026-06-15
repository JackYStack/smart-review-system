from app.core.issue_card import IssueCard


def build_markdown_report(task_id: str, issues: list[IssueCard]) -> str:
    """Build a simple Markdown review report."""

    lines = [f"# 审查报告 {task_id}", ""]
    if not issues:
        lines.append("未发现自动审查问题。")
    for issue in issues:
        lines.extend(
            [
                f"## {issue.title}",
                f"- 严重性：{issue.severity}",
                f"- 说明：{issue.description}",
                f"- 需人工复核：{issue.needs_human_review}",
                "",
            ]
        )
    return "\n".join(lines)
