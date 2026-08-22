"""Course-level final exams, AI grading, and immutable certificate issuance."""

from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.lib.arvan_client import ArvanAIError, ask_ai
from src.models import Certificate, Course, CourseModule, CourseVersion, Exam, ExamAttempt, User, UserCourseEnrollment
from src.prompts import load_prompt
from src.services.json_utils import parse_json_object
from src.services.rag import RetrievedChunk, format_retrieved_context, retrieve_course_chunks


FINAL_EXAM_GENERATION_PROMPT_VERSION = "final-exam-generation-v1"
FINAL_EXAM_GRADING_PROMPT_VERSION = "final-exam-grading-v1"
_QUESTION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


class FinalExamStateError(ValueError):
    """Raised when a learner cannot perform the requested final-exam action."""


class FinalExamAIError(RuntimeError):
    """Raised when grading cannot safely be completed by the model."""


@dataclass(frozen=True)
class FinalExamAttemptSession:
    attempt: ExamAttempt
    exam: Exam
    questions: list[dict[str, Any]]
    generation_method: str


@dataclass(frozen=True)
class FinalExamGrade:
    attempt: ExamAttempt
    exam: Exam
    score: int
    passed: bool
    feedback: str
    question_feedback: list[dict[str, Any]]
    certificate: Certificate | None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalized_questions(value: Any) -> list[dict[str, Any]]:
    raw_questions = value.get("questions") if isinstance(value, dict) else value
    if not isinstance(raw_questions, list) or not 2 <= len(raw_questions) <= 5:
        raise ValueError("Final exam must contain between two and five questions.")

    questions: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for position, raw in enumerate(raw_questions, start=1):
        if not isinstance(raw, dict):
            raise ValueError("Final exam question is not an object.")
        question_id = str(raw.get("id") or f"final-q-{position}").strip()
        question = str(raw.get("question") or "").strip()[:1200]
        rubric = str(raw.get("rubric") or "").strip()[:1200]
        question_type = str(raw.get("type") or "open").strip().lower()
        max_score = raw.get("max_score")
        if (
            not _QUESTION_ID_PATTERN.fullmatch(question_id)
            or question_id in seen_ids
            or len(question) < 12
            or len(rubric) < 8
            or question_type not in {"open", "scenario"}
            or isinstance(max_score, bool)
            or not isinstance(max_score, int)
            or max_score < 1
            or max_score > 100
        ):
            raise ValueError("Final exam question format is invalid.")
        seen_ids.add(question_id)
        questions.append(
            {
                "id": question_id,
                "type": question_type,
                "question": question,
                "rubric": rubric,
                "max_score": max_score,
            }
        )

    if sum(question["max_score"] for question in questions) != 100:
        raise ValueError("Final exam question scores must total one hundred.")
    return questions


def public_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": question["id"],
            "type": question["type"],
            "question": question["question"],
            "max_score": question["max_score"],
        }
        for question in questions
    ]


def attempt_snapshot_questions(attempt: ExamAttempt) -> list[dict[str, Any]]:
    """Return the immutable, validated question snapshot for one attempt."""

    return _normalized_questions(attempt.questions_snapshot_json)


def attempt_number(db: Session, attempt: ExamAttempt) -> int:
    return int(
        db.scalar(
            select(func.count(ExamAttempt.id)).where(
                ExamAttempt.enrollment_id == attempt.enrollment_id,
                ExamAttempt.exam_id == attempt.exam_id,
                ExamAttempt.id <= attempt.id,
            )
        )
        or 1
    )


def published_final_exam(db: Session, enrollment: UserCourseEnrollment) -> Exam:
    exam = db.scalars(
        select(Exam)
        .where(
            Exam.course_version_id == enrollment.course_version_id,
            Exam.status == "published",
        )
        .order_by(Exam.id.desc())
        .limit(1)
    ).first()
    if not exam:
        raise FinalExamStateError("آزمون نهایی این نسخه دوره هنوز منتشر نشده است.")
    _normalized_questions(exam.questions_json)
    return exam


def _current_attempt(db: Session, enrollment: UserCourseEnrollment, exam: Exam) -> ExamAttempt | None:
    return db.scalars(
        select(ExamAttempt)
        .where(
            ExamAttempt.enrollment_id == enrollment.id,
            ExamAttempt.exam_id == exam.id,
            ExamAttempt.user_id == enrollment.user_id,
            ExamAttempt.status == "in_progress",
        )
        .order_by(ExamAttempt.id.desc())
        .limit(1)
    ).first()


