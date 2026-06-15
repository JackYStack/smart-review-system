import re
from decimal import Decimal


def parse_metric_number(raw: str) -> Decimal | None:
    """Extract the first decimal number from a text value."""

    match = re.search(r"-?\d+(?:\.\d+)?", raw)
    if not match:
        return None
    return Decimal(match.group(0))
