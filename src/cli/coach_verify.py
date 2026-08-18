"""Verify one real, grounded course-coach reply without retaining test data."""

from __future__ import annotations

import argparse
import asyncio
import json
from uuid import uuid4

from sqlalchemy import select

from src.db import SessionLocal
from src.models import (
    CoachRetrievalEvent,
    Course,
    CourseModule,
    CourseModuleStageContent,
    CourseVersion,
    User,
    UserCourseEnrollment,
    UserProfile,
)
from src.services.coach import answer_course_question


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify an end-to-end Zito course-coach reply using a temporary learner."
    )
    parser.add_argument("--course-slug", default="personal-development-ai")
    parser.add_argument("--module-number", type=int, default=1)
    parser.add_argument(
        "--question",
        default=None,
        help="Optional learner question. Defaults to a question derived from the selected module objective.",
    )
    return parser.parse_args()


def _published_course_version(db, course_id: int) -> CourseVersion:
    version = db.scalars(
        select(CourseVersion)
        .where(CourseVersion.course_id == course_id, CourseVersion.status == "published")
        .order_by(CourseVersion.version_number.desc())
    ).first()
    if not version:
        raise ValueError("No published course version was found.")
    return version


def _module_stage(db, version: CourseVersion, module_number: int) -> tuple[CourseModuleStageContent, int]:
    stages = db.scalars(
        select(CourseModuleStageContent)
        .join(CourseModule, CourseModule.id == CourseModuleStageContent.course_module_id)
        .where(
            CourseModule.course_version_id == version.id,
            CourseModule.status == "approved",
            CourseModuleStageContent.status == "approved",
        )
        .order_by(CourseModule.module_number, CourseModuleStageContent.stage_number)
    ).all()
    for global_stage_number, stage in enumerate(stages, start=1):
        if stage.course_module and stage.course_module.module_number == module_number:
            return stage, global_stage_number
    raise ValueError(f"Module {module_number} was not found for the selected course version.")


def _default_question_for_stage(stage: CourseModuleStageContent) -> str:
    module = stage.course_module
    if not module:
        return "برای این سرفصل چه اقدام کوچک و عملی می‌توانم انجام دهم؟"
    objectives = module.learning_objectives_json if isinstance(module.learning_objectives_json, list) else []
    objective = next((str(item).strip() for item in objectives if str(item).strip()), module.title)
    return f"برای «{objective}» چه اقدام کوچک و عملی می‌توانم انجام دهم؟"


async def _run(arguments: argparse.Namespace) -> int:
    with SessionLocal() as db:
        try:
            course = db.scalars(select(Course).where(Course.slug == arguments.course_slug)).first()
            if not course:
                raise ValueError(f"Course slug was not found: {arguments.course_slug}")
            version = _published_course_version(db, course.id)
            stage, global_stage_number = _module_stage(db, version, arguments.module_number)
            question = arguments.question.strip() if arguments.question else _default_question_for_stage(stage)

            # Flush gives the service valid foreign keys; rollback below removes
            # every temporary row and deliberately leaves no learner test data.
            user = User(
                phone=f"0900{uuid4().int % 10**10:010d}",
                display_name="کاربر بررسی",
            )
            user.profile = UserProfile(
                work_or_study_field="مدیریت محصول",
                education_level="کارشناسی",
                learning_goal_interests="ساخت عادت یادگیری پایدار",
                ai_familiarity_level="تازه کار",
                daily_learning_time_text="25 دقیقه",
                daily_learning_minutes=25,
                preferred_career_path="مدیر محصول",
            )
            db.add(user)
            db.flush()

            enrollment = UserCourseEnrollment(
                user_id=user.id,
                course_id=course.id,
                course_version_id=version.id,
                current_stage_number=global_stage_number,
            )
            db.add(enrollment)
            db.flush()

            reply = await answer_course_question(
                db,
                user=user,
                enrollment=enrollment,
                stage=stage,
                stage_number=global_stage_number,
                question=question,
            )
            db.flush()
            event = db.scalars(
                select(CoachRetrievalEvent).where(
                    CoachRetrievalEvent.assistant_message_id == reply.assistant_message.id
                )
            ).one()
            output = {
                "course_slug": course.slug,
                "course_version": version.version_number,
                "module_number": arguments.module_number,
                "stage_number": global_stage_number,
                "retrieval_method": reply.retrieval_method,
                "grounded": reply.grounded,
                "citation_count": len(reply.citations),
                "answer_length": len(reply.assistant_message.content),
                "model_response_used": reply.assistant_message.model is not None,
                "event_status": event.status,
                "temporary_records_rolled_back": True,
            }
            print(json.dumps(output, ensure_ascii=True))
            return 0 if reply.grounded and reply.citations and event.status == "ok" else 2
        finally:
            db.rollback()


def main() -> int:
    return asyncio.run(_run(_parse_arguments()))


if __name__ == "__main__":
    raise SystemExit(main())
