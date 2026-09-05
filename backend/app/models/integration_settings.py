from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IntegrationSettings(Base):
    """Runtime integration overrides; NULL means use the deployment environment."""

    __tablename__ = "integration_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    dify_workflow_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    dify_workflow_base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    dify_workflow_api_key: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    dify_workflow_user_prefix: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dify_workflow_timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dify_workflow_output_variable: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dify_workflow_output_format: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dify_workflow_accept_partial: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    dify_workflow_continue_on_failure: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    paddleocr_api_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    paddleocr_api_key: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    paddleocr_timeout_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    paddle_convert_timeout_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