def latest_attempt(db: Session, enrollment: UserCourseEnrollment, exam: Exam) -> ExamAttempt | None:
    return db.scalars(
        select(ExamAttempt)
        .where(
            ExamAttempt.enrollment_id == enrollment.id,
            ExamAttempt.exam_id == exam.id,
            ExamAttempt.user_id == enrollment.user_id,
        )
        .order_by(ExamAttempt.id.desc())
        .limit(1)
    ).first()


def issued_certificate(db: Session, enrollment: UserCourseEnrollment) -> Certificate | None:
    return db.scalars(
        select(Certificate)
        .where(
            Certificate.user_id == enrollment.user_id,
            Certificate.course_version_id == enrollment.course_version_id,
        )
        .order_by(Certificate.id.desc())
        .limit(1)
    ).first()


def _course_outline(db: Session, course_version_id: int) -> list[dict[str, Any]]:
    modules = db.scalars(
        select(CourseModule)
        .where(CourseModule.course_version_id == course_version_id, CourseModule.status == "approved")
        .order_by(CourseModule.module_number)
    ).all()
    return [
        {
            "number": module.module_number,
            "title": module.title,
            "objectives": module.learning_objectives_json or [],
            "tags": module.tags_json or [],
        }
        for module in modules
    ]


async def _retrieve_exam_sources(
    db: Session,
    *,
    enrollment: UserCourseEnrollment,
    course: Course,
) -> tuple[list[RetrievedChunk], list[str]]:
    """Take at most one scoped source per module for balanced exam generation."""

    chunks: list[RetrievedChunk] = []
    retrieval_methods: list[str] = []
    seen_chunks: set[int] = set()
    modules = db.scalars(
        select(CourseModule)
        .where(CourseModule.course_version_id == enrollment.course_version_id, CourseModule.status == "approved")
        .order_by(CourseModule.module_number)
    ).all()
    for module in modules:
        objectives = "، ".join(str(item) for item in (module.learning_objectives_json or [])[:3])
        retrieval = await retrieve_course_chunks(
            db,
            course_version_id=enrollment.course_version_id,
            module_id=module.id,
            question=f"آزمون نهایی دوره {course.title}: {module.title}. {objectives}",
        )
        retrieval_methods.append(retrieval.method)
        for chunk in retrieval.chunks:
            if chunk.chunk_id in seen_chunks:
                continue
            seen_chunks.add(chunk.chunk_id)
            chunks.append(chunk)
            break
    return chunks, retrieval_methods


def _source_metadata(chunks: list[RetrievedChunk]) -> list[dict[str, Any]]:
    return [
        {
            "source_number": index,
            "title": chunk.document_title,
            "scope": chunk.scope,
        }
        for index, chunk in enumerate(chunks, start=1)
    ]


