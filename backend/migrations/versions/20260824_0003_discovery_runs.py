"""persist user-triggered fund discovery runs

Revision ID: 20260824_0003
Revises: 20260824_0002
Create Date: 2026-08-24
"""

import sqlalchemy as sa
from alembic import op

revision = "20260824_0003"
down_revision = "20260824_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "v2_discovery_runs" in inspector.get_table_names():
        return
    op.create_table(
        "v2_discovery_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("snapshot_id", sa.Integer(), sa.ForeignKey("v2_holding_snapshots.id"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rule_version", sa.String(length=32), nullable=False),
        sa.Column("rule_hash", sa.String(length=64), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_v2_discovery_runs_snapshot_id", "v2_discovery_runs", ["snapshot_id"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "v2_discovery_runs" in inspector.get_table_names():
        op.drop_index("ix_v2_discovery_runs_snapshot_id", table_name="v2_discovery_runs")
        op.drop_table("v2_discovery_runs")
