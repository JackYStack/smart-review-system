from pydantic import BaseModel


class EmbeddingRequest(BaseModel):
    """Embedding request."""

    text: str
    model: str = "bge-m3"


def normalize_for_embedding(text: str) -> str:
    """Normalize text before embedding."""

    return " ".join(text.split())
