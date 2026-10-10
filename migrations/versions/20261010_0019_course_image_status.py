"""track whether a generated course image is a draft or published to its stage

Revision ID: 20261010_0019
Revises: 20261007_0018
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261010_0019"
down_revision: Union[str, None] = "20261007_0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Images created before this revision were attached to their stage immediately.
    op.add_column(
        "course_generated_images",
        sa.Column("status", sa.String(length=20), server_default="published", nullable=False),
    )
    op.create_index("ix_course_generated_images_status", "course_generated_images", ["status"])


def downgrade() -> None:
    op.drop_index("ix_course_generated_images_status", table_name="course_generated_images")
    op.drop_column("course_generated_images", "status")
