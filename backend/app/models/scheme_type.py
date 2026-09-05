from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.scheme_review_task import SchemeReviewTask
    from app.models.scheme_template import SchemeTemplate
    from app.models.scheme_template_version import SchemeTemplateVersion
    from app.models.scheme_workflow_profile import SchemeDifyWorkflowProfile
    from app.models.user import User


class SchemeType(Base):
    __tablename__ = "scheme_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    published_template_version_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "scheme_template_versions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_scheme_types_published_template_version",
        ),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    template: Mapped[SchemeTemplate | None] = relationship(
        "SchemeTemplate",
        back_populates="scheme_type",
        uselist=False,
        cascade="all, delete-orphan",
    )
    review_tasks: Mapped[list[SchemeReviewTask]] = relationship(
        "SchemeReviewTask", back_populates="scheme_type"
    )
    dify_workflow_profile: Mapped[SchemeDifyWorkflowProfile | None] = relationship(
        "SchemeDifyWorkflowProfile",
        back_populates="scheme_type",
        uselist=False,
        cascade="all, delete-orphan",
    )
    template_versions: Mapped[list["SchemeTemplateVersion"]] = relationship(
        "SchemeTemplateVersion",
        foreign_keys="SchemeTemplateVersion.scheme_type_id",
        back_populates="scheme_type",
        cascade="all, delete-orphan",
    )
    published_template_version: Mapped["SchemeTemplateVersion | None"] = relationship(
        "SchemeTemplateVersion", foreign_keys=[published_template_version_id]
    )
    published_by: Mapped["User | None"] = relationship("User", foreign_keys=[published_by_id])

    @property
    def template_configured(self) -> bool:
        """已上传模版、完成解析且标题树非空。"""
        t = self.template
        if t is None or t.parsed_at is None:
            return False
        raw = t.parsed_structure
        if not raw or not str(raw).strip():
            return False
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return False
        nodes = data.get("nodes") if isinstance(data, dict) else None
        return isinstance(nodes, list) and len(nodes) > 0

    @property
    def workflow_configured(self) -> bool:
        """已保存有效的审核工作流（起点→结构审核→…→结束）。"""
        t = self.template
        if t is None or not t.review_workflow or not str(t.review_workflow).strip():
            return False
        try:
            data = json.loads(t.review_workflow)
        except json.JSONDecodeError:
            return False
        steps = data.get("steps") if isinstance(data, dict) else None
        if not isinstance(steps, list) or len(steps) < 3:
            return False
        return (
            steps[0] == "start"
            and steps[1] == "structure"
            and steps[-1] == "end"
        )
