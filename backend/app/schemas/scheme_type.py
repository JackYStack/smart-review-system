from datetime import datetime

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SchemeTypeCreate(BaseModel):
    category: str = Field(..., description="方案大类")
    name: str = Field(..., description="方案名称")
    remark: str | None = None

    @field_validator("category")
    @classmethod
    def category_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("方案大类不能为空")
        return s


class SchemeTypeUpdate(BaseModel):
    category: str | None = None
    name: str | None = None
    remark: str | None = None

    @field_validator("category")
    @classmethod
    def category_if_set(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if not s:
            raise ValueError("方案大类不能为空")
        return s


class SchemeTypeRead(BaseModel):
    id: int
    category: str
    name: str
    remark: str | None
    lifecycle_status: Literal["draft", "pending_validation", "published", "disabled"] = "draft"
    published_at: datetime | None = None
    published_by_id: int | None = None
    published_template_version_id: int | None = None
    created_at: datetime | None
    updated_at: datetime | None
    template_configured: bool = False
    workflow_configured: bool = False
    readiness_status: Literal["ready", "incomplete", "unavailable"] = "incomplete"
    readiness_issues: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class SchemeReadinessRead(BaseModel):
    scheme_type_id: int
    readiness_status: Literal["ready", "incomplete", "unavailable"]
    readiness_issues: list[str] = Field(default_factory=list)


class SchemeLifecycleAction(BaseModel):
    comment: str = Field(default="", max_length=2000)
