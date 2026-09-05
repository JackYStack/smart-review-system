from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.services.rule_engine import (
    _parameter_evidence,
    RuleExecutionError,
    compare_values,
    convert_value,
    normalize_value,
    safe_evaluate,
)
from app.models.rule_engine import ParameterValue
from app.schemas.rule_engine import FormulaDefinitionCreate, RuleDefinitionCreate


def test_unit_normalization_and_conversion() -> None:
    value, unit = normalize_value(2400, "mm")
    assert value == Decimal("2.400")
    assert unit == "m"
    assert convert_value(2.4, "m", "mm") == Decimal("2.4") / Decimal("0.001")


def test_unit_dimension_mismatch_is_rejected() -> None:
    with pytest.raises(RuleExecutionError, match="单位维度不一致"):
        convert_value(2, "m", "kN")


def test_safe_formula_evaluation_records_steps() -> None:
    result, steps = safe_evaluate(
        "max(height * load, resistance / 2)",
        {
            "height": Decimal("3"),
            "load": Decimal("2"),
            "resistance": Decimal("10"),
        },
    )
    assert result == Decimal("6")
    assert steps


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('whoami')",
        "(1).__class__",
        "open('secret')",
        "2 ** 999",
    ],
)
def test_safe_formula_blocks_unsafe_syntax(expression: str) -> None:
    with pytest.raises(RuleExecutionError):
        safe_evaluate(expression, {})


def test_comparators() -> None:
    assert compare_values(Decimal("1"), "<", Decimal("2"))
    assert compare_values(Decimal("2"), ">=", Decimal("2"))
    assert not compare_values(Decimal("2"), "!=", Decimal("2"))


def test_parameter_evidence_keeps_location_and_verification_state() -> None:
    row = ParameterValue(
        parameter_name="搭设高度",
        raw_value="24 m",
        numeric_value=Decimal("24"),
        unit="m",
        source_json='{"page_no":8,"quote":"搭设高度为24m"}',
        extraction_method="llm",
        confidence=Decimal("0.9300"),
        verified_by_id=None,
        verified_at=None,
    )
    payload = _parameter_evidence(row, value=Decimal("24"), unit="m")
    assert payload["source"]["page_no"] == 8
    assert payload["source"]["quote"] == "搭设高度为24m"
    assert payload["verified"] is False


def test_rule_schema_rejects_configuration_that_would_fail_at_runtime() -> None:
    with pytest.raises(ValidationError, match="keywords"):
        RuleDefinitionCreate(
            scheme_type_id=1,
            rule_code="REQ-001",
            name="必备章节",
            rule_type="required_section",
            config={},
        )
    with pytest.raises(ValidationError, match="min 不能大于 max"):
        RuleDefinitionCreate(
            scheme_type_id=1,
            rule_code="RANGE-001",
            name="参数范围",
            rule_type="parameter_range",
            config={"parameter": "height", "min": 30, "max": 20},
        )


def test_formula_schema_requires_one_threshold_and_complete_variable_mapping() -> None:
    base = {
        "rule_id": 1,
        "formula_code": "CAPACITY",
        "name": "承载力验算",
        "expression": "load / area",
        "variables": {
            "load": {"parameter": "load"},
            "area": {"parameter": "area"},
        },
    }
    with pytest.raises(ValidationError, match="必须且只能填写一个"):
        FormulaDefinitionCreate(**base)
    with pytest.raises(ValidationError, match="变量映射缺失"):
        FormulaDefinitionCreate(
            **{**base, "variables": {"load": {"parameter": "load"}}},
            threshold_value=1,
        )
