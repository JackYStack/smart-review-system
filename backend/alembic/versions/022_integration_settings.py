"""add runtime integration settings

Revision ID: 022
Revises: 021
Create Date: 2026-08-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "integration_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dify_workflow_enabled", sa.Boolean(), nullable=True),
        sa.Column("dify_workflow_base_url", sa.String(length=512), nullable=True),
        sa.Column("dify_workflow_api_key", sa.String(length=2048), nullable=True),
        sa.Column("dify_workflow_user_prefix", sa.String(length=255), nullable=True),
        sa.Column("dify_workflow_timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("dify_workflow_output_variable", sa.String(length=128), nullable=True),
        sa.Column("dify_workflow_output_format", sa.String(length=32), nullable=True),
        sa.Column("dify_workflow_accept_partial", sa.Boolean(), nullable=True),
        sa.Column("dify_workflow_continue_on_failure", sa.Boolean(), nullable=True),
        sa.Column("paddleocr_api_url", sa.String(length=512), nullable=True),
        sa.Column("paddleocr_api_key", sa.String(length=2048), nullable=True),
        sa.Column("paddleocr_timeout_seconds", sa.Float(), nullable=True),
        sa.Column("paddle_convert_timeout_seconds", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("integration_settings")