async def _generate_questions(
    db: Session,
    *,
    enrollment: UserCourseEnrollment,
    exam: Exam,
    course: Course,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fallback_questions = _normalized_questions(exam.questions_json)
    chunks, retrieval_methods = await _retrieve_exam_sources(db, enrollment=enrollment, course=course)
    fallback_metadata = {
        "method": "approved_fallback",
        "prompt_version": FINAL_EXAM_GENERATION_PROMPT_VERSION,
        "retrieval_methods": retrieval_methods,
        "source_chunks": _source_metadata(chunks),
    }
    if not chunks:
        return fallback_questions, fallback_metadata

    payload = {
        "course": {
            "title": course.title,
            "domain": course.domain,
            "version_number": db.get(CourseVersion, enrollment.course_version_id).version_number,
            "modules": _course_outline(db, enrollment.course_version_id),
        },
        "retrieved_sources": format_retrieved_context(chunks),
    }
    try:
        raw_response = await ask_ai(
            load_prompt("final_exam_generation.md"),
            json.dumps(payload, ensure_ascii=False),
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        questions = _normalized_questions(parse_json_object(raw_response))
    except (ArvanAIError, ValueError, TypeError, AttributeError):
        return fallback_questions, fallback_metadata

    return questions, {
        "method": "rag_generated",
        "model": get_settings().arvan_model,
        "prompt_version": FINAL_EXAM_GENERATION_PROMPT_VERSION,
        "retrieval_methods": retrieval_methods,
        "source_chunks": _source_metadata(chunks),
    }


async def start_final_exam(
    db: Session,
    *,
    user: User,
    enrollment: UserCourseEnrollment,
) -> FinalExamAttemptSession:
    if enrollment.status == "completed":
        raise FinalExamStateError("این دوره قبلا با موفقیت کامل شده است.")
    if enrollment.status != "awaiting_final_exam":
        raise FinalExamStateError("برای شروع آزمون نهایی، ابتدا همه سرفصل‌های دوره را کامل کن.")
    course = db.get(Course, enrollment.course_id)
    if not course:
        raise FinalExamStateError("دوره این ثبت‌نام پیدا نشد.")
    exam = published_final_exam(db, enrollment)
    existing = _current_attempt(db, enrollment, exam)
    if existing:
        try:
            questions = attempt_snapshot_questions(existing)
        except ValueError as exc:
            raise FinalExamStateError("تلاش فعال آزمون قابل بازیابی نیست.") from exc
        metadata = existing.generation_json if isinstance(existing.generation_json, dict) else {}
        return FinalExamAttemptSession(
            attempt=existing,
            exam=exam,
            questions=questions,
            generation_method=str(metadata.get("method") or "approved_fallback"),
        )

    questions, generation = await _generate_questions(
        db,
        enrollment=enrollment,
        exam=exam,
        course=course,
    )
    attempt = ExamAttempt(
        exam_id=exam.id,
        user_id=user.id,
        enrollment_id=enrollment.id,
        answers_json={},
        questions_snapshot_json=questions,
        generation_json=generation,
        status="in_progress",
    )
    db.add(attempt)
    db.flush()
    return FinalExamAttemptSession(
        attempt=attempt,
        exam=exam,
        questions=questions,
        generation_method=str(generation.get("method") or "approved_fallback"),
    )


def _normalized_answers(raw_answers: Any, questions: list[dict[str, Any]]) -> dict[str, str]:
    if not isinstance(raw_answers, dict):
        raise ValueError("پاسخ‌های آزمون باید به‌صورت ساخت‌یافته ارسال شوند.")
    answers: dict[str, str] = {}
    missing: list[str] = []
    for question in questions:
        answer = raw_answers.get(question["id"])
        if not isinstance(answer, str):
            missing.append(question["id"])
            continue
        clean_answer = answer.strip()
        if len(clean_answer) < 2:
            missing.append(question["id"])
            continue
        if len(clean_answer) > 2500:
            raise ValueError("هر پاسخ آزمون حداکثر می‌تواند ۲۵۰۰ نویسه داشته باشد.")
        answers[question["id"]] = clean_answer
    if missing:
        raise ValueError("به همه سوال‌های آزمون نهایی پاسخ بده.")
    return answers


def _normalized_grade(value: dict[str, Any], questions: list[dict[str, Any]], passing_score: int) -> tuple[int, bool, str, list[dict[str, Any]]]:
    score = value.get("score")
    if isinstance(score, bool) or not isinstance(score, int) or score < 0 or score > 100:
        raise ValueError("نمره AI معتبر نیست.")
    feedback = str(value.get("feedback") or "").strip()[:1600]
    if len(feedback) < 2:
        raise ValueError("بازخورد AI معتبر نیست.")

    raw_feedback = value.get("question_feedback")
    by_question_id = {
        str(item.get("question_id")): item
        for item in raw_feedback
        if isinstance(item, dict) and item.get("question_id")
    } if isinstance(raw_feedback, list) else {}
    question_feedback: list[dict[str, Any]] = []
    for question in questions:
        item = by_question_id.get(question["id"], {})
        item_score = item.get("score")
        if isinstance(item_score, bool) or not isinstance(item_score, int):
            item_score = None
        elif item_score < 0 or item_score > question["max_score"]:
            item_score = None
        item_feedback = str(item.get("feedback") or "").strip()[:700]
        question_feedback.append(
            {
                "question_id": question["id"],
                "score": item_score,
                "feedback": item_feedback or "پاسخ این بخش در نمره نهایی بررسی شد.",
            }
        )
    return score, score >= passing_score, feedback, question_feedback


def _new_certificate_number(db: Session) -> str:
    year = _now().strftime("%Y")
    for _ in range(10):
        candidate = f"ZITO-{year}-{secrets.token_hex(6).upper()}"
        exists = db.scalar(select(Certificate.id).where(Certificate.certificate_number == candidate))
        if not exists:
            return candidate
    raise RuntimeError("Could not allocate a unique certificate number.")


def _issue_certificate(
    db: Session,
    *,
    user: User,
    enrollment: UserCourseEnrollment,
    course: Course,
    version: CourseVersion,
    exam: Exam,
    attempt: ExamAttempt,
) -> Certificate:
    existing = issued_certificate(db, enrollment)
    if existing:
        return existing
    certificate = Certificate(
        user_id=user.id,
        course_id=course.id,
        course_version_id=version.id,
        exam_attempt_id=attempt.id,
        certificate_number=_new_certificate_number(db),
        recipient_name=user.display_name.strip()[:100],
        course_title=course.title,
        course_version_number=version.version_number,
        score=attempt.score,
        passing_score=exam.passing_score,
        status="issued",
    )
    db.add(certificate)
    db.flush()
    return certificate


async def grade_final_exam(
    db: Session,
    *,
    user: User,
    enrollment: UserCourseEnrollment,
    attempt_id: int,
    raw_answers: Any,
) -> FinalExamGrade:
    if enrollment.status not in {"awaiting_final_exam", "completed"}:
        raise FinalExamStateError("آزمون نهایی این مسیر هنوز در دسترس نیست.")
    attempt = db.scalars(
        select(ExamAttempt).where(
            ExamAttempt.id == attempt_id,
            ExamAttempt.enrollment_id == enrollment.id,
            ExamAttempt.user_id == user.id,
        )
    ).first()
    if not attempt:
        raise FinalExamStateError("تلاش آزمون نهایی پیدا نشد.")
    exam = db.get(Exam, attempt.exam_id)
    version = db.get(CourseVersion, enrollment.course_version_id)
    course = db.get(Course, enrollment.course_id)
    if not exam or not version or not course or exam.course_version_id != version.id:
        raise FinalExamStateError("قرارداد آزمون نهایی معتبر نیست.")
    questions = attempt_snapshot_questions(attempt)

    if attempt.status in {"passed", "failed"}:
        grading = attempt.grading_json if isinstance(attempt.grading_json, dict) else {}
        return FinalExamGrade(
            attempt=attempt,
            exam=exam,
            score=int(attempt.score or 0),
            passed=bool(attempt.passed),
            feedback=str(attempt.grading_feedback or "نتیجه آزمون ثبت شده است."),
            question_feedback=list(grading.get("question_feedback") or []),
            certificate=issued_certificate(db, enrollment),
        )
    if attempt.status != "in_progress":
        raise FinalExamStateError("وضعیت این تلاش آزمون معتبر نیست.")

    answers = _normalized_answers(raw_answers, questions)
    request_payload = {
        "exam": {
            "title": exam.title,
            "passing_score": exam.passing_score,
            "questions": questions,
        },
        "answers": answers,
    }
    try:
        raw_response = await ask_ai(
            load_prompt("final_exam_grading.md"),
            json.dumps(request_payload, ensure_ascii=False),
            temperature=0,
            response_format={"type": "json_object"},
        )
        score, passed, feedback, question_feedback = _normalized_grade(
            parse_json_object(raw_response),
            questions,
            exam.passing_score,
        )
    except (ArvanAIError, ValueError, TypeError) as exc:
        raise FinalExamAIError("تصحیح هوشمند در حال حاضر در دسترس نیست؛ کمی بعد دوباره ثبت کن.") from exc

    now = _now()
    attempt.answers_json = {"answers": answers}
    attempt.score = score
    attempt.passed = passed
    attempt.status = "passed" if passed else "failed"
    attempt.submitted_at = now
    attempt.grading_feedback = feedback
    attempt.grading_json = {
        "question_feedback": question_feedback,
        "model": get_settings().arvan_model,
        "prompt_version": FINAL_EXAM_GRADING_PROMPT_VERSION,
    }
    attempt.graded_by_ai_at = now

    certificate = None
    if passed:
        certificate = _issue_certificate(
            db,
            user=user,
            enrollment=enrollment,
            course=course,
            version=version,
            exam=exam,
            attempt=attempt,
        )
        enrollment.status = "completed"
        enrollment.completed_at = enrollment.completed_at or now

    return FinalExamGrade(
        attempt=attempt,
        exam=exam,
        score=score,
        passed=passed,
        feedback=feedback,
        question_feedback=question_feedback,
        certificate=certificate,
    )
