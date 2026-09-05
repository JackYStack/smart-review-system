from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.scheme_type import SchemeType
    from app.models.user import User


snapshot_text = Text().with_variant(mysql.LONGTEXT(), "mysql")


class SchemeTemplateVersion(Base):
    """Immutable snapshot used to reproduce a review configuration."""

    __tablename__ = "scheme_template_versions"
    __table_args__ = (
        UniqueConstraint("scheme_type_id", "version", name="uq_scheme_template_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scheme_type_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("scheme_types.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    configuration_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    parsed_structure: Mapped[str | None] = mapped_column(snapshot_text, nullable=True)
    review_workflow: Mapped[str | None] = mapped_column(snapshot_text, nullable=True)
    full_document_review_config: Mapped[str | None] = mapped_column(snapshot_text, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    scheme_type: Mapped["SchemeType"] = relationship(
        "SchemeType", foreign_keys=[scheme_type_id], back_populates="template_versions"
    )
    created_by: Mapped["User | None"] = relationship("User", foreign_keys=[created_by_id])
