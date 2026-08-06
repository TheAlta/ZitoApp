"""store the original daily learning-time response

Revision ID: 20260806_0009
Revises: 20260805_0008
Create Date: 2026-08-06

The raw response is retained for future prompt construction. The existing
daily_learning_minutes field remains an optional normalized convenience value.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260806_0009"
down_revision: Union[str, None] = "20260805_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    column = sa.Column("daily_learning_time_text", sa.String(length=120), nullable=True)
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("user_profiles") as batch:
            batch.add_column(column)
    else:
        op.add_column("user_profiles", column)

    op.get_bind().execute(
        sa.text(
            "UPDATE user_profiles "
            "SET daily_learning_time_text = CAST(daily_learning_minutes AS TEXT) "
            "WHERE daily_learning_time_text IS NULL AND daily_learning_minutes IS NOT NULL"
        )
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("user_profiles") as batch:
            batch.drop_column("daily_learning_time_text")
    else:
        op.drop_column("user_profiles", "daily_learning_time_text")
