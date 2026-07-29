"""创建 v1 MVP 数据表

Revision ID: 20260729_0001
Revises:
"""

from typing import Sequence

from alembic import op

from app.database import Base
from app import models  # noqa: F401

revision: str = "20260729_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
