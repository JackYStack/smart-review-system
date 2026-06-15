from app.services.rag.retriever import RetrievalHit


def rerank(query: str, hits: list[RetrievalHit]) -> list[RetrievalHit]:
    """Rerank retrieval hits."""

    _ = query
    return sorted(hits, key=lambda hit: hit.score, reverse=True)
