from app.services.rules.rule_engine import evaluate_threshold


def test_evaluate_threshold_flags_reached_value() -> None:
    result = evaluate_threshold(value=24, threshold=24, rule_id="scaffold-height")
    assert result.passed is False
