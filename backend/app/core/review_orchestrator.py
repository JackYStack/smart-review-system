from app.core.issue_card import EvidenceChain, IssueCard
from app.core.review_context import ReviewContext


class ReviewOrchestrator:
    """Coordinate the five-dimensional review chain."""

    async def run(self, context: ReviewContext) -> list[IssueCard]:
        """Run a minimal placeholder review pipeline."""

        issues: list[IssueCard] = []
        if context.scenario == "scaffold_landed" and "搭设高度" not in context.summary:
            issues.append(
                IssueCard(
                    issue_id=f"{context.document_id}-missing-height",
                    title="缺少脚手架搭设高度信息",
                    description="落地式钢管脚手架审查需要明确搭设高度，用于判断是否触发危大工程阈值。",
                    source_module="parameter",
                    severity="B",
                    evidence_chain=EvidenceChain(scheme_text=context.summary or "未提供方案摘要"),
                    confidence=0.65,
                    needs_human_review=True,
                )
            )
        return issues
