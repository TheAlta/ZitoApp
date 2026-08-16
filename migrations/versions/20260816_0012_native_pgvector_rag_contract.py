"""make course RAG native, version-safe, and asynchronously indexable

Revision ID: 20260816_0012
Revises: 20260808_0011
Create Date: 2026-08-16

The preceding local-only RAG foundation stored vectors as JSON and could fall
back from a module to unrelated course documents. This revision pins every KB
record to a published course version, stores Bge-m3 vectors as halfvec(3072),
and queues document indexing outside learner requests.
"""

from __future__ import annotations

import hashlib
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import HALFVEC


revision: str = "20260816_0012"
down_revision: Union[str, None] = "20260808_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def _add_unique_constraint(table_name: str, name: str, columns: list[str]) -> None:
    if _is_sqlite():
        with op.batch_alter_table(table_name) as batch:
            batch.create_unique_constraint(name, columns)
    else:
        op.create_unique_constraint(name, table_name, columns)


def _assert_pgvector_support() -> None:
    if _is_sqlite():
        return
    bind = op.get_bind()
    installed = bind.execute(
        sa.text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
    ).scalar_one_or_none()
    if not installed:
        raise RuntimeError(
            "pgvector is required before this migration. Install pgvector and run CREATE EXTENSION vector."
        )
    try:
        bind.execute(sa.text("SELECT NULL::halfvec"))
    except Exception as exc:
        raise RuntimeError(
            "The installed pgvector build does not support halfvec; install pgvector 0.7+ before migrating."
        ) from exc


def _backfill_document_versions_and_checksums() -> None:
    bind = op.get_bind()
    # Legacy seed documents belonged to the original version 1. A document for
    # which that relationship cannot be proved stops the migration instead of
    # being guessed into a newer course version.
    bind.execute(
        sa.text(
            "UPDATE course_kb_documents AS document "
            "SET course_version_id = ("
            "  SELECT version.id FROM course_versions AS version "
            "  WHERE version.course_id = document.course_id "
            "    AND version.version_number = 1"
            ") "
            "WHERE document.course_version_id IS NULL"
        )
    )
    unpinned = bind.execute(
        sa.text("SELECT count(*) FROM course_kb_documents WHERE course_version_id IS NULL")
    ).scalar_one()
    if unpinned:
        raise RuntimeError(
            f"Cannot pin {unpinned} KB document(s) to a course version safely. Resolve them before retrying."
        )

    for row in bind.execute(
        sa.text("SELECT id, content FROM course_kb_documents")
    ).mappings():
        checksum = hashlib.sha256(str(row["content"]).strip().encode("utf-8")).hexdigest()
        bind.execute(
            sa.text(
                "UPDATE course_kb_documents "
                "SET content_checksum = :checksum "
                "WHERE id = :document_id"
            ),
            {"checksum": checksum, "document_id": row["id"]},
        )


