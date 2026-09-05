"""add immutable template snapshots and per-scheme Dify profiles

Revision ID: 026
Revises: 025
Create Date: 2026-08-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scheme_template_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scheme_type_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("configuration_sha256", sa.String(length=64), nullable=False),
        sa.Column("parsed_structure", mysql.LONGTEXT(), nullable=True),
        sa.Column("review_workflow", mysql.LONGTEXT(), nullable=True),
        sa.Column("full_document_review_config", mysql.LONGTEXT(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["scheme_type_id"], ["scheme_types.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scheme_type_id", "version", name="uq_scheme_template_version"),
    )
    op.create_index(
        op.f("ix_scheme_template_versions_scheme_type_id"),
        "scheme_template_versions",
        ["scheme_type_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scheme_template_versions_created_by_id"),
        "scheme_template_versions",
        ["created_by_id"],
        unique=False,
    )
    op.add_column(
        "scheme_types",
        sa.Column("published_template_version_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_scheme_types_published_template_version",
        "scheme_types",
        "scheme_template_versions",
        ["published_template_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_scheme_types_published_template_version_id"),
        "scheme_types",
        ["published_template_version_id"],
        unique=False,
    )

    op.create_table(
        "scheme_dify_workflow_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scheme_type_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("base_url", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("api_key", sa.String(length=2048), nullable=True),
        sa.Column("user_prefix", sa.String(length=255), nullable=False, server_default="smart-review"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="900"),
        sa.Column("output_variable", sa.String(length=128), nullable=False, server_default="report"),
        sa.Column("output_format", sa.String(length=32), nullable=False, server_default="json"),
        sa.Column("accept_partial", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("continue_on_failure", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("input_mapping", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["scheme_type_id"], ["scheme_types.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scheme_type_id"),
    )
    op.add_column("scheme_review_tasks", sa.Column("template_version_id", sa.Integer(), nullable=True))
    op.add_column("scheme_review_tasks", sa.Column("template_snapshot_json", mysql.LONGTEXT(), nullable=True))
    op.add_column("scheme_review_tasks", sa.Column("dify_workflow_profile_id", sa.Integer(), nullable=True))
    op.add_column("scheme_review_tasks", sa.Column("dify_workflow_profile_version", sa.Integer(), nullable=True))
    op.add_column("scheme_review_tasks", sa.Column("dify_workflow_inputs_snapshot", mysql.LONGTEXT(), nullable=True))
    op.add_column("scheme_review_tasks", sa.Column("dify_workflow_config_snapshot", mysql.LONGTEXT(), nullable=True))
    op.add_column("scheme_review_tasks", sa.Column("dify_workflow_run_id", sa.String(length=128), nullable=True))
    op.add_column("scheme_review_tasks", sa.Column("dify_workflow_task_id", sa.String(length=128), nullable=True))
    op.add_column("scheme_review_tasks", sa.Column("dify_workflow_status", sa.String(length=32), nullable=True))
    op.add_column("scheme_review_tasks", sa.Column("dify_workflow_output_format", sa.String(length=32), nullable=True))
    op.create_foreign_key(
        "fk_review_tasks_template_version",
        "scheme_review_tasks",
        "scheme_template_versions",
        ["template_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_review_tasks_dify_profile",
        "scheme_review_tasks",
        "scheme_dify_workflow_profiles",
        ["dify_workflow_profile_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_scheme_review_tasks_template_version_id"), "scheme_review_tasks", ["template_version_id"], unique=False)
    op.create_index(op.f("ix_scheme_review_tasks_dify_workflow_profile_id"), "scheme_review_tasks", ["dify_workflow_profile_id"], unique=False)
    op.create_index(op.f("ix_scheme_review_tasks_dify_workflow_run_id"), "scheme_review_tasks", ["dify_workflow_run_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_scheme_review_tasks_dify_workflow_run_id"), table_name="scheme_review_tasks")
    op.drop_index(op.f("ix_scheme_review_tasks_dify_workflow_profile_id"), table_name="scheme_review_tasks")
    op.drop_index(op.f("ix_scheme_review_tasks_template_version_id"), table_name="scheme_review_tasks")
    op.drop_constraint("fk_review_tasks_dify_profile", "scheme_review_tasks", type_="foreignkey")
    op.drop_constraint("fk_review_tasks_template_version", "scheme_review_tasks", type_="foreignkey")
    for column in (
        "dify_workflow_output_format",
        "dify_workflow_status",
        "dify_workflow_task_id",
        "dify_workflow_run_id",
        "dify_workflow_config_snapshot",
        "dify_workflow_inputs_snapshot",
        "dify_workflow_profile_version",
        "dify_workflow_profile_id",
        "template_snapshot_json",
        "template_version_id",
    ):
        op.drop_column("scheme_review_tasks", column)
    op.drop_table("scheme_dify_workflow_profiles")
    op.drop_index(op.f("ix_scheme_types_published_template_version_id"), table_name="scheme_types")
    op.drop_constraint("fk_scheme_types_published_template_version", "scheme_types", type_="foreignkey")
    op.drop_column("scheme_types", "published_template_version_id")
    op.drop_table("scheme_template_versions")
