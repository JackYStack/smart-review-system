import re

PHONE_PATTERN = re.compile(r"1[3-9]\d{9}")


def redact_sensitive_text(text: str) -> str:
    """Redact simple sensitive identifiers from text."""

    return PHONE_PATTERN.sub("[REDACTED_PHONE]", text)
