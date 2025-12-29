"""add admin users table

Revision ID: d1f2731d83a1
Revises: cb36b9f5d9f1
Create Date: 2025-12-29 17:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d1f2731d83a1"
down_revision: Union[str, None] = "cb36b9f5d9f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("user_id", name="uq_admin_users_user_id"),
    )
    op.create_index("ix_admin_users_user_id", "admin_users", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_admin_users_user_id", table_name="admin_users")
    op.drop_table("admin_users")

