"""enforce enrollment course-version consistency

Revision ID: 20260819_0014
Revises: 20260816_0013
Create Date: 2026-08-19

The application has always populated ``course_id`` and ``course_version_id``
together. This additive revision turns that application convention into a
database guarantee without removing either compatibility column.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260819_0014"
down_revision: Union[str, None] = "20260816_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def _assert_clean_existing_data() -> None:
    bind = op.get_bind()
    course_mismatches = bind.execute(
        sa.text(
            """
            SELECT count(*)
            FROM user_course_enrollments AS enrollment
            JOIN course_versions AS version ON version.id = enrollment.course_version_id
            WHERE enrollment.course_id <> version.course_id
            """
        )
    ).scalar_one()
    if course_mismatches:
        raise RuntimeError(
            "Enrollment integrity migration stopped: "
            f"{course_mismatches} enrollment row(s) point to a version from another course."
        )

    invalid_progress = bind.execute(
        sa.text(
            """
            SELECT count(*)
            FROM user_course_enrollments
            WHERE current_stage_number < 1
               OR progress_percentage < 0
               OR progress_percentage > 100
            """
        )
    ).scalar_one()
    if invalid_progress:
        raise RuntimeError(
            "Enrollment integrity migration stopped: "
            f"{invalid_progress} enrollment row(s) have invalid progress values."
        )


def _upgrade_sqlite() -> None:
    with op.batch_alter_table("user_course_enrollments") as batch:
        batch.create_foreign_key(
            "fk_user_course_enrollments_version_course",
            "course_versions",
            ["course_version_id", "course_id"],
            ["id", "course_id"],
        )
        batch.create_check_constraint(
            "ck_user_course_enrollments_current_stage_number",
            "current_stage_number >= 1",
        )
        batch.create_check_constraint(
            "ck_user_course_enrollments_progress_percentage",
            "progress_percentage >= 0 AND progress_percentage <= 100",
        )
        batch.create_index("ix_user_course_enrollments_user_status", ["user_id", "status"])


def upgrade() -> None:
    _assert_clean_existing_data()
    if _is_sqlite():
        _upgrade_sqlite()
        return

    op.create_foreign_key(
        "fk_user_course_enrollments_version_course",
        "user_course_enrollments",
        "course_versions",
        ["course_version_id", "course_id"],
        ["id", "course_id"],
    )
    op.create_check_constraint(
        "ck_user_course_enrollments_current_stage_number",
        "user_course_enrollments",
        "current_stage_number >= 1",
    )
    op.create_check_constraint(
        "ck_user_course_enrollments_progress_percentage",
        "user_course_enrollments",
        "progress_percentage >= 0 AND progress_percentage <= 100",
    )
    op.create_index(
        "ix_user_course_enrollments_user_status",
        "user_course_enrollments",
        ["user_id", "status"],
    )


def _downgrade_sqlite() -> None:
    with op.batch_alter_table("user_course_enrollments") as batch:
        batch.drop_index("ix_user_course_enrollments_user_status")
        batch.drop_constraint("ck_user_course_enrollments_progress_percentage", type_="check")
        batch.drop_constraint("ck_user_course_enrollments_current_stage_number", type_="check")
        batch.drop_constraint("fk_user_course_enrollments_version_course", type_="foreignkey")


def downgrade() -> None:
    if _is_sqlite():
        _downgrade_sqlite()
        return

    op.drop_index("ix_user_course_enrollments_user_status", table_name="user_course_enrollments")
    op.drop_constraint(
        "ck_user_course_enrollments_progress_percentage",
        "user_course_enrollments",
        type_="check",
    )
    op.drop_constraint(
        "ck_user_course_enrollments_current_stage_number",
        "user_course_enrollments",
        type_="check",
    )
    op.drop_constraint(
        "fk_user_course_enrollments_version_course",
        "user_course_enrollments",
        type_="foreignkey",
    )
