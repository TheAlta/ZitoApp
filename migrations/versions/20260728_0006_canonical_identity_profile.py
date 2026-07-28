"""add canonical identity, profile, and user sessions

Revision ID: 20260728_0006
Revises: 20260727_0005
Create Date: 2026-07-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_0006"
down_revision: Union[str, None] = "20260727_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _preflight() -> None:
    connection = op.get_bind()
    duplicate_phone = connection.execute(
        sa.text(
            """
            SELECT phone
            FROM users
            WHERE phone IS NOT NULL
            GROUP BY phone
            HAVING count(*) > 1
            LIMIT 1
            """
        )
    ).scalar_one_or_none()
    if duplicate_phone is not None:
        raise RuntimeError("Canonical identity migration stopped: duplicate user phones exist.")


def upgrade() -> None:
    _preflight()
    dialect = op.get_bind().dialect.name

    op.add_column("users", sa.Column("display_name", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    if dialect == "postgresql":
        op.execute(
            """
            UPDATE users
            SET display_name = CASE
                WHEN username IS NOT NULL
                     AND trim(username) <> ''
                     AND username !~ '^09[0-9]{9}$'
                    THEN left(trim(username), 100)
                WHEN full_name IS NOT NULL AND trim(full_name) <> ''
                    THEN left(trim(full_name), 100)
                ELSE 'User ' || id::text
            END
            """
        )
    else:
        op.execute(
            """
            UPDATE users
            SET display_name = CASE
                WHEN username IS NOT NULL AND trim(username) <> ''
                    THEN substr(trim(username), 1, 100)
                WHEN full_name IS NOT NULL AND trim(full_name) <> ''
                    THEN substr(trim(full_name), 1, 100)
                ELSE 'User ' || CAST(id AS TEXT)
            END
            """
        )
    op.execute(
        """
        UPDATE users
        SET phone_verified_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP),
            last_login_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
        WHERE phone IS NOT NULL
        """
    )
    if dialect == "sqlite":
        with op.batch_alter_table("users") as batch:
            batch.alter_column(
                "display_name",
                existing_type=sa.String(length=100),
                nullable=False,
            )
    else:
        op.alter_column("users", "display_name", existing_type=sa.String(length=100), nullable=False)
    op.create_index("ix_users_display_name", "users", ["display_name"])
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"])

    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("work_or_study_field", sa.String(length=255), nullable=True),
        sa.Column("education_level", sa.String(length=80), nullable=True),
        sa.Column("learning_goal_interests", sa.Text(), nullable=True),
        sa.Column("ai_familiarity_level", sa.String(length=50), nullable=True),
        sa.Column("daily_learning_minutes", sa.Integer(), nullable=True),
        sa.Column("preferred_career_path", sa.String(length=255), nullable=True),
        sa.Column("referral_source", sa.String(length=120), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "daily_learning_minutes IS NULL OR "
            "(daily_learning_minutes >= 0 AND daily_learning_minutes <= 1440)",
            name="ck_user_profiles_daily_learning_minutes",
        ),
    )
    insert_keyword = "INSERT OR IGNORE" if dialect == "sqlite" else "INSERT"
    conflict_clause = "" if dialect == "sqlite" else "ON CONFLICT (user_id) DO NOTHING"
    op.execute(
        f"""
        {insert_keyword} INTO user_profiles (
            user_id,
            work_or_study_field,
            learning_goal_interests,
            daily_learning_minutes,
            referral_source,
            created_at,
            updated_at
        )
        SELECT
            user_id,
            NULLIF(trim(work_domain), ''),
            NULLIF(trim(learning_goal), ''),
            daily_study_minutes,
            NULLIF(trim(referral_source), ''),
            created_at,
            updated_at
        FROM user_profiles_v2
        {conflict_clause}
        """
    )

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
    )
    op.create_index(
        "ix_user_sessions_user_active",
        "user_sessions",
        ["user_id", "revoked_at", "expires_at"],
    )

    op.add_column(
        "phone_otp_codes",
        sa.Column("purpose", sa.String(length=30), server_default="login", nullable=False),
    )
    op.create_index(
        "ix_phone_otp_latest",
        "phone_otp_codes",
        ["phone", "purpose", "created_at"],
    )
    op.create_index(
        "ix_phone_otp_cleanup",
        "phone_otp_codes",
        ["expires_at", "consumed_at"],
    )


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    op.drop_index("ix_phone_otp_cleanup", table_name="phone_otp_codes")
    op.drop_index("ix_phone_otp_latest", table_name="phone_otp_codes")
    op.drop_column("phone_otp_codes", "purpose")

    op.drop_index("ix_user_sessions_user_active", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_table("user_profiles")

    op.drop_index("ix_users_deleted_at", table_name="users")
    op.drop_index("ix_users_display_name", table_name="users")
    if dialect == "sqlite":
        with op.batch_alter_table("users") as batch:
            batch.drop_column("deleted_at")
            batch.drop_column("last_login_at")
            batch.drop_column("phone_verified_at")
            batch.drop_column("display_name")
    else:
        op.drop_column("users", "deleted_at")
        op.drop_column("users", "last_login_at")
        op.drop_column("users", "phone_verified_at")
        op.drop_column("users", "display_name")
