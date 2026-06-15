from pydantic import BaseModel, Field


class ReviewContext(BaseModel):
    """Input context shared by review modules."""

    document_id: str
    scenario: str
    summary: str = ""
    extracted_parameters: dict[str, str] = Field(default_factory=dict)
    kb_version: str = "v0.1"
    rule_version: str = "v0.1"
    prompt_version: str = "v0.1"
