from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.review_governance import ReviewRound
    from app.models.scheme_review_task import SchemeReviewTask
    from app.models.user import User


class DocumentArtifact(Base):
    """Immutable index of every material document produced by a review."""

    __tablename__ = "document_artifacts"
    __table_args__ = (
        UniqueConstraint("task_id", "artifact_kind", "version_no", name="uq_task_artifact_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("scheme_review_tasks.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    review_round_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("review_rounds.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    artifact_kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    minio_bucket: Mapped[str] = mapped_column(String(128), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    supersedes_artifact_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("document_artifacts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    task: Mapped["SchemeReviewTask"] = relationship("SchemeReviewTask")
    review_round: Mapped["ReviewRound | None"] = relationship("ReviewRound")
    created_by: Mapped["User | None"] = relationship("User")
    supersedes_artifact: Mapped["DocumentArtifact | None"] = relationship(
        "DocumentArtifact", remote_side="DocumentArtifact.id"
    )


class OnlyofficeEditSession(Base):
    """Binds one OnlyOffice callback key to one task document version."""

    __tablename__ = "onlyoffice_edit_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("scheme_review_tasks.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    document_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    source_object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    current_object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    task: Mapped["SchemeReviewTask"] = relationship("SchemeReviewTask")
    created_by: Mapped["User | None"] = relationship("User")
