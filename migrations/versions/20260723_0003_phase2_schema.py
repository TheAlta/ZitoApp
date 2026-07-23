"""phase 2 course cms and learning profile schema

Revision ID: 20260723_0003
Revises: 20260714_0002
Create Date: 2026-07-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260723_0003"
down_revision: Union[str, None] = "20260714_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False, unique=True),
        sa.Column("domain", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "course_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="seed"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("course_id", "version_number", name="uq_course_versions_course_version"),
    )
    op.create_table(
        "course_kb_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags", sa.String(length=255), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=False, server_default="seed"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "course_stage_contents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_version_id", sa.Integer(), sa.ForeignKey("course_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_number", sa.Integer(), nullable=False),
        sa.Column("stage_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="approved"),
        sa.Column("ai_generation_status", sa.String(length=40), nullable=False, server_default="seeded"),
        sa.Column("review_status", sa.String(length=40), nullable=False, server_default="approved"),
        sa.Column("reviewed_by", sa.String(length=100), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("course_version_id", "stage_number", name="uq_course_stage_version_number"),
    )
    op.create_table(
        "user_profiles_v2",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("age_range", sa.String(length=80), nullable=True),
        sa.Column("work_status", sa.String(length=120), nullable=True),
        sa.Column("work_domain", sa.String(length=255), nullable=True),
        sa.Column("referral_source", sa.String(length=120), nullable=True),
        sa.Column("daily_study_minutes", sa.Integer(), nullable=True),
        sa.Column("learning_goal", sa.String(length=255), nullable=True),
        sa.Column("experience_level", sa.String(length=80), nullable=True),
        sa.Column("preferred_learning_style", sa.String(length=120), nullable=True),
        sa.Column("learning_blocker", sa.String(length=255), nullable=True),
        sa.Column("commitment_level", sa.String(length=80), nullable=True),
        sa.Column("target_skill", sa.String(length=255), nullable=True),
        sa.Column("interested_domains", sa.JSON(), nullable=True),
        sa.Column("decision_factors", sa.JSON(), nullable=True),
        sa.Column("notification_channel", sa.String(length=80), nullable=True),
        sa.Column("reminder_frequency", sa.String(length=80), nullable=True),
        sa.Column("recommended_course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("recommended_track_label", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "profile_builder_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_key", sa.String(length=120), nullable=False),
        sa.Column("answer_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "step_key", name="uq_profile_builder_user_step"),
    )
    op.create_table(
        "user_course_enrollments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_version_id", sa.Integer(), sa.ForeignKey("course_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("current_stage_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("progress_percentage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "course_version_id", name="uq_user_course_version_enrollment"),
    )
    op.create_table(
        "user_stage_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enrollment_id", sa.Integer(), sa.ForeignKey("user_course_enrollments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="not_started"),
        sa.Column("response_json", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("enrollment_id", "stage_number", name="uq_user_stage_progress_enrollment_stage"),
    )
    op.create_table(
        "exams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_version_id", sa.Integer(), sa.ForeignKey("course_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("questions_json", sa.JSON(), nullable=False),
        sa.Column("passing_score", sa.Integer(), nullable=False, server_default="70"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="published"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "exam_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exam_id", sa.Integer(), sa.ForeignKey("exams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enrollment_id", sa.Integer(), sa.ForeignKey("user_course_enrollments.id", ondelete="CASCADE"), nullable=True),
        sa.Column("answers_json", sa.JSON(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("grading_feedback", sa.Text(), nullable=True),
        sa.Column("graded_by_ai_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "certificates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_version_id", sa.Integer(), sa.ForeignKey("course_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exam_attempt_id", sa.Integer(), sa.ForeignKey("exam_attempts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("certificate_number", sa.String(length=120), nullable=False, unique=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="issued"),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("certificates")
    op.drop_table("exam_attempts")
    op.drop_table("exams")
    op.drop_table("user_stage_progress")
    op.drop_table("user_course_enrollments")
    op.drop_table("profile_builder_answers")
    op.drop_table("user_profiles_v2")
    op.drop_table("course_stage_contents")
    op.drop_table("course_kb_documents")
    op.drop_table("course_versions")
    op.drop_table("courses")
