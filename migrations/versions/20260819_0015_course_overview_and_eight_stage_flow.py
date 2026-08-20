"""add versioned course overview and eight-stage learning-flow support

Revision ID: 20260819_0015
Revises: 20260819_0014
Create Date: 2026-08-19

This revision is additive. Existing course versions and learner progress keep
their original contracts; a new published version can declare a different
number of module stages and an end-of-course final-exam gate.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260819_0015"
down_revision: Union[str, None] = "20260819_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def _add_course_version_columns_sqlite(batch) -> None:
    batch.add_column(sa.Column("overview_json", sa.JSON(), nullable=True))
    batch.add_column(sa.Column("module_stage_count", sa.Integer(), nullable=True))
    batch.add_column(
        sa.Column(
            "requires_final_exam",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        )
    )
    batch.create_check_constraint(
        "ck_course_versions_module_stage_count",
        "module_stage_count IS NULL OR module_stage_count >= 1",
    )


def _add_module_stage_columns_sqlite(batch) -> None:
    batch.add_column(sa.Column("evaluation_config_json", sa.JSON(), nullable=True))


def _add_progress_columns_sqlite(batch) -> None:
    batch.add_column(sa.Column("score", sa.Integer(), nullable=True))
    batch.add_column(sa.Column("evaluation_json", sa.JSON(), nullable=True))
    batch.add_column(
        sa.Column(
            "assessment_attempt_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        )
    )
    batch.add_column(sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True))
    batch.add_column(sa.Column("generated_content_json", sa.JSON(), nullable=True))
    batch.add_column(sa.Column("generated_content_sources_json", sa.JSON(), nullable=True))
    batch.add_column(sa.Column("generated_content_model", sa.String(length=120), nullable=True))
    batch.add_column(sa.Column("generated_content_prompt_version", sa.String(length=80), nullable=True))
    batch.add_column(sa.Column("generated_content_at", sa.DateTime(timezone=True), nullable=True))
    batch.create_check_constraint(
        "ck_user_module_stage_progress_score",
        "score IS NULL OR (score >= 0 AND score <= 100)",
    )
    batch.create_check_constraint(
        "ck_user_module_stage_progress_attempt_count",
        "assessment_attempt_count >= 0",
    )


def _mark_existing_module_versions_as_twenty_stage() -> None:
    op.execute(
        """
        UPDATE course_versions
        SET module_stage_count = 20
        WHERE module_stage_count IS NULL
          AND EXISTS (
              SELECT 1
              FROM course_modules
              WHERE course_modules.course_version_id = course_versions.id
          )
        """
    )


def upgrade() -> None:
    if _is_sqlite():
        with op.batch_alter_table("course_versions") as batch:
            _add_course_version_columns_sqlite(batch)
        with op.batch_alter_table("course_module_stage_contents") as batch:
            _add_module_stage_columns_sqlite(batch)
        with op.batch_alter_table("user_module_stage_progress") as batch:
            _add_progress_columns_sqlite(batch)
        _mark_existing_module_versions_as_twenty_stage()
        return

    op.add_column("course_versions", sa.Column("overview_json", sa.JSON(), nullable=True))
    op.add_column("course_versions", sa.Column("module_stage_count", sa.Integer(), nullable=True))
    op.add_column(
        "course_versions",
        sa.Column("requires_final_exam", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_check_constraint(
        "ck_course_versions_module_stage_count",
        "course_versions",
        "module_stage_count IS NULL OR module_stage_count >= 1",
    )
    op.add_column("course_module_stage_contents", sa.Column("evaluation_config_json", sa.JSON(), nullable=True))
    op.add_column("user_module_stage_progress", sa.Column("score", sa.Integer(), nullable=True))
    op.add_column("user_module_stage_progress", sa.Column("evaluation_json", sa.JSON(), nullable=True))
    op.add_column(
        "user_module_stage_progress",
        sa.Column("assessment_attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("user_module_stage_progress", sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("user_module_stage_progress", sa.Column("generated_content_json", sa.JSON(), nullable=True))
    op.add_column("user_module_stage_progress", sa.Column("generated_content_sources_json", sa.JSON(), nullable=True))
    op.add_column("user_module_stage_progress", sa.Column("generated_content_model", sa.String(length=120), nullable=True))
    op.add_column("user_module_stage_progress", sa.Column("generated_content_prompt_version", sa.String(length=80), nullable=True))
    op.add_column("user_module_stage_progress", sa.Column("generated_content_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_user_module_stage_progress_score",
        "user_module_stage_progress",
        "score IS NULL OR (score >= 0 AND score <= 100)",
    )
    op.create_check_constraint(
        "ck_user_module_stage_progress_attempt_count",
        "user_module_stage_progress",
        "assessment_attempt_count >= 0",
    )
    _mark_existing_module_versions_as_twenty_stage()


def _drop_progress_columns_sqlite(batch) -> None:
    batch.drop_constraint("ck_user_module_stage_progress_attempt_count", type_="check")
    batch.drop_constraint("ck_user_module_stage_progress_score", type_="check")
    batch.drop_column("generated_content_at")
    batch.drop_column("generated_content_prompt_version")
    batch.drop_column("generated_content_model")
    batch.drop_column("generated_content_sources_json")
    batch.drop_column("generated_content_json")
    batch.drop_column("evaluated_at")
    batch.drop_column("assessment_attempt_count")
    batch.drop_column("evaluation_json")
    batch.drop_column("score")


def _drop_course_version_columns_sqlite(batch) -> None:
    batch.drop_constraint("ck_course_versions_module_stage_count", type_="check")
    batch.drop_column("requires_final_exam")
    batch.drop_column("module_stage_count")
    batch.drop_column("overview_json")


def downgrade() -> None:
    if _is_sqlite():
        with op.batch_alter_table("user_module_stage_progress") as batch:
            _drop_progress_columns_sqlite(batch)
        with op.batch_alter_table("course_module_stage_contents") as batch:
            batch.drop_column("evaluation_config_json")
        with op.batch_alter_table("course_versions") as batch:
            _drop_course_version_columns_sqlite(batch)
        return

    op.drop_constraint(
        "ck_user_module_stage_progress_attempt_count",
        "user_module_stage_progress",
        type_="check",
    )
    op.drop_constraint(
        "ck_user_module_stage_progress_score",
        "user_module_stage_progress",
        type_="check",
    )
    for column in (
        "generated_content_at",
        "generated_content_prompt_version",
        "generated_content_model",
        "generated_content_sources_json",
        "generated_content_json",
        "evaluated_at",
        "assessment_attempt_count",
        "evaluation_json",
        "score",
    ):
        op.drop_column("user_module_stage_progress", column)
    op.drop_column("course_module_stage_contents", "evaluation_config_json")
    op.drop_constraint("ck_course_versions_module_stage_count", "course_versions", type_="check")
    op.drop_column("course_versions", "requires_final_exam")
    op.drop_column("course_versions", "module_stage_count")
    op.drop_column("course_versions", "overview_json")
