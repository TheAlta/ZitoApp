"""Synchronize approved checked-in mock KB content into the database.

This command never calls Arvan. It creates or updates documents, scopes them
to a course version, creates chunks, and queues any needed indexing jobs.
Run the RAG worker separately to create embeddings.
"""

from __future__ import annotations

import argparse
import json

from sqlalchemy import select

from src.db import SessionLocal
from src.models import Course, CourseModule, CourseVersion
from src.services.kb_import import KnowledgeBaseImportError, sync_personal_development_mock_kb


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Zito mock Markdown knowledge-base content.")
    parser.add_argument("--course-slug", default="personal-development-ai")
    parser.add_argument("--version", type=int, default=None, help="Published version number; defaults to newest.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report changes, then roll them back.")
    return parser.parse_args()


def main() -> int:
    arguments = _parse_arguments()
    with SessionLocal() as db:
        course = db.scalars(select(Course).where(Course.slug == arguments.course_slug)).first()
        if not course:
            raise KnowledgeBaseImportError(f"Course slug was not found: {arguments.course_slug}")

        versions = select(CourseVersion).where(
            CourseVersion.course_id == course.id,
            CourseVersion.status == "published",
        )
        if arguments.version is not None:
            versions = versions.where(CourseVersion.version_number == arguments.version)
        version = db.scalars(versions.order_by(CourseVersion.version_number.desc())).first()
        if not version:
            raise KnowledgeBaseImportError("No matching published course version was found.")

        modules = list(
            db.scalars(
                select(CourseModule)
                .where(CourseModule.course_version_id == version.id)
                .order_by(CourseModule.module_number)
            ).all()
        )
        if not modules:
            raise KnowledgeBaseImportError("The selected course version has no modules to scope knowledge-base content.")

        summary = sync_personal_development_mock_kb(
            db,
            course=course,
            course_version=version,
            modules_by_number={module.module_number: module for module in modules},
        )
        output = {
            "dry_run": arguments.dry_run,
            "course_slug": course.slug,
            "course_version": version.version_number,
            "documents_created": summary.created,
            "documents_updated": summary.updated,
            "documents_archived": summary.archived,
            "scopes_created": summary.scopes_created,
            "scopes_removed": summary.scopes_removed,
            "chunk_changes": summary.chunk_changes,
            "documents_synced": len(summary.documents),
        }
        if arguments.dry_run:
            db.rollback()
        else:
            db.commit()
        print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
