"""Report migration-safety facts without exposing learner or secret data."""

from __future__ import annotations

import json

from sqlalchemy import exists, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.db import SessionLocal
from src.models import (
    CourseKbIndexJob,
    CourseModule,
    CourseVersion,
    UserCourseEnrollment,
    UserModuleStageProgress,
    UserStageProgress,
)


def _count(db: Session, statement) -> int:
    return int(db.scalar(statement) or 0)


def _migration_revision(db: Session) -> str:
    try:
        value = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    except SQLAlchemyError:
        return "unavailable"
    return str(value) if value else "unavailable"


def collect_database_audit(db: Session) -> dict[str, object]:
    """Return aggregate-only facts used before any future legacy cleanup."""
    has_modules = exists(select(1).where(CourseModule.course_version_id == CourseVersion.id))
    legacy_version_condition = ~has_modules
    mismatch_condition = UserCourseEnrollment.course_id != CourseVersion.course_id

    rag_statuses = {
        str(status): int(count)
        for status, count in db.execute(
            select(CourseKbIndexJob.status, func.count(CourseKbIndexJob.id)).group_by(
                CourseKbIndexJob.status
            )
        ).all()
    }

    return {
        "alembic_revision": _migration_revision(db),
        "learning_structure": {
            "module_based_course_versions": _count(
                db,
                select(func.count(CourseVersion.id)).where(has_modules),
            ),
            "flat_compatibility_course_versions": _count(
                db,
                select(func.count(CourseVersion.id)).where(legacy_version_condition),
            ),
            "flat_compatibility_enrollments": _count(
                db,
                select(func.count(UserCourseEnrollment.id))
                .join(CourseVersion, CourseVersion.id == UserCourseEnrollment.course_version_id)
                .where(legacy_version_condition),
            ),
            "module_progress_rows": _count(db, select(func.count(UserModuleStageProgress.id))),
            "flat_progress_rows": _count(db, select(func.count(UserStageProgress.id))),
        },
        "enrollment_integrity": {
            "course_version_mismatches": _count(
                db,
                select(func.count(UserCourseEnrollment.id))
                .join(CourseVersion, CourseVersion.id == UserCourseEnrollment.course_version_id)
                .where(mismatch_condition),
            ),
            "invalid_progress_rows": _count(
                db,
                select(func.count(UserCourseEnrollment.id)).where(
                    (UserCourseEnrollment.current_stage_number < 1)
                    | (UserCourseEnrollment.progress_percentage < 0)
                    | (UserCourseEnrollment.progress_percentage > 100)
                ),
            ),
        },
        "rag_index_jobs": rag_statuses,
    }


def main() -> int:
    with SessionLocal() as db:
        print(json.dumps(collect_database_audit(db), ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
