"""separate review outcome, completeness and human review state

Revision ID: 024
Revises: 023
Create Date: 2026-08-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scheme_review_tasks",
        sa.Column(
            "review_conclusion",
            sa.String(length=32),
            nullable=False,
            server_default="not_reviewed",
        ),
    )
    op.add_column(
        "scheme_review_tasks",
        sa.Column(
            "completeness_status",
            sa.String(length=32),
            nullable=False,
            server_default="unavailable",
        ),
    )
    op.add_column(
        "scheme_review_tasks",
        sa.Column(
            "human_status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
    )
    op.create_index(
        op.f("ix_scheme_review_tasks_review_conclusion"),
        "scheme_review_tasks",
        ["review_conclusion"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scheme_review_tasks_completeness_status"),
        "scheme_review_tasks",
        ["completeness_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scheme_review_tasks_human_status"),
        "scheme_review_tasks",
        ["human_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_scheme_review_tasks_human_status"), table_name="scheme_review_tasks")
    op.drop_index(
        op.f("ix_scheme_review_tasks_completeness_status"),
        table_name="scheme_review_tasks",
    )
    op.drop_index(
        op.f("ix_scheme_review_tasks_review_conclusion"),
        table_name="scheme_review_tasks",
    )
    op.drop_column("scheme_review_tasks", "human_status")
    op.drop_column("scheme_review_tasks", "completeness_status")
    op.drop_column("scheme_review_tasks", "review_conclusion")
