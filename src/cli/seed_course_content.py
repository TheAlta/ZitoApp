"""Idempotently add or refresh the checked-in Fake CMS learning content.

This command deliberately does not seed administrators. It is intended for a
database that has already received its Alembic schema migration.
"""

from __future__ import annotations

import argparse
import asyncio
import json

from sqlalchemy import select

from src.db import SessionLocal
from src.models import Course, CourseVersion
from src.seed import seed_phase2_fake_course
from src.services.rag import run_index_worker_once


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed Zito Fake CMS content and make its RAG sources ready for coaching."
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Seed only; leave pending RAG jobs for the supervised worker.",
    )
    parser.add_argument(
        "--index-limit",
        type=int,
        default=50,
        help="Maximum queued KB documents to index after seeding (default: 50).",
    )
    arguments = parser.parse_args()
    if arguments.index_limit < 1:
        parser.error("--index-limit must be at least 1")
    return arguments


def main() -> int:
    arguments = _parse_arguments()
    with SessionLocal() as db:
        seed_phase2_fake_course(db)
        course = db.scalars(select(Course).where(Course.slug == "personal-development-ai")).one()
        versions = list(
            db.scalars(
                select(CourseVersion)
                .where(CourseVersion.course_id == course.id)
                .order_by(CourseVersion.version_number)
            ).all()
        )
        output: dict[str, object] = {
            "course_slug": course.slug,
            "versions": [
                {
                    "number": version.version_number,
                    "status": version.status,
                    "module_stage_count": version.module_stage_count,
                    "requires_final_exam": version.requires_final_exam,
                }
                for version in versions
            ],
        }

    if arguments.skip_index:
        output["indexing"] = {"skipped": True}
        print(json.dumps(output, ensure_ascii=True, sort_keys=True))
        return 0

    outcomes = asyncio.run(run_index_worker_once(SessionLocal, limit=arguments.index_limit))
    status_counts: dict[str, int] = {}
    errors: list[dict[str, object]] = []
    for outcome in outcomes:
        status_counts[outcome.status] = status_counts.get(outcome.status, 0) + 1
        if outcome.status in {"retry", "failed"}:
            errors.append(
                {
                    "job_id": outcome.job_id,
                    "status": outcome.status,
                    "error": outcome.error_message,
                }
            )
    output["indexing"] = {
        "skipped": False,
        "processed": len(outcomes),
        "statuses": status_counts,
        "errors": errors,
    }
    print(json.dumps(output, ensure_ascii=True, sort_keys=True))
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
