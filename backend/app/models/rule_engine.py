from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.review_governance import ReviewIssue
    from app.models.scheme_review_task import SchemeReviewTask
    from app.models.scheme_type import SchemeType
    from app.models.user import User


class RuleDefinition(Base):
    __tablename__ = "rule_definitions"
    __table_args__ = (
        UniqueConstraint("scheme_type_id", "rule_code", "version", name="uq_rule_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scheme_type_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("scheme_types.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="error")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    source_standard_no: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    source_standard_name: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    source_version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    source_clause: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    source_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    scheme_type: Mapped["SchemeType"] = relationship("SchemeType")
    created_by: Mapped["User | None"] = relationship("User")
    formulas: Mapped[list["FormulaDefinition"]] = relationship(
        "FormulaDefinition", back_populates="rule", cascade="all, delete-orphan"
    )


class FormulaDefinition(Base):
    __tablename__ = "formula_definitions"
    __table_args__ = (
        UniqueConstraint("rule_id", "formula_code", "version", name="uq_formula_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rule_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    formula_code: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    expression: Mapped[str] = mapped_column(Text, nullable=False)
    variables_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    result_unit: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    comparator: Mapped[str] = mapped_column(String(8), nullable=False, default="<=")
    threshold_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    threshold_parameter: Mapped[str | None] = mapped_column(String(128), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    rule: Mapped[RuleDefinition] = relationship("RuleDefinition", back_populates="formulas")


class ParameterValue(Base):
    __tablename__ = "parameter_values"
    __table_args__ = (
        UniqueConstraint("task_id", "parameter_name", name="uq_task_parameter"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("scheme_review_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parameter_name: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_value: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    normalized_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    normalized_unit: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    source_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    extraction_method: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    verified_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    task: Mapped["SchemeReviewTask"] = relationship("SchemeReviewTask")
    verified_by: Mapped["User | None"] = relationship("User")


class CalculationResult(Base):
    __tablename__ = "calculation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("scheme_review_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rule_definitions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    formula_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("formula_definitions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    calculated_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    result_unit: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    inputs_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    steps_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    expected_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task: Mapped["SchemeReviewTask"] = relationship("SchemeReviewTask")
    rule: Mapped[RuleDefinition] = relationship("RuleDefinition")
    formula: Mapped["FormulaDefinition | None"] = relationship("FormulaDefinition")


class EvidenceSource(Base):
    __tablename__ = "evidence_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("scheme_review_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    review_issue_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("review_issues.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="regulation")
    standard_no: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    standard_name: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    standard_version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    effect_status: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    clause_no: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    clause_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    page_no: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    dataset_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    segment_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    retrieval_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 6), nullable=True)
    scheme_quote: Mapped[str] = mapped_column(Text, nullable=False, default="")
    location_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task: Mapped["SchemeReviewTask"] = relationship("SchemeReviewTask")
    review_issue: Mapped["ReviewIssue | None"] = relationship("ReviewIssue")
