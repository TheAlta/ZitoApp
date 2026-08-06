"""add module-scoped learning structure

Revision ID: 20260805_0008
Revises: 20260728_0007
Create Date: 2026-08-05

This revision is deliberately additive. The prior flat 20-stage schema and all
existing enrollment progress remain available for already-pinned course versions.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260805_0008"
down_revision: Union[str, None] = "20260728_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_course_kb_version_scope() -> None:
    column = sa.Column("course_version_id", sa.Integer(), nullable=True)
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("course_kb_documents") as batch:
            batch.add_column(column)
            batch.create_foreign_key(
                "fk_course_kb_documents_course_version_id",
                "course_versions",
                ["course_version_id"],
                ["id"],
                ondelete="CASCADE",
            )
            batch.create_index("ix_course_kb_documents_course_version_id", ["course_version_id"])
        return

    op.add_column("course_kb_documents", column)
    op.create_foreign_key(
        "fk_course_kb_documents_course_version_id",
        "course_kb_documents",
        "course_versions",
        ["course_version_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_course_kb_documents_course_version_id", "course_kb_documents", ["course_version_id"])


def _drop_course_kb_version_scope() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("course_kb_documents") as batch:
            batch.drop_index("ix_course_kb_documents_course_version_id")
            batch.drop_constraint("fk_course_kb_documents_course_version_id", type_="foreignkey")
            batch.drop_column("course_version_id")
        return

    op.drop_index("ix_course_kb_documents_course_version_id", table_name="course_kb_documents")
    op.drop_constraint("fk_course_kb_documents_course_version_id", "course_kb_documents", type_="foreignkey")
    op.drop_column("course_kb_documents", "course_version_id")


def upgrade() -> None:
    op.create_table(
        "learning_stage_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=80), nullable=False, unique=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("default_order >= 1", name="ck_learning_stage_templates_default_order"),
    )
    op.create_table(
        "course_modules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_version_id", sa.Integer(), sa.ForeignKey("course_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("learning_objectives_json", sa.JSON(), nullable=False),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="approved"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("module_number >= 1", name="ck_course_modules_module_number"),
        sa.UniqueConstraint("course_version_id", "module_number", name="uq_course_modules_version_number"),
    )
    op.create_index(
        "ix_course_modules_version_status_number",
        "course_modules",
        ["course_version_id", "status", "module_number"],
    )
    op.create_table(
        "course_module_stage_contents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_module_id", sa.Integer(), sa.ForeignKey("course_modules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("learning_stage_templates.id"), nullable=False),
        sa.Column("stage_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="approved"),
        sa.Column("ai_generation_status", sa.String(length=40), nullable=False, server_default="seeded"),
        sa.Column("review_status", sa.String(length=40), nullable=False, server_default="approved"),
        sa.Column("reviewed_by", sa.String(length=100), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("stage_number >= 1", name="ck_course_module_stage_contents_stage_number"),
        sa.UniqueConstraint("course_module_id", "stage_number", name="uq_course_module_stage_number"),
        sa.UniqueConstraint("course_module_id", "template_id", name="uq_course_module_template"),
    )
    op.create_index(
        "ix_course_module_stage_contents_module_status_order",
        "course_module_stage_contents",
        ["course_module_id", "status", "stage_number"],
    )

    _add_course_kb_version_scope()
    op.create_table(
        "course_kb_document_modules",
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("course_kb_documents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("course_module_id", sa.Integer(), sa.ForeignKey("course_modules.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_course_kb_document_modules_module", "course_kb_document_modules", ["course_module_id"])

    op.create_table(
        "user_module_stage_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enrollment_id", sa.Integer(), sa.ForeignKey("user_course_enrollments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module_stage_content_id", sa.Integer(), sa.ForeignKey("course_module_stage_contents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="locked"),
        sa.Column("response_json", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("enrollment_id", "module_stage_content_id", name="uq_user_module_stage_progress_item"),
    )
    op.create_index(
        "ix_user_module_stage_progress_enrollment_status",
        "user_module_stage_progress",
        ["enrollment_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_module_stage_progress_enrollment_status", table_name="user_module_stage_progress")
    op.drop_table("user_module_stage_progress")
    op.drop_index("ix_course_kb_document_modules_module", table_name="course_kb_document_modules")
    op.drop_table("course_kb_document_modules")
    _drop_course_kb_version_scope()
    op.drop_index("ix_course_module_stage_contents_module_status_order", table_name="course_module_stage_contents")
    op.drop_table("course_module_stage_contents")
    op.drop_index("ix_course_modules_version_status_number", table_name="course_modules")
    op.drop_table("course_modules")
    op.drop_table("learning_stage_templates")
