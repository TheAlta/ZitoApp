"""add immutable final-exam attempts and certificate snapshots

Revision ID: 20260820_0016
Revises: 20260819_0015
Create Date: 2026-08-20

Existing exam records remain valid. New fields are additive so an old attempt
or certificate can still be read while all newly issued records are immutable
snapshots of the learner-facing assessment and certificate data.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260820_0016"
down_revision: Union[str, None] = "20260819_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def _upgrade_exam_attempts(batch) -> None:
    batch.add_column(sa.Column("questions_snapshot_json", sa.JSON(), nullable=True))
    batch.add_column(sa.Column("generation_json", sa.JSON(), nullable=True))
    batch.add_column(
        sa.Column("status", sa.String(length=40), nullable=False, server_default="in_progress")
    )
    batch.add_column(sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    batch.add_column(sa.Column("grading_json", sa.JSON(), nullable=True))
    batch.create_check_constraint(
        "ck_exam_attempts_score",
        "score IS NULL OR (score >= 0 AND score <= 100)",
    )
    batch.create_index(
        "ix_exam_attempts_enrollment_status_created",
        ["enrollment_id", "status", "created_at"],
    )


def _upgrade_certificates(batch) -> None:
    batch.add_column(sa.Column("recipient_name", sa.String(length=100), nullable=True))
    batch.add_column(sa.Column("course_title", sa.String(length=255), nullable=True))
    batch.add_column(sa.Column("course_version_number", sa.Integer(), nullable=True))
    batch.add_column(sa.Column("score", sa.Integer(), nullable=True))
    batch.add_column(sa.Column("passing_score", sa.Integer(), nullable=True))
    batch.create_unique_constraint(
        "uq_certificates_user_course_version",
        ["user_id", "course_version_id"],
    )
    batch.create_check_constraint(
        "ck_certificates_score",
        "score IS NULL OR (score >= 0 AND score <= 100)",
    )
    batch.create_check_constraint(
        "ck_certificates_passing_score",
        "passing_score IS NULL OR (passing_score >= 0 AND passing_score <= 100)",
    )


def upgrade() -> None:
    if _is_sqlite():
        with op.batch_alter_table("exam_attempts") as batch:
            _upgrade_exam_attempts(batch)
        with op.batch_alter_table("certificates") as batch:
            _upgrade_certificates(batch)
        return

    op.add_column("exam_attempts", sa.Column("questions_snapshot_json", sa.JSON(), nullable=True))
    op.add_column("exam_attempts", sa.Column("generation_json", sa.JSON(), nullable=True))
    op.add_column(
        "exam_attempts",
        sa.Column("status", sa.String(length=40), nullable=False, server_default="in_progress"),
    )
    op.add_column("exam_attempts", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("exam_attempts", sa.Column("grading_json", sa.JSON(), nullable=True))
    op.create_check_constraint(
        "ck_exam_attempts_score",
        "exam_attempts",
        "score IS NULL OR (score >= 0 AND score <= 100)",
    )
    op.create_index(
        "ix_exam_attempts_enrollment_status_created",
        "exam_attempts",
        ["enrollment_id", "status", "created_at"],
    )

    op.add_column("certificates", sa.Column("recipient_name", sa.String(length=100), nullable=True))
    op.add_column("certificates", sa.Column("course_title", sa.String(length=255), nullable=True))
    op.add_column("certificates", sa.Column("course_version_number", sa.Integer(), nullable=True))
    op.add_column("certificates", sa.Column("score", sa.Integer(), nullable=True))
    op.add_column("certificates", sa.Column("passing_score", sa.Integer(), nullable=True))
    op.create_unique_constraint(
        "uq_certificates_user_course_version",
        "certificates",
        ["user_id", "course_version_id"],
    )
    op.create_check_constraint(
        "ck_certificates_score",
        "certificates",
        "score IS NULL OR (score >= 0 AND score <= 100)",
    )
    op.create_check_constraint(
        "ck_certificates_passing_score",
        "certificates",
        "passing_score IS NULL OR (passing_score >= 0 AND passing_score <= 100)",
    )


def _downgrade_exam_attempts(batch) -> None:
    batch.drop_index("ix_exam_attempts_enrollment_status_created")
    batch.drop_constraint("ck_exam_attempts_score", type_="check")
    batch.drop_column("grading_json")
    batch.drop_column("submitted_at")
    batch.drop_column("status")
    batch.drop_column("generation_json")
    batch.drop_column("questions_snapshot_json")


def _downgrade_certificates(batch) -> None:
    batch.drop_constraint("ck_certificates_passing_score", type_="check")
    batch.drop_constraint("ck_certificates_score", type_="check")
    batch.drop_constraint("uq_certificates_user_course_version", type_="unique")
    batch.drop_column("passing_score")
    batch.drop_column("score")
    batch.drop_column("course_version_number")
    batch.drop_column("course_title")
    batch.drop_column("recipient_name")


def downgrade() -> None:
    if _is_sqlite():
        with op.batch_alter_table("certificates") as batch:
            _downgrade_certificates(batch)
        with op.batch_alter_table("exam_attempts") as batch:
            _downgrade_exam_attempts(batch)
        return

    op.drop_constraint("ck_certificates_passing_score", "certificates", type_="check")
    op.drop_constraint("ck_certificates_score", "certificates", type_="check")
    op.drop_constraint("uq_certificates_user_course_version", "certificates", type_="unique")
    for column in ("passing_score", "score", "course_version_number", "course_title", "recipient_name"):
        op.drop_column("certificates", column)

    op.drop_index("ix_exam_attempts_enrollment_status_created", table_name="exam_attempts")
    op.drop_constraint("ck_exam_attempts_score", "exam_attempts", type_="check")
    for column in ("grading_json", "submitted_at", "status", "generation_json", "questions_snapshot_json"):
        op.drop_column("exam_attempts", column)
