from pydantic import BaseModel, Field, field_validator


class KnowledgeBasePublic(BaseModel):
    """返回给前端：不暴露完整密钥。"""

    dify_base_url: str
    dify_dataset_name_prefix: str
    api_key_configured: bool


class DifyDatasetItem(BaseModel):
    """Dify 知识库（数据集）列表项。"""

    id: str
    name: str


class KnowledgeBaseTestRequest(BaseModel):
    """Connection test values; blank secret means reuse the saved key."""

    dify_base_url: str | None = None
    dify_dataset_name_prefix: str | None = None
    dify_api_key: str | None = Field(
        default=None,
        description="Temporary Dataset API key; blank means use the saved key",
    )
    test_query: str = Field(
        default="脚手架安全技术要求",
        max_length=250,
        description="A short query used to verify that dataset retrieval really works",
    )

    @field_validator("dify_base_url", "dify_dataset_name_prefix", "dify_api_key", "test_query")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class KnowledgeBaseTestResult(BaseModel):
    ok: bool
    status: str
    detail: str
    latency_ms: int
    dataset_count: int = 0
    datasets: list[DifyDatasetItem] = Field(default_factory=list)


class KnowledgeBaseUpdate(BaseModel):
    dify_base_url: str = Field(..., description="Dify API 根路径，如 http://host/v1")
    dify_dataset_name_prefix: str = Field(default="", description="仅显示名称以该前缀开头的知识库")
    dify_api_key: str | None = Field(
        default=None,
        description="新密钥；不传或空字符串表示不修改已保存的密钥",
    )

    @field_validator("dify_base_url")
    @classmethod
    def strip_url(cls, v: str) -> str:
        return v.strip()

    @field_validator("dify_dataset_name_prefix")
    @classmethod
    def strip_dataset_prefix(cls, v: str) -> str:
        return v.strip()