def _upgrade_documents() -> None:
    op.add_column(
        "course_kb_documents",
        sa.Column("content_checksum", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "course_kb_documents",
        sa.Column("status", sa.String(length=30), nullable=False, server_default="approved"),
    )
    op.add_column(
        "course_kb_documents",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    _backfill_document_versions_and_checksums()

    if _is_sqlite():
        with op.batch_alter_table("course_kb_documents") as batch:
            batch.alter_column("course_version_id", existing_type=sa.Integer(), nullable=False)
            batch.alter_column("content_checksum", existing_type=sa.String(length=64), nullable=False)
            batch.create_unique_constraint("uq_course_kb_documents_id_version", ["id", "course_version_id"])
            batch.create_foreign_key(
                "fk_course_kb_documents_version_course",
                "course_versions",
                ["course_version_id", "course_id"],
                ["id", "course_id"],
                ondelete="CASCADE",
            )
            batch.create_index(
                "ix_course_kb_documents_version_status",
                ["course_version_id", "status", "id"],
            )
        return

    op.alter_column("course_kb_documents", "course_version_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("course_kb_documents", "content_checksum", existing_type=sa.String(length=64), nullable=False)
    op.create_unique_constraint(
        "uq_course_kb_documents_id_version",
        "course_kb_documents",
        ["id", "course_version_id"],
    )
    op.create_foreign_key(
        "fk_course_kb_documents_version_course",
        "course_kb_documents",
        "course_versions",
        ["course_version_id", "course_id"],
        ["id", "course_id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_course_kb_documents_version_status",
        "course_kb_documents",
        ["course_version_id", "status", "id"],
    )


def _upgrade_rag_configs() -> None:
    op.add_column(
        "course_rag_configs",
        sa.Column("embedding_model", sa.String(length=120), nullable=False, server_default="Bge-m3"),
    )
    op.add_column(
        "course_rag_configs",
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False, server_default="3072"),
    )
    if _is_sqlite():
        with op.batch_alter_table("course_rag_configs") as batch:
            batch.drop_column("allow_course_fallback")
    else:
        op.drop_column("course_rag_configs", "allow_course_fallback")


def _upgrade_document_module_scope() -> None:
    bind = op.get_bind()
    op.add_column(
        "course_kb_document_modules",
        sa.Column("course_version_id", sa.Integer(), nullable=True),
    )
    bind.execute(
        sa.text(
            "UPDATE course_kb_document_modules AS scope "
            "SET course_version_id = ("
            "  SELECT document.course_version_id FROM course_kb_documents AS document "
            "  WHERE document.id = scope.document_id"
            ")"
        )
    )
    missing = bind.execute(
        sa.text("SELECT count(*) FROM course_kb_document_modules WHERE course_version_id IS NULL")
    ).scalar_one()
    if missing:
        raise RuntimeError(f"Cannot version-scope {missing} KB module mapping(s).")

    if _is_sqlite():
        with op.batch_alter_table("course_kb_document_modules") as batch:
            batch.alter_column("course_version_id", existing_type=sa.Integer(), nullable=False)
            batch.create_foreign_key(
                "fk_course_kb_document_modules_document_version",
                "course_kb_documents",
                ["document_id", "course_version_id"],
                ["id", "course_version_id"],
                ondelete="CASCADE",
            )
            batch.create_foreign_key(
                "fk_course_kb_document_modules_module_version",
                "course_modules",
                ["course_module_id", "course_version_id"],
                ["id", "course_version_id"],
                ondelete="CASCADE",
            )
            batch.create_index(
                "ix_course_kb_document_modules_version_module",
                ["course_version_id", "course_module_id"],
            )
        return

    op.alter_column("course_kb_document_modules", "course_version_id", existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key(
        "fk_course_kb_document_modules_document_version",
        "course_kb_document_modules",
        "course_kb_documents",
        ["document_id", "course_version_id"],
        ["id", "course_version_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_course_kb_document_modules_module_version",
        "course_kb_document_modules",
        "course_modules",
        ["course_module_id", "course_version_id"],
        ["id", "course_version_id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_course_kb_document_modules_version_module",
        "course_kb_document_modules",
        ["course_version_id", "course_module_id"],
    )


def _upgrade_chunks() -> None:
    bind = op.get_bind()
    embedding_type = sa.JSON() if _is_sqlite() else HALFVEC(3072)
    op.add_column(
        "course_kb_document_chunks",
        sa.Column("course_version_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "course_kb_document_chunks",
        sa.Column("embedding", embedding_type, nullable=True),
    )
    op.add_column(
        "course_kb_document_chunks",
        sa.Column("embedding_input_checksum", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "course_kb_document_chunks",
        sa.Column("embedding_indexed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "course_kb_document_chunks",
        sa.Column("embedding_error", sa.Text(), nullable=True),
    )
    bind.execute(
        sa.text(
            "UPDATE course_kb_document_chunks AS chunk "
            "SET course_version_id = ("
            "  SELECT document.course_version_id FROM course_kb_documents AS document "
            "  WHERE document.id = chunk.document_id"
            "), embedding_input_checksum = chunk.content_checksum, "
            "embedding_status = 'pending', embedding_model = NULL, embedding_dimension = NULL"
        )
    )
    missing = bind.execute(
        sa.text(
            "SELECT count(*) FROM course_kb_document_chunks "
            "WHERE course_version_id IS NULL OR embedding_input_checksum IS NULL"
        )
    ).scalar_one()
    if missing:
        raise RuntimeError(f"Cannot migrate {missing} KB chunk(s) to the native vector contract.")

    if _is_sqlite():
        with op.batch_alter_table("course_kb_document_chunks") as batch:
            batch.alter_column("course_version_id", existing_type=sa.Integer(), nullable=False)
            batch.alter_column("embedding_input_checksum", existing_type=sa.String(length=64), nullable=False)
            batch.create_foreign_key(
                "fk_course_kb_chunks_document_version",
                "course_kb_documents",
                ["document_id", "course_version_id"],
                ["id", "course_version_id"],
                ondelete="CASCADE",
            )
            batch.create_index(
                "ix_course_kb_document_chunks_version_status",
                ["course_version_id", "embedding_status"],
            )
            batch.drop_column("embedding_json")
        return

    op.alter_column("course_kb_document_chunks", "course_version_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column(
        "course_kb_document_chunks",
        "embedding_input_checksum",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.create_foreign_key(
        "fk_course_kb_chunks_document_version",
        "course_kb_document_chunks",
        "course_kb_documents",
        ["document_id", "course_version_id"],
        ["id", "course_version_id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_course_kb_document_chunks_version_status",
        "course_kb_document_chunks",
        ["course_version_id", "embedding_status"],
    )
    op.drop_column("course_kb_document_chunks", "embedding_json")
    op.execute(
        "CREATE INDEX ix_course_kb_document_chunks_embedding_hnsw "
        "ON course_kb_document_chunks USING hnsw "
        "(embedding halfvec_cosine_ops) WITH (m = 16, ef_construction = 64) "
        "WHERE embedding IS NOT NULL"
    )


def _create_index_jobs() -> None:
    op.create_table(
        "course_kb_index_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "course_version_id",
            sa.Integer(),
            sa.ForeignKey("course_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("course_kb_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(length=120), nullable=False, server_default="Bge-m3"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["document_id", "course_version_id"],
            ["course_kb_documents.id", "course_kb_documents.course_version_id"],
            name="fk_course_kb_index_jobs_document_version",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_course_kb_index_jobs_attempt_count"),
        sa.CheckConstraint("max_attempts >= 1", name="ck_course_kb_index_jobs_max_attempts"),
    )
    op.create_index(
        "ix_course_kb_index_jobs_status_next",
        "course_kb_index_jobs",
        ["status", "next_attempt_at", "id"],
    )
    op.create_index(
        "ix_course_kb_index_jobs_version_status",
        "course_kb_index_jobs",
        ["course_version_id", "status"],
    )
    op.create_index(
        "ix_course_kb_index_jobs_document_status",
        "course_kb_index_jobs",
        ["document_id", "status"],
    )
    if _is_sqlite():
        op.create_index(
            "ix_course_kb_index_jobs_active_document",
            "course_kb_index_jobs",
            ["document_id", "status"],
        )
    else:
        op.execute(
            "CREATE UNIQUE INDEX uq_course_kb_index_jobs_active_document "
            "ON course_kb_index_jobs (document_id) "
            "WHERE status IN ('queued', 'running', 'retry')"
        )

    bind = op.get_bind()
    for row in bind.execute(
        sa.text("SELECT id, course_version_id, content_checksum FROM course_kb_documents")
    ).mappings():
        bind.execute(
            sa.text(
                "INSERT INTO course_kb_index_jobs "
                "(course_version_id, document_id, source_checksum, embedding_model, status, max_attempts) "
                "VALUES (:course_version_id, :document_id, :source_checksum, 'Bge-m3', 'queued', 5)"
            ),
            {
                "course_version_id": row["course_version_id"],
                "document_id": row["id"],
                "source_checksum": row["content_checksum"],
            },
        )


def upgrade() -> None:
    _assert_pgvector_support()
    _add_unique_constraint("course_versions", "uq_course_versions_id_course", ["id", "course_id"])
    _add_unique_constraint("course_modules", "uq_course_modules_id_version", ["id", "course_version_id"])
    _upgrade_documents()
    _upgrade_rag_configs()
    _upgrade_document_module_scope()
    _upgrade_chunks()
    _create_index_jobs()


def downgrade() -> None:
    if _is_sqlite():
        op.drop_index("ix_course_kb_index_jobs_active_document", table_name="course_kb_index_jobs")
    else:
        op.execute("DROP INDEX IF EXISTS uq_course_kb_index_jobs_active_document")
        op.execute("DROP INDEX IF EXISTS ix_course_kb_document_chunks_embedding_hnsw")
    op.drop_index("ix_course_kb_index_jobs_document_status", table_name="course_kb_index_jobs")
    op.drop_index("ix_course_kb_index_jobs_version_status", table_name="course_kb_index_jobs")
    op.drop_index("ix_course_kb_index_jobs_status_next", table_name="course_kb_index_jobs")
    op.drop_table("course_kb_index_jobs")

    if _is_sqlite():
        with op.batch_alter_table("course_kb_document_chunks") as batch:
            batch.add_column(sa.Column("embedding_json", sa.JSON(), nullable=True))
            batch.drop_index("ix_course_kb_document_chunks_version_status")
            batch.drop_constraint("fk_course_kb_chunks_document_version", type_="foreignkey")
            batch.drop_column("embedding_error")
            batch.drop_column("embedding_indexed_at")
            batch.drop_column("embedding_input_checksum")
            batch.drop_column("embedding")
            batch.drop_column("course_version_id")
    else:
        op.add_column("course_kb_document_chunks", sa.Column("embedding_json", sa.JSON(), nullable=True))
        op.drop_index("ix_course_kb_document_chunks_version_status", table_name="course_kb_document_chunks")
        op.drop_constraint("fk_course_kb_chunks_document_version", "course_kb_document_chunks", type_="foreignkey")
        op.drop_column("course_kb_document_chunks", "embedding_error")
        op.drop_column("course_kb_document_chunks", "embedding_indexed_at")
        op.drop_column("course_kb_document_chunks", "embedding_input_checksum")
        op.drop_column("course_kb_document_chunks", "embedding")
        op.drop_column("course_kb_document_chunks", "course_version_id")

    if _is_sqlite():
        with op.batch_alter_table("course_kb_document_modules") as batch:
            batch.drop_index("ix_course_kb_document_modules_version_module")
            batch.drop_constraint("fk_course_kb_document_modules_module_version", type_="foreignkey")
            batch.drop_constraint("fk_course_kb_document_modules_document_version", type_="foreignkey")
            batch.drop_column("course_version_id")
    else:
        op.drop_index("ix_course_kb_document_modules_version_module", table_name="course_kb_document_modules")
        op.drop_constraint(
            "fk_course_kb_document_modules_module_version",
            "course_kb_document_modules",
            type_="foreignkey",
        )
        op.drop_constraint(
            "fk_course_kb_document_modules_document_version",
            "course_kb_document_modules",
            type_="foreignkey",
        )
        op.drop_column("course_kb_document_modules", "course_version_id")

    op.add_column(
        "course_rag_configs",
        sa.Column("allow_course_fallback", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.drop_column("course_rag_configs", "embedding_dimensions")
    op.drop_column("course_rag_configs", "embedding_model")

    if _is_sqlite():
        with op.batch_alter_table("course_kb_documents") as batch:
            batch.drop_index("ix_course_kb_documents_version_status")
            batch.drop_constraint("fk_course_kb_documents_version_course", type_="foreignkey")
            batch.drop_constraint("uq_course_kb_documents_id_version", type_="unique")
            batch.alter_column("course_version_id", existing_type=sa.Integer(), nullable=True)
            batch.drop_column("updated_at")
            batch.drop_column("status")
            batch.drop_column("content_checksum")
    else:
        op.drop_index("ix_course_kb_documents_version_status", table_name="course_kb_documents")
        op.drop_constraint("fk_course_kb_documents_version_course", "course_kb_documents", type_="foreignkey")
        op.drop_constraint("uq_course_kb_documents_id_version", "course_kb_documents", type_="unique")
        op.alter_column("course_kb_documents", "course_version_id", existing_type=sa.Integer(), nullable=True)
        op.drop_column("course_kb_documents", "updated_at")
        op.drop_column("course_kb_documents", "status")
        op.drop_column("course_kb_documents", "content_checksum")

    if _is_sqlite():
        with op.batch_alter_table("course_modules") as batch:
            batch.drop_constraint("uq_course_modules_id_version", type_="unique")
        with op.batch_alter_table("course_versions") as batch:
            batch.drop_constraint("uq_course_versions_id_course", type_="unique")
    else:
        op.drop_constraint("uq_course_modules_id_version", "course_modules", type_="unique")
        op.drop_constraint("uq_course_versions_id_course", "course_versions", type_="unique")
