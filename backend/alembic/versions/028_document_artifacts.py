"""add immutable document artifact history

Revision ID: 028
Revises: 027
Create Date: 2026-08-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_artifacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("review_round_id", sa.Integer(), nullable=True),
        sa.Column("artifact_kind", sa.String(length=32), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("minio_bucket", sa.String(length=128), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("immutable", sa.Boolean(), nullable=False),
        sa.Column("supersedes_artifact_id", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["review_round_id"], ["review_rounds.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supersedes_artifact_id"], ["document_artifacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["scheme_review_tasks.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
        sa.UniqueConstraint("task_id", "artifact_kind", "version_no", name="uq_task_artifact_version"),
    )
    op.create_index("ix_document_artifacts_task_id", "document_artifacts", ["task_id"])
    op.create_index("ix_document_artifacts_review_round_id", "document_artifacts", ["review_round_id"])
    op.create_index("ix_document_artifacts_artifact_kind", "document_artifacts", ["artifact_kind"])
    op.create_index("ix_document_artifacts_supersedes_artifact_id", "document_artifacts", ["supersedes_artifact_id"])
    op.create_index("ix_document_artifacts_created_by_id", "document_artifacts", ["created_by_id"])


def downgrade() -> None:
    op.drop_index("ix_document_artifacts_created_by_id", table_name="document_artifacts")
    op.drop_index("ix_document_artifacts_supersedes_artifact_id", table_name="document_artifacts")
    op.drop_index("ix_document_artifacts_artifact_kind", table_name="document_artifacts")
    op.drop_index("ix_document_artifacts_review_round_id", table_name="document_artifacts")
    op.drop_index("ix_document_artifacts_task_id", table_name="document_artifacts")
    op.drop_table("document_artifacts")
