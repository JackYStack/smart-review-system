from typing import Literal

from pydantic import BaseModel, Field

SourceModule = Literal[
    "parse",
    "procedure",
    "completeness",
    "applicability",
    "parameter",
    "calculation",
    "rag",
    "llm",
]
Severity = Literal["A", "B", "C"]


class EvidenceChain(BaseModel):
    """Traceable evidence for one review issue."""

    scheme_text: str
    page_number: int | None = None
    clause_id: str | None = None
    clause_text: str | None = None
    source_file: str | None = None


class IssueCard(BaseModel):
    """Structured review issue card."""

    issue_id: str
    title: str
    description: str
    source_module: SourceModule
    severity: Severity
    evidence_chain: EvidenceChain
    confidence: float = Field(ge=0.0, le=1.0)
    needs_human_review: bool = False
