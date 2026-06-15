from pydantic import BaseModel


class RetrievalHit(BaseModel):
    """One knowledge retrieval hit."""

    chunk_id: str
    text: str
    score: float
    source: str | None = None


async def retrieve(query: str, top_k: int = 5) -> list[RetrievalHit]:
    """Retrieve relevant knowledge chunks."""

    _ = (query, top_k)
    return []
