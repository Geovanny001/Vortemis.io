"""Refresh tokens and shared login attempts.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "api_tokens",
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "api_tokens",
        sa.Column("previous_refresh_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "api_tokens",
        sa.Column(
            "refresh_expires_at", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.create_index(
        "ix_api_tokens_refresh_token_hash",
        "api_tokens",
        ["refresh_token_hash"],
        unique=True,
    )
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_login_attempts_username", "login_attempts", ["username"]
    )
    op.create_index(
        "ix_login_attempts_attempted_at",
        "login_attempts",
        ["attempted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_login_attempts_attempted_at", table_name="login_attempts")
    op.drop_index("ix_login_attempts_username", table_name="login_attempts")
    op.drop_table("login_attempts")
    op.drop_index("ix_api_tokens_refresh_token_hash", table_name="api_tokens")
    op.drop_column("api_tokens", "refresh_expires_at")
    op.drop_column("api_tokens", "previous_refresh_hash")
    op.drop_column("api_tokens", "refresh_token_hash")
