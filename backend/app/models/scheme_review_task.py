from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.scheme_type import SchemeType
    from app.models.scheme_workflow_profile import SchemeDifyWorkflowProfile
    from app.models.scheme_template_version import SchemeTemplateVersion
    from app.models.review_attachment import ReviewAttachment
    from app.models.user import User


class ReviewTaskStatus(StrEnum):
    pending = "pending"
    processing = "processing"
    succeeded = "succeeded"
    failed = "failed"
    canceled = "canceled"


class ReviewConclusion(StrEnum):
    """Business conclusion, intentionally separate from task execution status."""

    passed = "passed"
    issues_found = "issues_found"
    not_reviewed = "not_reviewed"


class CompletenessStatus(StrEnum):
    """Whether every configured review stage produced a usable result."""

    complete = "complete"
    partial = "partial"
    unavailable = "unavailable"


class HumanReviewStatus(StrEnum):
    """Reserved lifecycle state for the later expert-review implementation."""

    pending = "pending"
    in_review = "in_review"
    changes_requested = "changes_requested"
    approved = "approved"


# Keep generic Text for non-MySQL engines, but use LONGTEXT on MySQL
# so large JSON reports do not overflow TEXT's 64KB limit.
review_result_text_type = Text().with_variant(mysql.LONGTEXT(), "mysql")


class SchemeReviewTask(Base):
    __tablename__ = "scheme_review_tasks"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_review_task_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scheme_type_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("scheme_types.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ReviewTaskStatus.pending)
    review_conclusion: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ReviewConclusion.not_reviewed, index=True
    )
    completeness_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=CompletenessStatus.unavailable, index=True
    )
    human_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=HumanReviewStatus.pending, index=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    retry_of_task_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("scheme_review_tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    result_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    minio_bucket: Mapped[str] = mapped_column(String(128), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    output_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    review_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_result_json: Mapped[str | None] = mapped_column(review_result_text_type, nullable=True)
    template_version_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("scheme_template_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    template_snapshot_json: Mapped[str | None] = mapped_column(
        review_result_text_type, nullable=True
    )
    dify_workflow_profile_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("scheme_dify_workflow_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    dify_workflow_profile_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dify_workflow_inputs_snapshot: Mapped[str | None] = mapped_column(
        review_result_text_type, nullable=True
    )
    dify_workflow_config_snapshot: Mapped[str | None] = mapped_column(
        review_result_text_type, nullable=True
    )
    dify_workflow_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    dify_workflow_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dify_workflow_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dify_workflow_output_format: Mapped[str | None] = mapped_column(String(32), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    scheme_type: Mapped[SchemeType] = relationship("SchemeType", back_populates="review_tasks")
    dify_workflow_profile: Mapped[SchemeDifyWorkflowProfile | None] = relationship(
        "SchemeDifyWorkflowProfile", back_populates="review_tasks"
    )
    template_version: Mapped["SchemeTemplateVersion | None"] = relationship(
        "SchemeTemplateVersion", foreign_keys=[template_version_id]
    )
    attachments: Mapped[list["ReviewAttachment"]] = relationship(
        "ReviewAttachment", back_populates="task", cascade="all, delete-orphan"
    )
    retry_of_task: Mapped["SchemeReviewTask | None"] = relationship(
        "SchemeReviewTask", remote_side="SchemeReviewTask.id", foreign_keys=[retry_of_task_id]
    )
    user: Mapped[User] = relationship("User", back_populates="review_tasks")
