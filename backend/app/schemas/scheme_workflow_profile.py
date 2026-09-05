from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


OutputFormat = Literal["auto", "json", "markdown"]
ProfileSource = Literal["scheme_profile", "global"]
CANONICAL_INPUTS = {
    "documents",
    "site_images",
    "project_name",
    "project_region",
    "risk_type",
    "review_focus",
}
DEFAULT_INPUT_MAPPING = {
    "documents": "documents",
    "project_name": "project_name",
    "project_region": "project_region",
    "risk_type": "risk_type",
    "review_focus": "review_focus",
}
_VARIABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_input_mapping(value: dict[str, str]) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for canonical, target in value.items():
        source = str(canonical or "").strip()
        destination = str(target or "").strip()
        if source not in CANONICAL_INPUTS:
            raise ValueError(f"不支持的标准输入字段: {source or '-'}")
        if not _VARIABLE_RE.fullmatch(destination):
            raise ValueError(f"Dify 输入变量名无效: {destination or '-'}")
        cleaned[source] = destination
    if "documents" not in cleaned:
        raise ValueError("input_mapping 必须包含 documents")
    if len(cleaned.values()) != len(set(cleaned.values())):
        raise ValueError("不同标准输入不能映射到同一个 Dify 变量")
    return cleaned


class SchemeWorkflowProfileUpdate(BaseModel):
    enabled: bool = False
    base_url: str = ""
    api_key: str | None = Field(default=None, description="留空表示保留现有密钥")
    clear_api_key: bool = False
    user_prefix: str = "smart-review"
    timeout_seconds: int = Field(default=900, ge=30, le=3600)
    output_variable: str = Field(default="report", min_length=1, max_length=128)
    output_format: OutputFormat = "json"
    accept_partial: bool = True
    continue_on_failure: bool = True
    input_mapping: dict[str, str] = Field(
        default_factory=lambda: dict(DEFAULT_INPUT_MAPPING)
    )

    @field_validator("base_url", "user_prefix", "output_variable")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("input_mapping")
    @classmethod
    def mapping_is_valid(cls, value: dict[str, str]) -> dict[str, str]:
        return validate_input_mapping(value)

    @model_validator(mode="after")
    def enabled_profile_is_complete(self) -> "SchemeWorkflowProfileUpdate":
        if self.enabled and not self.base_url:
            raise ValueError("启用类型 Workflow 时 base_url 不能为空")
        if self.clear_api_key and self.api_key and self.api_key.strip():
            raise ValueError("clear_api_key 与 api_key 不能同时设置")
        return self


class SchemeWorkflowProfilePublic(BaseModel):
    scheme_type_id: int
    profile_id: int | None = None
    version: int | None = None
    configured: bool
    source: ProfileSource
    enabled: bool
    base_url: str
    api_key_configured: bool
    user_prefix: str
    timeout_seconds: int
    output_variable: str
    output_format: OutputFormat
    accept_partial: bool
    continue_on_failure: bool
    input_mapping: dict[str, str]
