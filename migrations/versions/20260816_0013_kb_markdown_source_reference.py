"""track the source location of course KB documents

Revision ID: 20260816_0013
Revises: 20260816_0012
Create Date: 2026-08-16

The runtime RAG schema already pins documents to a course version. This
revision adds non-secret provenance so a document can be traced back to its
checked-in mock Markdown source now, and to a future CMS source later.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260816_0013"
down_revision: Union[str, None] = "20260816_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    op.add_column(
        "course_kb_documents",
        sa.Column("source_reference", sa.String(length=500), nullable=True),
    )
    op.create_index(
        "ix_course_kb_documents_version_source_ref",
        "course_kb_documents",
        ["course_version_id", "source_reference"],
    )


def downgrade() -> None:
    if _is_sqlite():
        with op.batch_alter_table("course_kb_documents") as batch:
            batch.drop_index("ix_course_kb_documents_version_source_ref")
            batch.drop_column("source_reference")
        return

    op.drop_index("ix_course_kb_documents_version_source_ref", table_name="course_kb_documents")
    op.drop_column("course_kb_documents", "source_reference")
