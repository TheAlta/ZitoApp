"""add CMS authoring and generation audit to course versions

Revision ID: 20260912_0017
Revises: 20260820_0016
Create Date: 2026-09-12

The authoring brief belongs to a version, not the mutable course record. This
keeps published learning paths and their audit trail stable when an admin
starts editing the next version.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260912_0017"
down_revision: Union[str, None] = "20260820_0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_columns(batch) -> None:
    batch.add_column(sa.Column("authoring_brief_json", sa.JSON(), nullable=True))
    batch.add_column(
        sa.Column("generation_status", sa.String(length=40), nullable=False, server_default="not_requested")
    )
    batch.add_column(sa.Column("generation_model", sa.String(length=120), nullable=True))
    batch.add_column(sa.Column("generation_prompt_version", sa.String(length=80), nullable=True))
    batch.add_column(sa.Column("generation_error", sa.Text(), nullable=True))
    batch.add_column(sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True))


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("course_versions") as batch:
            _add_columns(batch)
        return
    op.add_column("course_versions", sa.Column("authoring_brief_json", sa.JSON(), nullable=True))
    op.add_column(
        "course_versions",
        sa.Column("generation_status", sa.String(length=40), nullable=False, server_default="not_requested"),
    )
    op.add_column("course_versions", sa.Column("generation_model", sa.String(length=120), nullable=True))
    op.add_column("course_versions", sa.Column("generation_prompt_version", sa.String(length=80), nullable=True))
    op.add_column("course_versions", sa.Column("generation_error", sa.Text(), nullable=True))
    op.add_column("course_versions", sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True))


def _drop_columns(batch) -> None:
    batch.drop_column("generated_at")
    batch.drop_column("generation_error")
    batch.drop_column("generation_prompt_version")
    batch.drop_column("generation_model")
    batch.drop_column("generation_status")
    batch.drop_column("authoring_brief_json")


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("course_versions") as batch:
            _drop_columns(batch)
        return
    for column in (
        "generated_at",
        "generation_error",
        "generation_prompt_version",
        "generation_model",
        "generation_status",
        "authoring_brief_json",
    ):
        op.drop_column("course_versions", column)
