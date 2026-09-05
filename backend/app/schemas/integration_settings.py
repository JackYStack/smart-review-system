from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


ConfigSource = Literal["database", "environment", "default"]
OutputFormat = Literal["auto", "json", "markdown"]


class WorkflowIntegrationPublic(BaseModel):
    enabled: bool
    base_url: str
    api_key_configured: bool
    user_prefix: str
    timeout_seconds: int
    output_variable: str
    output_format: OutputFormat
    accept_partial: bool
    continue_on_failure: bool
    source: ConfigSource


class DocumentIntegrationPublic(BaseModel):
    paddleocr_api_url: str
    paddleocr_api_key_configured: bool
    paddleocr_timeout_seconds: float
    convert_timeout_seconds: float
    libreoffice_configured: bool
    source: ConfigSource


class IntegrationSettingsPublic(BaseModel):
    workflow: WorkflowIntegrationPublic
    document: DocumentIntegrationPublic


class IntegrationSettingsUpdate(BaseModel):
    dify_workflow_enabled: bool
    dify_workflow_base_url: str
    dify_workflow_api_key: str | None = Field(default=None, description="留空表示不修改密钥")
    dify_workflow_user_prefix: str = "smart-review"
    dify_workflow_timeout_seconds: int = Field(default=900, ge=30, le=3600)
    dify_workflow_output_variable: str = "report"
    dify_workflow_output_format: OutputFormat = "auto"
    dify_workflow_accept_partial: bool = True
    dify_workflow_continue_on_failure: bool = True
    paddleocr_api_url: str
    paddleocr_api_key: str | None = Field(default=None, description="留空表示不修改密钥")
    paddleocr_timeout_seconds: float = Field(default=600, ge=10, le=3600)
    paddle_convert_timeout_seconds: float = Field(default=180, ge=10, le=1200)

    @field_validator(
        "dify_workflow_base_url",
        "dify_workflow_user_prefix",
        "dify_workflow_output_variable",
        "paddleocr_api_url",
    )
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("dify_workflow_output_variable")
    @classmethod
    def validate_output_variable(cls, value: str) -> str:
        if not value:
            raise ValueError("输出变量名不能为空")
        return value


class IntegrationTestRequest(BaseModel):
    service: Literal[
        "dify_workflow",
        "dify_dataset",
        "paddleocr",
        "libreoffice",
        "onlyoffice",
        "minio",
    ]


class IntegrationTestResult(BaseModel):
    service: str
    ok: bool
    status: str
    detail: str
    latency_ms: int | None = None
    app_name: str | None = None


class ServiceStatusItem(BaseModel):
    service: str
    label: str
    state: Literal["connected", "configured", "unconfigured", "error"]
    detail: str
    editable: bool


class ServiceStatusPublic(BaseModel):
    services: list[ServiceStatusItem]
