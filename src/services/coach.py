"""Grounded, course-version-scoped coaching for the learner-facing app."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.lib.arvan_client import ArvanAIError, ask_ai
from src.models import (
    CoachMessage,
    CoachRetrievalEvent,
    CoachThread,
    Course,
    CourseModuleStageContent,
    User,
    UserCourseEnrollment,
)
from src.prompts import load_prompt
from src.services.json_utils import parse_json_object
from src.services.rag import RetrievedChunk, format_retrieved_context, retrieve_course_chunks


COACH_PROMPT_VERSION = "course-coach-v2"
_MODEL_HISTORY_LIMIT = 4
_MODEL_HISTORY_MESSAGE_CHAR_LIMIT = 600
_VISIBLE_HISTORY_LIMIT = 40


@dataclass(frozen=True)
class CoachReply:
    thread: CoachThread
    assistant_message: CoachMessage
    grounded: bool
    citations: list[dict[str, Any]]
    retrieval_method: str
    suggested_action: str | None


def _first_name(display_name: str) -> str:
    return display_name.strip().split()[0][:50] if display_name.strip() else "دوست خوبم"


def build_personalized_context(
    user: User,
    enrollment: UserCourseEnrollment,
    stage: CourseModuleStageContent,
    stage_number: int,
    course: Course,
) -> dict[str, Any]:
    """Return only the learner attributes that are useful for coaching.

    Phone, user/enrollment IDs, sessions and referral source stay inside Zito
    and are never sent to Arvan.
    """
    profile = user.profile
    module = stage.course_module
    if not module:
        raise ValueError("The learning stage is missing its course module.")

    return {
        "learner": {
            "preferred_name": _first_name(user.display_name),
            "work_or_study_field": profile.work_or_study_field if profile else None,
            "education_level": profile.education_level if profile else None,
            "learning_goal_interests": profile.learning_goal_interests if profile else None,
            "ai_familiarity_level": profile.ai_familiarity_level if profile else None,
            "daily_learning_time": profile.daily_learning_time_text if profile else None,
            "preferred_career_path": profile.preferred_career_path if profile else None,
        },
        "course": {
            "title": course.title,
            "domain": course.domain,
        },
        "module": {
            "number": module.module_number,
            "title": module.title,
            "objectives": module.learning_objectives_json or [],
            "tags": module.tags_json or [],
        },
        "learning_stage": {
            "global_number": stage_number,
            "module_number": stage.stage_number,
            "title": stage.title,
            "type": stage.template.code if stage.template else None,
        },
        "progress": {
            "current_stage_number": enrollment.current_stage_number,
            "progress_percentage": enrollment.progress_percentage,
        },
    }


def get_or_create_coach_thread(
    db: Session,
    *,
    user: User,
    enrollment: UserCourseEnrollment,
) -> CoachThread:
    thread = db.scalars(
        select(CoachThread).where(CoachThread.enrollment_id == enrollment.id)
    ).first()
    if thread:
        if thread.user_id != user.id:
            raise RuntimeError("Coach thread ownership does not match its enrollment.")
        return thread

    thread = CoachThread(user_id=user.id, enrollment_id=enrollment.id, status="active")
    db.add(thread)
    db.flush()
    return thread


def list_coach_messages(
    db: Session,
    *,
    user: User,
    enrollment: UserCourseEnrollment,
    limit: int = _VISIBLE_HISTORY_LIMIT,
) -> tuple[CoachThread | None, list[CoachMessage]]:
    thread = db.scalars(
        select(CoachThread).where(
            CoachThread.enrollment_id == enrollment.id,
            CoachThread.user_id == user.id,
        )
    ).first()
    if not thread:
        return None, []
    messages = db.scalars(
        select(CoachMessage)
        .where(CoachMessage.thread_id == thread.id)
        .order_by(CoachMessage.created_at.desc(), CoachMessage.id.desc())
        .limit(max(1, min(limit, _VISIBLE_HISTORY_LIMIT)))
    ).all()
    return thread, list(reversed(messages))


def _history_for_model(
    db: Session,
    thread_id: int,
    *,
    exclude_message_id: int | None = None,
) -> list[dict[str, str]]:
    statement = select(CoachMessage).where(CoachMessage.thread_id == thread_id)
    if exclude_message_id is not None:
        statement = statement.where(CoachMessage.id != exclude_message_id)
    messages = db.scalars(
        statement
        .order_by(CoachMessage.created_at.desc(), CoachMessage.id.desc())
        .limit(_MODEL_HISTORY_LIMIT)
    ).all()
    return [
        {
            "role": "assistant" if item.role == "assistant" else "user",
            "content": item.content[:_MODEL_HISTORY_MESSAGE_CHAR_LIMIT],
        }
        for item in reversed(messages)
    ]


def _public_citation(number: int, chunk: RetrievedChunk) -> dict[str, Any]:
    return {
        "source_number": number,
        "title": chunk.document_title,
        "scope": chunk.scope,
    }


def _audit_citation(number: int, chunk: RetrievedChunk) -> dict[str, Any]:
    return {"source_number": number, **chunk.citation()}


def _stage_visible_content(stage: CourseModuleStageContent) -> str:
    """Build a bounded, learner-visible source from the current approved stage.

    The RAG worker remains the primary source of truth.  This source exists
    only as a graceful fallback while an approved KB document is waiting to be
    indexed or the embedding provider is temporarily unavailable.  It never
    reads the private evaluation configuration stored beside a stage.
    """
    content = stage.content_json if isinstance(stage.content_json, dict) else {}
    parts: list[str] = [f"عنوان مرحله: {stage.title}"]

    intro = content.get("intro")
    if isinstance(intro, str) and intro.strip():
        parts.append(intro.strip())

    for block in content.get("blocks", []):
        if not isinstance(block, dict):
            continue
        title = block.get("title")
        if isinstance(title, str) and title.strip():
            parts.append(title.strip())
        body = block.get("body")
        if isinstance(body, str) and body.strip():
            parts.append(body.strip())
        for item in block.get("items", []):
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
            elif isinstance(item, dict):
                for key in ("front", "back", "point", "mistake", "correction", "question"):
                    value = item.get(key)
                    if isinstance(value, str) and value.strip():
                        parts.append(value.strip())
                options = item.get("options")
                if isinstance(options, list):
                    parts.extend(str(option).strip() for option in options if str(option).strip())

    activity = content.get("activity")
    if isinstance(activity, dict):
        for key in ("title", "prompt"):
            value = activity.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())

    # De-duplicate deterministically and keep this emergency source small
    # enough for a model request.  The full version-scoped KB remains the
    # preferred context whenever retrieval is ready.
    seen: set[str] = set()
    unique_parts = []
    for part in parts:
        normalized = " ".join(part.split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique_parts.append(normalized)
    return "\n".join(unique_parts)[:4200]


def _current_stage_fallback_source(stage: CourseModuleStageContent) -> RetrievedChunk | None:
    content = _stage_visible_content(stage)
    if not content:
        return None
    return RetrievedChunk(
        # Negative IDs make it explicit in audit JSON that this is not a
        # persisted KB chunk.  No database foreign key points to this value.
        chunk_id=-(stage.id or 1),
        document_id=0,
        document_title=f"محتوای تاییدشده مرحله: {stage.title}",
        content=content,
        score=1.0,
        scope="current_stage",
    )


def _citations_from_numbers(
    source_numbers: Any,
    chunks: list[RetrievedChunk],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(source_numbers, list):
        raise ValueError("Coach response has no source number list.")

    public: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    seen: set[int] = set()
    for value in source_numbers:
        if not isinstance(value, int) or value in seen or value < 1 or value > len(chunks):
            continue
        seen.add(value)
        chunk = chunks[value - 1]
        public.append(_public_citation(value, chunk))
        audit.append(_audit_citation(value, chunk))
    if not public:
        raise ValueError("Coach response did not cite a retrieved source.")
    return public, audit


def _fallback_without_sources() -> str:
    return (
        "در منابع تاییدشده‌ی این سرفصل، پاسخ قابل اتکایی برای این سؤال پیدا نکردم. "
        "سؤالت را با یکی از مفهوم‌های همین درس مطرح کن تا دقیق‌تر کنارت باشم."
    )


def _fallback_after_model_error(chunks: list[RetrievedChunk]) -> str:
    titles = "، ".join(chunk.document_title for chunk in chunks[:2])
    return (
        "منابع مرتبط پیدا شد، اما پاسخ کوچ در این لحظه با خطا روبه‌رو شد. "
        f"فعلاً بخش «{titles}» را مرور کن و کمی بعد دوباره سؤالت را بپرس."
    )


async def answer_course_question(
    db: Session,
    *,
    user: User,
    enrollment: UserCourseEnrollment,
    stage: CourseModuleStageContent,
    stage_number: int,
    question: str,
) -> CoachReply:
    """Store a learner question and an auditable, KB-grounded reply.

    The caller owns the transaction and must commit after this function returns.
    """
    clean_question = question.strip()
    if not clean_question:
        raise ValueError("Coach question cannot be empty.")
    if not stage.course_module:
        raise ValueError("The learning stage is missing its course module.")
    course = db.get(Course, enrollment.course_id)
    if not course:
        raise ValueError("The enrolled course no longer exists.")

    thread = get_or_create_coach_thread(db, user=user, enrollment=enrollment)
    learner_message = CoachMessage(
        thread_id=thread.id,
        module_stage_content_id=stage.id,
        role="user",
        content=clean_question,
        content_json={"stage_number": stage_number},
    )
    db.add(learner_message)
    db.flush()

    started = perf_counter()
    retrieval = await retrieve_course_chunks(
        db,
        course_version_id=enrollment.course_version_id,
        module_id=stage.course_module_id,
        question=clean_question,
    )

    status = "ok"
    error_message = retrieval.error_message
    suggested_action: str | None = None
    public_citations: list[dict[str, Any]] = []
    audit_citations: list[dict[str, Any]] = []
    model: str | None = None
    source_chunks = retrieval.chunks
    retrieval_method = retrieval.method

    if not source_chunks:
        # A newly published course can have approved stage material before its
        # background embedding job finishes.  Keep the coach useful, but mark
        # the source honestly and never substitute content from another module.
        stage_fallback = _current_stage_fallback_source(stage)
        if stage_fallback:
            source_chunks = [stage_fallback]
            retrieval_method = "stage_content_fallback"
            status = "stage_fallback"

    if not source_chunks:
        answer = _fallback_without_sources()
        grounded = False
        status = "no_grounding"
    else:
        try:
            context = build_personalized_context(user, enrollment, stage, stage_number, course)
            request_payload = {
                "learner_question": clean_question,
                "learner_context": context,
                # The current question is already represented by learner_question.
                # Excluding it prevents redundant prompt tokens on every request.
                "conversation_history": _history_for_model(
                    db,
                    thread.id,
                    exclude_message_id=learner_message.id,
                ),
                "retrieved_sources": format_retrieved_context(source_chunks),
            }
            raw_response = await ask_ai(
                load_prompt("course_coach_response.md"),
                json.dumps(request_payload, ensure_ascii=False),
                temperature=0.2,
                # The prompt and parser both require an object. Request it at
                # the gateway level too, so a conversational prose reply does
                # not turn a grounded answer into an avoidable fallback.
                response_format={"type": "json_object"},
            )
            parsed = parse_json_object(raw_response)
            answer = str(parsed.get("answer") or "").strip()
            if not answer:
                raise ValueError("Coach response contains no answer.")
            answer = answer[:2500]
            public_citations, audit_citations = _citations_from_numbers(
                parsed.get("source_numbers"),
                source_chunks,
            )
            candidate_action = parsed.get("suggested_action")
            if isinstance(candidate_action, str) and candidate_action.strip():
                suggested_action = candidate_action.strip()[:500]
            grounded = True
            model = get_settings().arvan_model
        except (ArvanAIError, ValueError, TypeError) as exc:
            answer = _fallback_after_model_error(source_chunks)
            public_citations = [_public_citation(index, chunk) for index, chunk in enumerate(source_chunks, start=1)]
            audit_citations = [_audit_citation(index, chunk) for index, chunk in enumerate(source_chunks, start=1)]
            grounded = True
            status = "fallback"
            error_message = str(exc)[:1000]

    now = datetime.now(timezone.utc)
    assistant_message = CoachMessage(
        thread_id=thread.id,
        module_stage_content_id=stage.id,
        role="assistant",
        content=answer,
        content_json={
            "grounded": grounded,
            "citations": public_citations,
            "suggested_action": suggested_action,
        },
        model=model,
        prompt_version=COACH_PROMPT_VERSION,
    )
    db.add(assistant_message)
    db.flush()
    db.add(
        CoachRetrievalEvent(
            assistant_message_id=assistant_message.id,
            rag_config_id=retrieval.rag_config.id if retrieval.rag_config else None,
            retrieval_method=retrieval_method,
            source_chunks_json=audit_citations,
            grounded=grounded,
            latency_ms=round((perf_counter() - started) * 1000),
            status=status,
            error_message=error_message,
        )
    )
    thread.last_message_at = now

    return CoachReply(
        thread=thread,
        assistant_message=assistant_message,
        grounded=grounded,
        citations=public_citations,
        retrieval_method=retrieval_method,
        suggested_action=suggested_action,
    )
