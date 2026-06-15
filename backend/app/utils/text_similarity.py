from difflib import SequenceMatcher


def similarity(left: str, right: str) -> float:
    """Return a normalized text similarity ratio."""

    return SequenceMatcher(a=left, b=right).ratio()
