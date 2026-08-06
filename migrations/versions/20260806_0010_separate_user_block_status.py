"""separate user blocking from soft deletion

Revision ID: 20260806_0010
Revises: 20260806_0009
Create Date: 2026-08-06

Soft-deleted users retain their identity and may reactivate it through a
successful phone OTP. Blocking is an independent administrative state.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260806_0010"
down_revision: Union[str, None] = "20260806_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    column = sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True)
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("users") as batch:
            batch.add_column(column)
            batch.create_index("ix_users_blocked_at", ["blocked_at"])
    else:
        op.add_column("users", column)
        op.create_index("ix_users_blocked_at", "users", ["blocked_at"])


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("users") as batch:
            batch.drop_index("ix_users_blocked_at")
            batch.drop_column("blocked_at")
    else:
        op.drop_index("ix_users_blocked_at", table_name="users")
        op.drop_column("users", "blocked_at")
