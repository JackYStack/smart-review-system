from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.scheme_review_task import SchemeReviewTask
    from app.models.scheme_type import SchemeType


class SchemeDifyWorkflowProfile(Base):
    """Versioned per-scheme Dify Workflow configuration.

    ``api_key`` always stores the encrypted secret-store representation.  A row
    is an explicit override: a disabled row disables Dify for that scheme rather
    than inheriting the global integration setting.
    """

    __tablename__ = "scheme_dify_workflow_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scheme_type_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("scheme_types.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    api_key: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    user_prefix: Mapped[str] = mapped_column(
        String(255), nullable=False, default="smart-review"
    )
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=900)
    output_variable: Mapped[str] = mapped_column(String(128), nullable=False, default="report")
    output_format: Mapped[str] = mapped_column(String(32), nullable=False, default="json")
    accept_partial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    continue_on_failure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    input_mapping: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    scheme_type: Mapped[SchemeType] = relationship(
        "SchemeType", back_populates="dify_workflow_profile"
    )
    review_tasks: Mapped[list[SchemeReviewTask]] = relationship(
        "SchemeReviewTask", back_populates="dify_workflow_profile"
    )
