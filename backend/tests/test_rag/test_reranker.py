from app.services.rag.reranker import rerank
from app.services.rag.retriever import RetrievalHit


def test_rerank_orders_by_score() -> None:
    hits = [
        RetrievalHit(chunk_id="a", text="low", score=0.1),
        RetrievalHit(chunk_id="b", text="high", score=0.9),
    ]
    assert rerank("query", hits)[0].chunk_id == "b"
