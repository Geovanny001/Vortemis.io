"""Initial schema.

Revision ID: 0001
Revises:
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dim_conn_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=16), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "dim_mitre_tactics",
        sa.Column("tactic_id", sa.Integer(), nullable=False),
        sa.Column("mitre_id", sa.String(length=15), nullable=False),
        sa.Column("tactic_name", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("tactic_id"),
        sa.UniqueConstraint("mitre_id"),
    )
    op.create_table(
        "dim_protocols",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=16), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "ingestion_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_path", sa.String(length=512), nullable=False),
        sa.Column("device", sa.BigInteger(), nullable=False),
        sa.Column("inode", sa.BigInteger(), nullable=False),
        sa.Column("offset", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_path"),
    )
    op.create_table(
        "soc_operators",
        sa.Column("operator_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint("operator_id"),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "fact_network_flows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("flow_id", sa.String(length=36), nullable=False),
        sa.Column("src_ip", sa.String(length=64), nullable=False),
        sa.Column("dst_ip", sa.String(length=64), nullable=False),
        sa.Column("src_port", sa.Integer(), nullable=False),
        sa.Column("dst_port", sa.Integer(), nullable=False),
        sa.Column("protocol_id", sa.Integer(), nullable=False),
        sa.Column("conn_state_id", sa.Integer(), nullable=True),
        sa.Column("tactic_id", sa.Integer(), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("orig_bytes", sa.BigInteger(), nullable=False),
        sa.Column("resp_bytes", sa.BigInteger(), nullable=False),
        sa.Column("duration", sa.Float(), nullable=False),
        sa.Column("iat_ms", sa.Float(), nullable=True),
        sa.Column("anomaly_probability", sa.Float(), nullable=False),
        sa.Column("is_anomaly", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["conn_state_id"], ["dim_conn_states.id"]),
        sa.ForeignKeyConstraint(["protocol_id"], ["dim_protocols.id"]),
        sa.ForeignKeyConstraint(["tactic_id"], ["dim_mitre_tactics.tactic_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("flow_id"),
    )
    op.create_index(
        "ix_fact_network_flows_anomaly_probability",
        "fact_network_flows",
        ["anomaly_probability"],
    )
    op.create_index(
        "ix_fact_network_flows_is_anomaly",
        "fact_network_flows",
        ["is_anomaly"],
    )
    op.create_index(
        "ix_fact_network_flows_src_ip",
        "fact_network_flows",
        ["src_ip"],
    )
    op.create_index(
        "ix_fact_network_flows_tactic_id",
        "fact_network_flows",
        ["tactic_id"],
    )
    op.create_index(
        "ix_fact_network_flows_ts",
        "fact_network_flows",
        ["ts"],
    )


def downgrade() -> None:
    op.drop_index("ix_fact_network_flows_ts", table_name="fact_network_flows")
    op.drop_index("ix_fact_network_flows_tactic_id", table_name="fact_network_flows")
    op.drop_index("ix_fact_network_flows_src_ip", table_name="fact_network_flows")
    op.drop_index("ix_fact_network_flows_is_anomaly", table_name="fact_network_flows")
    op.drop_index(
        "ix_fact_network_flows_anomaly_probability",
        table_name="fact_network_flows",
    )
    op.drop_table("fact_network_flows")
    op.drop_table("soc_operators")
    op.drop_table("ingestion_state")
    op.drop_table("dim_protocols")
    op.drop_table("dim_mitre_tactics")
    op.drop_table("dim_conn_states")
