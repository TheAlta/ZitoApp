"""separate user phone login identity

Revision ID: 20260727_0005
Revises: 20260726_0004
Create Date: 2026-07-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260727_0005"
down_revision: Union[str, None] = "20260726_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(length=20), nullable=True))
    op.execute(
        """
        UPDATE users
        SET phone = username
        WHERE username LIKE '09%'
          AND length(username) = 11
          AND id = (
              SELECT min(previous.id)
              FROM users AS previous
              WHERE previous.username = users.username
          )
        """
    )
    op.execute(
        """
        UPDATE users
        SET username = full_name
        WHERE full_name IS NOT NULL
          AND trim(full_name) <> ''
        """
    )
    op.create_index("ix_users_phone", "users", ["phone"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_phone", table_name="users")
    op.drop_column("users", "phone")
