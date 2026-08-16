"""add course coach and RAG audit foundation

Revision ID: 20260808_0011
Revises: 20260806_0010
Create Date: 2026-08-08

This migration is additive. It keeps the canonical user profile and pinned
course-version model intact while adding retrievable KB chunks, non-secret
provider routing, and auditable learner/coach conversations.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260808_0011"
down_revision: Union[str, None] = "20260806_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "course_rag_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_version_id", sa.Integer(), sa.ForeignKey("course_versions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="zito_embedding"),
        sa.Column("endpoint_config_ref", sa.String(length=120), nullable=True),
        sa.Column("knowledge_base_ref", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="ready"),
        sa.Column("supports_metadata_filters", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allow_course_fallback", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_course_rag_configs_status", "course_rag_configs", ["status"])

    op.create_table(
        "course_kb_document_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("course_kb_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_checksum", sa.String(length=64), nullable=False),
        sa.Column("embedding_json", sa.JSON(), nullable=True),
        sa.Column("embedding_model", sa.String(length=120), nullable=True),
        sa.Column("embedding_dimension", sa.Integer(), nullable=True),
        sa.Column("embedding_status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_course_kb_document_chunk_index"),
    )
    op.create_index(
        "ix_course_kb_document_chunks_document_status",
        "course_kb_document_chunks",
        ["document_id", "embedding_status"],
    )

    op.create_table(
        "coach_threads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enrollment_id", sa.Integer(), sa.ForeignKey("user_course_enrollments.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_coach_threads_user_updated", "coach_threads", ["user_id", "last_message_at"])

    op.create_table(
        "coach_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("thread_id", sa.Integer(), sa.ForeignKey("coach_threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module_stage_content_id", sa.Integer(), sa.ForeignKey("course_module_stage_contents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_coach_messages_thread_created", "coach_messages", ["thread_id", "created_at"])

    op.create_table(
        "coach_retrieval_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("assistant_message_id", sa.Integer(), sa.ForeignKey("coach_messages.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("rag_config_id", sa.Integer(), sa.ForeignKey("course_rag_configs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("retrieval_method", sa.String(length=50), nullable=False),
        sa.Column("source_chunks_json", sa.JSON(), nullable=False),
        sa.Column("grounded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="ok"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_coach_retrieval_events_config_created",
        "coach_retrieval_events",
        ["rag_config_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_coach_retrieval_events_config_created", table_name="coach_retrieval_events")
    op.drop_table("coach_retrieval_events")
    op.drop_index("ix_coach_messages_thread_created", table_name="coach_messages")
    op.drop_table("coach_messages")
    op.drop_index("ix_coach_threads_user_updated", table_name="coach_threads")
    op.drop_table("coach_threads")
    op.drop_index("ix_course_kb_document_chunks_document_status", table_name="course_kb_document_chunks")
    op.drop_table("course_kb_document_chunks")
    op.drop_index("ix_course_rag_configs_status", table_name="course_rag_configs")
    op.drop_table("course_rag_configs")
