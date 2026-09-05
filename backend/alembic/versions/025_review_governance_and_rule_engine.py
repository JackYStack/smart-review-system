"""add project governance, expert review, evidence and deterministic rules

Revision ID: 025
Revises: 024
Create Date: 2026-08-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scheme_types",
        sa.Column("lifecycle_status", sa.String(length=32), nullable=False, server_default="draft"),
    )
    op.add_column("scheme_types", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("scheme_types", sa.Column("published_by_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_scheme_types_published_by_id_users",
        "scheme_types",
        "users",
        ["published_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_scheme_types_lifecycle_status"), "scheme_types", ["lifecycle_status"], unique=False)
    op.create_index(op.f("ix_scheme_types_published_by_id"), "scheme_types", ["published_by_id"], unique=False)

    op.add_column("basis_items", sa.Column("scheme_type_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_basis_items_scheme_type_id_scheme_types",
        "basis_items",
        "scheme_types",
        ["scheme_type_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_basis_items_scheme_type_id"), "basis_items", ["scheme_type_id"], unique=False)
    op.execute(
        sa.text(
            "UPDATE basis_items b JOIN scheme_types s "
            "ON b.scheme_category = s.category AND b.scheme_name = s.name "
            "SET b.scheme_type_id = s.id WHERE b.scheme_type_id IS NULL"
        )
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("region", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("construction_unit", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("contractor", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("supervision_unit", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_projects_name"), "projects", ["name"], unique=False)
    op.create_index(op.f("ix_projects_created_by_id"), "projects", ["created_by_id"], unique=False)

    op.create_table(
        "document_revisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("scheme_type_id", sa.Integer(), nullable=False),
        sa.Column("parent_revision_id", sa.Integer(), nullable=True),
        sa.Column("version_label", sa.String(length=64), nullable=False, server_default="V1"),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("minio_bucket", sa.String(length=128), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_revision_id"], ["document_revisions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scheme_type_id"], ["scheme_types.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
        sa.UniqueConstraint("project_id", "scheme_type_id", "version_label", name="uq_revision_version"),
    )
    op.create_index(op.f("ix_document_revisions_project_id"), "document_revisions", ["project_id"], unique=False)
    op.create_index(op.f("ix_document_revisions_scheme_type_id"), "document_revisions", ["scheme_type_id"], unique=False)
    op.create_index(op.f("ix_document_revisions_parent_revision_id"), "document_revisions", ["parent_revision_id"], unique=False)
    op.create_index(op.f("ix_document_revisions_created_by_id"), "document_revisions", ["created_by_id"], unique=False)

    op.create_table(
        "review_rounds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_revision_id", sa.Integer(), nullable=True),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("parent_round_id", sa.Integer(), nullable=True),
        sa.Column("round_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending_ai"),
        sa.Column("assigned_expert_id", sa.Integer(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("conclusion", sa.String(length=32), nullable=True),
        sa.Column("final_comment", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signed_by_id", sa.Integer(), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signed_report_object_key", sa.String(length=512), nullable=True),
        sa.Column("signed_report_sha256", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["assigned_expert_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_revision_id"], ["document_revisions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_round_id"], ["review_rounds.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["signed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["scheme_review_tasks.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_revision_id", "round_no", name="uq_review_round_number"),
        sa.UniqueConstraint("task_id"),
    )
    for column in ("document_revision_id", "parent_round_id", "status", "assigned_expert_id", "signed_by_id"):
        op.create_index(op.f(f"ix_review_rounds_{column}"), "review_rounds", [column], unique=False)

    op.create_table(
        "review_issues",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_round_id", sa.Integer(), nullable=False),
        sa.Column("issue_key", sa.String(length=64), nullable=False),
        sa.Column("source_issue_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("step_id", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="warning"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("anchor_json", sa.Text(), nullable=False),
        sa.Column("related_json", sa.Text(), nullable=False),
        sa.Column("disposition", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("reviewer_comment", sa.Text(), nullable=False),
        sa.Column("final_severity", sa.String(length=16), nullable=True),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["review_round_id"], ["review_rounds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_round_id", "issue_key", name="uq_round_issue_key"),
    )
    for column in ("review_round_id", "step_id", "disposition", "reviewed_by_id"):
        op.create_index(op.f(f"ix_review_issues_{column}"), "review_issues", [column], unique=False)

    op.create_table(
        "expert_decisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_round_id", sa.Integer(), nullable=False),
        sa.Column("issue_id", sa.Integer(), nullable=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["issue_id"], ["review_issues.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["review_round_id"], ["review_rounds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("review_round_id", "issue_id", "actor_id", "action"):
        op.create_index(op.f(f"ix_expert_decisions_{column}"), "expert_decisions", [column], unique=False)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("data_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("actor_id", "entity_type", "entity_id", "action"):
        op.create_index(op.f(f"ix_audit_events_{column}"), "audit_events", [column], unique=False)

    op.create_table(
        "rule_definitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scheme_type_id", sa.Integer(), nullable=False),
        sa.Column("rule_code", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("rule_type", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="error"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("source_standard_no", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("source_standard_name", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("source_version", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("source_clause", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["scheme_type_id"], ["scheme_types.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scheme_type_id", "rule_code", "version", name="uq_rule_version"),
    )
    for column in ("scheme_type_id", "rule_code", "rule_type"):
        op.create_index(op.f(f"ix_rule_definitions_{column}"), "rule_definitions", [column], unique=False)

    op.create_table(
        "formula_definitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("formula_code", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("expression", sa.Text(), nullable=False),
        sa.Column("variables_json", sa.Text(), nullable=False),
        sa.Column("result_unit", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("comparator", sa.String(length=8), nullable=False, server_default="<="),
        sa.Column("threshold_value", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("threshold_parameter", sa.String(length=128), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["rule_id"], ["rule_definitions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_id", "formula_code", "version", name="uq_formula_version"),
    )
    op.create_index(op.f("ix_formula_definitions_rule_id"), "formula_definitions", ["rule_id"], unique=False)

    op.create_table(
        "parameter_values",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("parameter_name", sa.String(length=128), nullable=False),
        sa.Column("raw_value", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("numeric_value", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("normalized_value", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("normalized_unit", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("source_json", sa.Text(), nullable=False),
        sa.Column("extraction_method", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("verified_by_id", sa.Integer(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["scheme_review_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "parameter_name", name="uq_task_parameter"),
    )
    op.create_index(op.f("ix_parameter_values_task_id"), "parameter_values", ["task_id"], unique=False)

    op.create_table(
        "calculation_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("formula_id", sa.Integer(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("calculated_value", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("result_unit", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("inputs_json", sa.Text(), nullable=False),
        sa.Column("steps_json", sa.Text(), nullable=False),
        sa.Column("expected_json", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["formula_id"], ["formula_definitions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rule_id"], ["rule_definitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["task_id"], ["scheme_review_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("task_id", "rule_id", "formula_id"):
        op.create_index(op.f(f"ix_calculation_results_{column}"), "calculation_results", [column], unique=False)

    op.create_table(
        "evidence_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("review_issue_id", sa.Integer(), nullable=True),
        sa.Column("source_kind", sa.String(length=32), nullable=False, server_default="regulation"),
        sa.Column("standard_no", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("standard_name", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("standard_version", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("effect_status", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("clause_no", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("clause_text", sa.Text(), nullable=False),
        sa.Column("page_no", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("dataset_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("segment_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("retrieval_score", sa.Numeric(precision=8, scale=6), nullable=True),
        sa.Column("scheme_quote", sa.Text(), nullable=False),
        sa.Column("location_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["review_issue_id"], ["review_issues.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["scheme_review_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evidence_sources_task_id"), "evidence_sources", ["task_id"], unique=False)
    op.create_index(op.f("ix_evidence_sources_review_issue_id"), "evidence_sources", ["review_issue_id"], unique=False)


def downgrade() -> None:
    op.drop_table("evidence_sources")
    op.drop_table("calculation_results")
    op.drop_table("parameter_values")
    op.drop_table("formula_definitions")
    op.drop_table("rule_definitions")
    op.drop_table("audit_events")
    op.drop_table("expert_decisions")
    op.drop_table("review_issues")
    op.drop_table("review_rounds")
    op.drop_table("document_revisions")
    op.drop_table("projects")
    op.drop_index(op.f("ix_basis_items_scheme_type_id"), table_name="basis_items")
    op.drop_constraint("fk_basis_items_scheme_type_id_scheme_types", "basis_items", type_="foreignkey")
    op.drop_column("basis_items", "scheme_type_id")
    op.drop_index(op.f("ix_scheme_types_published_by_id"), table_name="scheme_types")
    op.drop_index(op.f("ix_scheme_types_lifecycle_status"), table_name="scheme_types")
    op.drop_constraint("fk_scheme_types_published_by_id_users", "scheme_types", type_="foreignkey")
    op.drop_column("scheme_types", "published_by_id")
    op.drop_column("scheme_types", "published_at")
    op.drop_column("scheme_types", "lifecycle_status")
