from pydantic import BaseModel


class RuleResult(BaseModel):
    """Rule evaluation result."""

    rule_id: str
    passed: bool
    message: str


def evaluate_threshold(value: float, threshold: float, rule_id: str) -> RuleResult:
    """Evaluate a numeric threshold rule."""

    passed = value < threshold
    message = "passed" if passed else f"value {value} reaches threshold {threshold}"
    return RuleResult(rule_id=rule_id, passed=passed, message=message)
