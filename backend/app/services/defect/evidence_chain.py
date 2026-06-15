from app.core.issue_card import EvidenceChain


def has_complete_evidence(evidence: EvidenceChain) -> bool:
    """Check whether an evidence chain is sufficient for automatic output."""

    return bool(evidence.scheme_text and evidence.clause_text)
