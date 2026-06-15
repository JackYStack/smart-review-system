from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "危大工程智审系统"
    api_v1_prefix: str = "/api/v1"
    debug: bool = True
    secret_key: str = Field(default="dev-secret-key-change-in-production")

    postgres_url: str = "postgresql://user:pass@localhost:5432/smart_review"
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    redis_url: str = "redis://localhost:6379/0"

    vllm_base_url: str = "http://localhost:8000/v1"
    vllm_model_name: str = "Qwen/Qwen3-30B-A3B"
    vllm_api_key: str = "not-needed-for-local"
    bge_m3_model_path: str = "./models/bge-m3"

    max_parse_timeout_seconds: int = 300
    max_review_timeout_seconds: int = 600

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_flag(cls, value: object) -> object:
        """Accept common deployment words in DEBUG-like environments."""

        if isinstance(value, str) and value.lower() in {"release", "prod", "production"}:
            return False
        return value


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
