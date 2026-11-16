"""API tokens.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("operator_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["operator_id"], ["soc_operators.operator_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_api_tokens_expires_at", "api_tokens", ["expires_at"]
    )
    op.create_index(
        "ix_api_tokens_operator_id", "api_tokens", ["operator_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_api_tokens_operator_id", table_name="api_tokens")
    op.drop_index("ix_api_tokens_expires_at", table_name="api_tokens")
    op.drop_table("api_tokens")
