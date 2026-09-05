"""add task idempotency, leases, cancellation and multi-file attachments

Revision ID: 027
Revises: 026
Create Date: 2026-08-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("scheme_review_tasks", sa.Column("idempotency_key", sa.String(length=64), nullable=True))
    op.add_column("scheme_review_tasks", sa.Column("priority", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("scheme_review_tasks", sa.Column("attempt_no", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("scheme_review_tasks", sa.Column("retry_of_task_id", sa.Integer(), nullable=True))
    op.add_column("scheme_review_tasks", sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("scheme_review_tasks", sa.Column("lease_owner", sa.String(length=128), nullable=True))
    op.add_column("scheme_review_tasks", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_review_tasks_retry_of_task",
        "scheme_review_tasks",
        "scheme_review_tasks",
        ["retry_of_task_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_review_task_idempotency",
        "scheme_review_tasks",
        ["user_id", "idempotency_key"],
    )
    for column in (
        "idempotency_key",
        "priority",
        "retry_of_task_id",
        "lease_expires_at",
    ):
        op.create_index(
            op.f(f"ix_scheme_review_tasks_{column}"),
            "scheme_review_tasks",
            [column],
            unique=False,
        )

    op.create_table(
        "review_attachments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("minio_bucket", sa.String(length=128), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("scan_status", sa.String(length=32), nullable=False, server_default="not_scanned"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["scheme_review_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
    )
    op.create_index(op.f("ix_review_attachments_task_id"), "review_attachments", ["task_id"], unique=False)
    op.create_index(op.f("ix_review_attachments_kind"), "review_attachments", ["kind"], unique=False)
    op.create_index(op.f("ix_review_attachments_scan_status"), "review_attachments", ["scan_status"], unique=False)


def downgrade() -> None:
    op.drop_table("review_attachments")
    for column in (
        "lease_expires_at",
        "retry_of_task_id",
        "priority",
        "idempotency_key",
    ):
        op.drop_index(op.f(f"ix_scheme_review_tasks_{column}"), table_name="scheme_review_tasks")
    op.drop_constraint("uq_review_task_idempotency", "scheme_review_tasks", type_="unique")
    op.drop_constraint("fk_review_tasks_retry_of_task", "scheme_review_tasks", type_="foreignkey")
    for column in (
        "lease_expires_at",
        "lease_owner",
        "cancel_requested_at",
        "retry_of_task_id",
        "attempt_no",
        "priority",
        "idempotency_key",
    ):
        op.drop_column("scheme_review_tasks", column)
