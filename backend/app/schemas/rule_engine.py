from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import ast
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


RuleType = Literal["required_section", "parameter_range", "cross_field", "formula"]
_FORMULA_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_FORMULA_FUNCTIONS = {"abs", "min", "max", "sqrt"}


def validate_rule_configuration(rule_type: str, config: dict) -> dict:
    if rule_type == "required_section":
        keywords = config.get("keywords")
        if not isinstance(keywords, list) or not any(str(item).strip() for item in keywords):
            raise ValueError("required_section 必须配置非空 keywords")
        if str(config.get("match") or "all") not in {"all", "any"}:
            raise ValueError("required_section.match 只能是 all 或 any")
    elif rule_type == "parameter_range":
        if not str(config.get("parameter") or "").strip():
            raise ValueError("parameter_range 必须配置 parameter")
        if config.get("min") is None and config.get("max") is None:
            raise ValueError("parameter_range 至少配置 min 或 max")
        try:
            minimum = Decimal(str(config["min"])) if config.get("min") is not None else None
            maximum = Decimal(str(config["max"])) if config.get("max") is not None else None
        except Exception as exc:
            raise ValueError("parameter_range 的 min/max 必须是数值") from exc
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError("parameter_range 的 min 不能大于 max")
    elif rule_type == "cross_field":
        left = str(config.get("left") or "").strip()
        right = str(config.get("right") or "").strip()
        if not left or not right or left == right:
            raise ValueError("cross_field 必须配置两个不同的参数")
        if str(config.get("operator") or "==") not in {"<", "<=", "==", ">=", ">", "!="}:
            raise ValueError("cross_field.operator 不受支持")
        try:
            tolerance = Decimal(str(config.get("tolerance") or "0"))
        except Exception as exc:
            raise ValueError("cross_field.tolerance 必须是数值") from exc
        if tolerance < 0:
            raise ValueError("cross_field.tolerance 不能为负数")
    elif rule_type == "formula":
        if config and not isinstance(config, dict):
            raise ValueError("formula.config 必须是对象")
    else:
        raise ValueError(f"不支持的规则类型: {rule_type}")
    return config


class RuleDefinitionCreate(BaseModel):
    scheme_type_id: int
    rule_code: str = Field(..., min_length=1, max_length=128)
    version: int = Field(default=1, ge=1)
    name: str = Field(..., min_length=1, max_length=255)
    rule_type: RuleType
    severity: Literal["error", "warning", "info"] = "error"
    enabled: bool = True
    config: dict = Field(default_factory=dict)
    source_standard_no: str = Field(default="", max_length=128)
    source_standard_name: str = Field(default="", max_length=512)
    source_version: str = Field(default="", max_length=64)
    source_clause: str = Field(default="", max_length=128)
    source_text: str = ""

    @field_validator("rule_code", "name")
    @classmethod
    def non_blank_rule_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("不能为空白文本")
        return cleaned

    @model_validator(mode="after")
    def config_matches_rule_type(self) -> "RuleDefinitionCreate":
        validate_rule_configuration(self.rule_type, self.config)
        return self


class RuleDefinitionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    severity: Literal["error", "warning", "info"] | None = None
    enabled: bool | None = None
    config: dict | None = None
    source_standard_no: str | None = Field(default=None, max_length=128)
    source_standard_name: str | None = Field(default=None, max_length=512)
    source_version: str | None = Field(default=None, max_length=64)
    source_clause: str | None = Field(default=None, max_length=128)
    source_text: str | None = None


class RuleDefinitionPublic(RuleDefinitionCreate):
    id: int
    created_by_id: int | None = None
    created_at: datetime
    updated_at: datetime


