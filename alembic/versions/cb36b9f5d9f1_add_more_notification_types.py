"""add more notification types

Revision ID: cb36b9f5d9f1
Revises: 04ec92c79304
Create Date: 2025-12-29 16:11:26.247624

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cb36b9f5d9f1'
down_revision: Union[str, None] = '04ec92c79304'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'proxy_expired'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'proxy_auto_prolong_success'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'proxy_auto_prolong_failed'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'admin_alert'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
