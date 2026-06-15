import pytest

from app.core.review_context import ReviewContext
from app.core.review_orchestrator import ReviewOrchestrator


@pytest.mark.asyncio
async def test_scaffold_landed_missing_height_requires_review() -> None:
    context = ReviewContext(document_id="doc_1", scenario="scaffold_landed", summary="方案摘要")
    issues = await ReviewOrchestrator().run(context)
    assert issues
    assert issues[0].needs_human_review is True
