"""Verify real course-scoped pgvector retrieval without exposing KB text."""

from __future__ import annotations

import argparse
import asyncio
import json

from sqlalchemy import select

from src.db import SessionLocal
from src.models import Course, CourseModule, CourseVersion
from src.services.rag import retrieve_course_chunks


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a Zito course RAG retrieval.")
    parser.add_argument("--course-slug", default="personal-development-ai")
    parser.add_argument("--module-number", type=int, default=1)
    parser.add_argument("--question", default="اولین قدم برای یک هدف بزرگ چیست؟")
    return parser.parse_args()


async def _run(arguments: argparse.Namespace) -> int:
    with SessionLocal() as db:
        course = db.scalars(select(Course).where(Course.slug == arguments.course_slug)).first()
        if not course:
            raise ValueError(f"Course slug was not found: {arguments.course_slug}")
        version = db.scalars(
            select(CourseVersion)
            .where(CourseVersion.course_id == course.id, CourseVersion.status == "published")
            .order_by(CourseVersion.version_number.desc())
        ).first()
        if not version:
            raise ValueError("No published course version was found.")
        module = db.scalars(
            select(CourseModule).where(
                CourseModule.course_version_id == version.id,
                CourseModule.module_number == arguments.module_number,
            )
        ).first()
        if not module:
            raise ValueError(f"Module {arguments.module_number} was not found for the selected course version.")

        result = await retrieve_course_chunks(
            db,
            course_version_id=version.id,
            module_id=module.id,
            question=arguments.question,
        )
        output = {
            "course_slug": course.slug,
            "course_version": version.version_number,
            "module_number": module.module_number,
            "retrieval_method": result.method,
            "grounded": result.grounded,
            "source_count": len(result.chunks),
            "sources": [
                {
                    "title": chunk.document_title,
                    "scope": chunk.scope,
                    "score": round(chunk.score, 4),
                }
                for chunk in result.chunks
            ],
        }
        if result.error_message:
            output["error_message"] = result.error_message
        # Windows PowerShell can use a legacy code page; escaped JSON keeps
        # this operational verifier reliable without changing KB data itself.
        print(json.dumps(output, ensure_ascii=True))
        return 0 if result.grounded else 2


def main() -> int:
    return asyncio.run(_run(_parse_arguments()))


if __name__ == "__main__":
    raise SystemExit(main())
