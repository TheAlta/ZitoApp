"""store generated course images and their lesson ownership

Revision ID: 20261007_0018
Revises: 20260912_0017
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261007_0018"
down_revision: Union[str, None] = "20260912_0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "course_generated_images",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_version_id", sa.Integer(), sa.ForeignKey("course_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_module_id", sa.Integer(), sa.ForeignKey("course_modules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_content_id", sa.Integer(), sa.ForeignKey("course_module_stage_contents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.String(length=80), nullable=False, unique=True),
        sa.Column("mime_type", sa.String(length=40), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("size", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_course_generated_images_stage_created", "course_generated_images", ["stage_content_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_course_generated_images_stage_created", table_name="course_generated_images")
    op.drop_table("course_generated_images")
