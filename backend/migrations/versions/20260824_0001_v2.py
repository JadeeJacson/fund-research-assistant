"""fund position decision console v2 baseline

Revision ID: 20260824_0001
Revises:
Create Date: 2026-08-24
"""

import sqlalchemy as sa
from alembic import op

from app import models  # noqa: F401
from app.database import Base

revision = "20260824_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    Base.metadata.create_all(bind=connection)
    inspector = sa.inspect(connection)

    fund_columns = {column["name"] for column in inspector.get_columns("v2_funds")}
    missing_fund_columns = {
        "currency": sa.Column("currency", sa.String(length=16), nullable=False, server_default="CNY"),
        "valuation_lag_note": sa.Column("valuation_lag_note", sa.String(length=240), nullable=False, server_default=""),
        "target_risk": sa.Column("target_risk", sa.String(length=80), nullable=False, server_default=""),
        "product_status": sa.Column("product_status", sa.String(length=48), nullable=False, server_default="active"),
        "tracking_error": sa.Column("tracking_error", sa.Float(), nullable=True),
        "return_method": sa.Column("return_method", sa.String(length=120), nullable=False, server_default="cumulative_nav"),
    }
    for name, column in missing_fund_columns.items():
        if name not in fund_columns:
            op.add_column("v2_funds", column)

    import_columns = {column["name"] for column in inspector.get_columns("v2_import_items")}
    if "correction_json" not in import_columns:
        op.add_column(
            "v2_import_items",
            sa.Column("correction_json", sa.Text(), nullable=False, server_default="{}"),
        )


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
