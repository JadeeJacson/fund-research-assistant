"""store optional OCR displayed profit

Revision ID: 20260824_0002
Revises: 20260824_0001
Create Date: 2026-08-24
"""

import sqlalchemy as sa
from alembic import op

revision = "20260824_0002"
down_revision = "20260824_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("v2_import_items")}
    if "displayed_profit" not in columns:
        op.add_column("v2_import_items", sa.Column("displayed_profit", sa.Float(), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("v2_import_items")}
    if "displayed_profit" in columns:
        op.drop_column("v2_import_items", "displayed_profit")
