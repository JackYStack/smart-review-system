from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class KnowledgeQuery(BaseModel):
    """Knowledge base query request."""

    query: str
    top_k: int = 5


@router.post("/search")
async def search_knowledge_base(request: KnowledgeQuery) -> dict[str, object]:
    """Return placeholder retrieval results."""

    return {"query": request.query, "top_k": request.top_k, "results": []}


@router.get("/versions")
async def list_knowledge_versions() -> dict[str, list[str]]:
    """List available knowledge base versions."""

    return {"versions": ["v0.1"]}
