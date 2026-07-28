"""remove legacy onboarding and duplicate user schema

Revision ID: 20260728_0007
Revises: 20260728_0006
Create Date: 2026-07-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_0007"
down_revision: Union[str, None] = "20260728_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _require_canonical_phone_identity() -> None:
    missing_phone = op.get_bind().execute(
        sa.text("SELECT count(*) FROM users WHERE phone IS NULL OR trim(phone) = ''")
    ).scalar_one()
    if missing_phone:
        raise RuntimeError(
            "Legacy cleanup stopped: every remaining user must have a verified phone. "
            "Resolve or remove legacy users before upgrading."
        )


def upgrade() -> None:
    _require_canonical_phone_identity()
    dialect = op.get_bind().dialect.name

    # These tables were replaced by user_profiles and the course-scoped learning schema.
    op.drop_table("answers")
    op.drop_table("questions")
    op.drop_table("user_progress")
    op.drop_table("knowledge_documents")
    op.drop_table("profile_builder_answers")
    op.drop_table("user_profiles_v2")

    if dialect == "sqlite":
        with op.batch_alter_table("users") as batch:
            batch.alter_column(
                "phone",
                existing_type=sa.String(length=20),
                nullable=False,
            )
            batch.drop_column("profession")
            batch.drop_column("username")
            batch.drop_column("full_name")
    else:
        op.alter_column(
            "users",
            "phone",
            existing_type=sa.String(length=20),
            nullable=False,
        )
        op.drop_column("users", "profession")
        op.drop_column("users", "username")
        op.drop_column("users", "full_name")


def downgrade() -> None:
    dialect = op.get_bind().dialect.name

    if dialect == "sqlite":
        with op.batch_alter_table("users") as batch:
            batch.add_column(sa.Column("full_name", sa.String(length=255), nullable=True))
            batch.add_column(sa.Column("username", sa.String(length=100), nullable=True))
            batch.add_column(sa.Column("profession", sa.String(length=255), nullable=True))
            batch.alter_column(
                "phone",
                existing_type=sa.String(length=20),
                nullable=True,
            )
    else:
        op.add_column("users", sa.Column("full_name", sa.String(length=255), nullable=True))
        op.add_column("users", sa.Column("username", sa.String(length=100), nullable=True))
        op.add_column("users", sa.Column("profession", sa.String(length=255), nullable=True))
        op.alter_column(
            "users",
            "phone",
            existing_type=sa.String(length=20),
            nullable=True,
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
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "profile_builder_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_key", sa.String(length=120), nullable=False),
        sa.Column("answer_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "step_key", name="uq_profile_builder_user_step"),
    )
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "user_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("percentage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_lesson", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=80), nullable=False, unique=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("validation_reason", sa.Text(), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
