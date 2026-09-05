from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.scheme_review_task import SchemeReviewTask
    from app.models.scheme_type import SchemeType
    from app.models.user import User


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    construction_unit: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    contractor: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    supervision_unit: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    created_by: Mapped["User | None"] = relationship("User", foreign_keys=[created_by_id])
    revisions: Mapped[list["DocumentRevision"]] = relationship(
        "DocumentRevision", back_populates="project", cascade="all, delete-orphan"
    )


class DocumentRevision(Base):
    __tablename__ = "document_revisions"
    __table_args__ = (
        UniqueConstraint("project_id", "scheme_type_id", "version_label", name="uq_revision_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scheme_type_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("scheme_types.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    parent_revision_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("document_revisions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    version_label: Mapped[str] = mapped_column(String(64), nullable=False, default="V1")
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    minio_bucket: Mapped[str] = mapped_column(String(128), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped[Project] = relationship("Project", back_populates="revisions")
    scheme_type: Mapped["SchemeType"] = relationship("SchemeType")
    parent_revision: Mapped["DocumentRevision | None"] = relationship(
        "DocumentRevision", remote_side="DocumentRevision.id"
    )
    created_by: Mapped["User | None"] = relationship("User", foreign_keys=[created_by_id])
    review_rounds: Mapped[list["ReviewRound"]] = relationship(
        "ReviewRound", back_populates="document_revision"
    )


class ReviewRound(Base):
    __tablename__ = "review_rounds"
    __table_args__ = (
        UniqueConstraint("document_revision_id", "round_no", name="uq_review_round_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_revision_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("document_revisions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("scheme_review_tasks.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    parent_round_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("review_rounds.id", ondelete="SET NULL"), nullable=True, index=True
    )
    round_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_ai", index=True)
    assigned_expert_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    conclusion: Mapped[str | None] = mapped_column(String(32), nullable=True)
    final_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signed_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signed_report_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    signed_report_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    document_revision: Mapped["DocumentRevision | None"] = relationship(
        "DocumentRevision", back_populates="review_rounds"
    )
    task: Mapped["SchemeReviewTask"] = relationship("SchemeReviewTask")
    parent_round: Mapped["ReviewRound | None"] = relationship(
        "ReviewRound", remote_side="ReviewRound.id"
    )
    assigned_expert: Mapped["User | None"] = relationship(
        "User", foreign_keys=[assigned_expert_id]
    )
    signed_by: Mapped["User | None"] = relationship("User", foreign_keys=[signed_by_id])
    issues: Mapped[list["ReviewIssue"]] = relationship(
        "ReviewIssue", back_populates="review_round", cascade="all, delete-orphan"
    )
    decisions: Mapped[list["ExpertDecision"]] = relationship(
        "ExpertDecision", back_populates="review_round", cascade="all, delete-orphan"
    )


class ReviewIssue(Base):
    __tablename__ = "review_issues"
    __table_args__ = (UniqueConstraint("review_round_id", "issue_key", name="uq_round_issue_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_round_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("review_rounds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    issue_key: Mapped[str] = mapped_column(String(64), nullable=False)
    source_issue_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    step_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="warning")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False, default="")
    anchor_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    related_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    disposition: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", index=True)
    reviewer_comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    final_severity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    reviewed_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    review_round: Mapped[ReviewRound] = relationship("ReviewRound", back_populates="issues")
    reviewed_by: Mapped["User | None"] = relationship("User", foreign_keys=[reviewed_by_id])


class ExpertDecision(Base):
    __tablename__ = "expert_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_round_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("review_rounds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    issue_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("review_issues.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    review_round: Mapped[ReviewRound] = relationship("ReviewRound", back_populates="decisions")
    issue: Mapped["ReviewIssue | None"] = relationship("ReviewIssue")
    actor: Mapped["User | None"] = relationship("User", foreign_keys=[actor_id])


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    data_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    actor: Mapped["User | None"] = relationship("User", foreign_keys=[actor_id])
