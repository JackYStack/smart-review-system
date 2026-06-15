from decimal import Decimal


def compare_ratio(design_value: Decimal, allowed_value: Decimal) -> bool:
    """Return whether the design value is within the allowed value."""

    return design_value <= allowed_value