class FormulaDefinitionCreate(BaseModel):
    rule_id: int
    formula_code: str = Field(..., min_length=1, max_length=128)
    version: int = Field(default=1, ge=1)
    name: str = Field(..., min_length=1, max_length=255)
    expression: str = Field(..., min_length=1, max_length=4000)
    variables: dict[str, dict | str] = Field(default_factory=dict)
    result_unit: str = Field(default="", max_length=32)
    comparator: Literal["<", "<=", "==", ">=", ">", "!="] = "<="
    threshold_value: Decimal | None = None
    threshold_parameter: str | None = Field(default=None, max_length=128)
    enabled: bool = True

    @field_validator("threshold_parameter")
    @classmethod
    def strip_threshold_parameter(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None

    @field_validator("formula_code", "name", "expression")
    @classmethod
    def non_blank_formula_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("不能为空白文本")
        return cleaned

    @model_validator(mode="after")
    def formula_is_deterministic(self) -> "FormulaDefinitionCreate":
        if (self.threshold_value is None) == (self.threshold_parameter is None):
            raise ValueError("threshold_value 与 threshold_parameter 必须且只能填写一个")
        invalid_names = [name for name in self.variables if not _FORMULA_NAME_RE.fullmatch(name)]
        if invalid_names:
            raise ValueError(f"公式变量名无效: {invalid_names[0]}")
        try:
            tree = ast.parse(self.expression, mode="eval")
        except SyntaxError as exc:
            raise ValueError("公式表达式语法错误") from exc
        referenced = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and node.id not in _FORMULA_FUNCTIONS
        }
        missing = sorted(referenced - set(self.variables))
        if missing:
            raise ValueError(f"公式变量映射缺失: {missing[0]}")
        return self


class FormulaDefinitionPublic(FormulaDefinitionCreate):
    id: int
    created_at: datetime
    updated_at: datetime


class ParameterValueUpsert(BaseModel):
    parameter_name: str = Field(..., min_length=1, max_length=128)
    raw_value: str = Field(default="", max_length=255)
    numeric_value: Decimal | None = None
    unit: str = Field(default="", max_length=32)
    source: dict = Field(default_factory=dict)
    extraction_method: Literal["manual", "regex", "llm", "table", "formula"] = "manual"
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    verified: bool = False

    @field_validator("parameter_name")
    @classmethod
    def non_blank_parameter_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("参数名不能为空白文本")
        return cleaned


class ParameterValuePublic(BaseModel):
    id: int
    task_id: int
    parameter_name: str
    raw_value: str
    numeric_value: Decimal | None
    unit: str
    normalized_value: Decimal | None
    normalized_unit: str
    source: dict = Field(default_factory=dict)
    extraction_method: str
    confidence: Decimal | None
    verified_by_id: int | None
    verified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CalculationResultPublic(BaseModel):
    id: int
    task_id: int
    rule_id: int
    formula_id: int | None
    passed: bool
    calculated_value: Decimal | None
    result_unit: str
    inputs: dict = Field(default_factory=dict)
    steps: list = Field(default_factory=list)
    expected: dict = Field(default_factory=dict)
    message: str
    error_message: str
    created_at: datetime


class RuleRunResponse(BaseModel):
    task_id: int
    total: int
    passed: int
    failed: int
    errors: int
    results: list[CalculationResultPublic]


class EvidenceSourceCreate(BaseModel):
    review_issue_id: int | None = None
    source_kind: str = Field(default="regulation", max_length=32)
    standard_no: str = Field(default="", max_length=128)
    standard_name: str = Field(default="", max_length=512)
    standard_version: str = Field(default="", max_length=64)
    effect_status: str = Field(default="", max_length=64)
    clause_no: str = Field(default="", max_length=128)
    clause_text: str = ""
    page_no: str = Field(default="", max_length=32)
    dataset_id: str = Field(default="", max_length=128)
    segment_id: str = Field(default="", max_length=128)
    retrieval_score: Decimal | None = None
    scheme_quote: str = ""
    location: dict = Field(default_factory=dict)


class EvidenceSourcePublic(EvidenceSourceCreate):
    id: int
    task_id: int
    created_at: datetime
