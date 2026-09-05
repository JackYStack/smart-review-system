"""bind OnlyOffice callbacks to edit sessions

Revision ID: 029
Revises: 028
Create Date: 2026-08-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "029"
down_revision: Union[str, None] = "028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "onlyoffice_edit_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("document_key", sa.String(length=64), nullable=False),
        sa.Column("source_object_key", sa.String(length=512), nullable=False),
        sa.Column("current_object_key", sa.String(length=512), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["scheme_review_tasks.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_key"),
    )
    op.create_index("ix_onlyoffice_edit_sessions_task_id", "onlyoffice_edit_sessions", ["task_id"])
    op.create_index("ix_onlyoffice_edit_sessions_created_by_id", "onlyoffice_edit_sessions", ["created_by_id"])
    op.create_index("ix_onlyoffice_edit_sessions_expires_at", "onlyoffice_edit_sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_onlyoffice_edit_sessions_expires_at", table_name="onlyoffice_edit_sessions")
    op.drop_index("ix_onlyoffice_edit_sessions_created_by_id", table_name="onlyoffice_edit_sessions")
    op.drop_index("ix_onlyoffice_edit_sessions_task_id", table_name="onlyoffice_edit_sessions")
    op.drop_table("onlyoffice_edit_sessions")
