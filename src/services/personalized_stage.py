"""Generate and cache a safe, RAG-grounded work example for a learning stage."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from src.config import get_settings
from src.lib.arvan_client import ArvanAIError, ask_ai
from src.models import Course, CourseModuleStageContent, User, UserCourseEnrollment
from src.prompts import load_prompt
from src.services.coach import build_personalized_context
from src.services.json_utils import parse_json_object
from src.services.rag import RetrievedChunk, format_retrieved_context, retrieve_course_chunks


PERSONALIZED_WORK_EXAMPLE_PROMPT_VERSION = "personalized-work-example-v1"


@dataclass(frozen=True)
class PersonalizedStageContent:
    content: dict[str, Any]
    citations: list[dict[str, Any]]
    grounded: bool
    model: str | None
    prompt_version: str


def _public_citation(number: int, chunk: RetrievedChunk) -> dict[str, Any]:
    return {
        "source_number": number,
        "title": chunk.document_title,
        "scope": chunk.scope,
    }


def _citations_from_numbers(source_numbers: Any, chunks: list[RetrievedChunk]) -> list[dict[str, Any]]:
    if not isinstance(source_numbers, list):
        raise ValueError("Personalized example has no source number list.")
    citations: list[dict[str, Any]] = []
    seen: set[int] = set()
    for value in source_numbers:
        if not isinstance(value, int) or value in seen or value < 1 or value > len(chunks):
            continue
        seen.add(value)
        citations.append(_public_citation(value, chunks[value - 1]))
    if not citations:
        raise ValueError("Personalized example did not cite a retrieved source.")
    return citations


def _fallback_content(user: User, stage: CourseModuleStageContent) -> dict[str, Any]:
    module = stage.course_module
    profile = user.profile
    field = (profile.work_or_study_field if profile else None) or "مسیر فعلی تو"
    module_title = module.title if module else "این سرفصل"
    return {
        "title": f"یک مثال کاربردی در {field}",
        "scenario": (
            f"در {field}، یک موقعیت واقعی را انتخاب کن که «{module_title}» بتواند تصمیم یا برنامه‌ریزی تو را روشن‌تر کند."
        ),
        "application_steps": [
            "مسئله را در دو یا سه جمله و بدون داده حساس مشخص کن.",
            "یک پیشنهاد اولیه از AI بگیر و فرض‌های آن را جدا کن.",
            "پیشنهاد را با شرایط واقعی و بررسی انسانی خودت تطبیق بده.",
        ],
        "reflection_question": "این مثال در کار یا مسیر تحصیلی تو چه تفاوتی با یک مثال عمومی دارد؟",
    }


def _parse_model_content(payload: dict[str, Any]) -> dict[str, Any]:
    title = str(payload.get("title") or "").strip()[:180]
    scenario = str(payload.get("scenario") or "").strip()[:1200]
    reflection_question = str(payload.get("reflection_question") or "").strip()[:500]
    steps_raw = payload.get("application_steps")
    steps = [str(item).strip()[:400] for item in steps_raw] if isinstance(steps_raw, list) else []
    steps = [item for item in steps if item][:4]
    if not title or not scenario or not reflection_question or not steps:
        raise ValueError("Personalized example response is incomplete.")
    return {
        "title": title,
        "scenario": scenario,
        "application_steps": steps,
        "reflection_question": reflection_question,
    }


async def generate_personalized_work_example(
    db: Session,
    *,
    user: User,
    enrollment: UserCourseEnrollment,
    stage: CourseModuleStageContent,
    stage_number: int,
) -> PersonalizedStageContent:
    """Build one personal example without sending phone, IDs or referral data to AI."""

    if not stage.course_module:
        raise ValueError("The learning stage is missing its course module.")
    course = db.get(Course, enrollment.course_id)
    if not course:
        raise ValueError("The enrolled course no longer exists.")

    retrieval_question = (
        f"یک مثال کاربردی و مسئولانه درباره {stage.course_module.title} "
        "برای یک یادگیرنده در مسیر شغلی خودش"
    )
    retrieval = await retrieve_course_chunks(
        db,
        course_version_id=enrollment.course_version_id,
        module_id=stage.course_module_id,
        question=retrieval_question,
    )
    fallback = _fallback_content(user, stage)
    if not retrieval.chunks:
        return PersonalizedStageContent(
            content=fallback,
            citations=[],
            grounded=False,
            model=None,
            prompt_version=PERSONALIZED_WORK_EXAMPLE_PROMPT_VERSION,
        )

    try:
        request_payload = {
            "learner_context": build_personalized_context(user, enrollment, stage, stage_number, course),
            "retrieved_sources": format_retrieved_context(retrieval.chunks),
        }
        raw_response = await ask_ai(
            load_prompt("personalized_work_example.md"),
            json.dumps(request_payload, ensure_ascii=False),
            temperature=0.25,
            response_format={"type": "json_object"},
        )
        parsed = parse_json_object(raw_response)
        content = _parse_model_content(parsed)
        citations = _citations_from_numbers(parsed.get("source_numbers"), retrieval.chunks)
        return PersonalizedStageContent(
            content=content,
            citations=citations,
            grounded=True,
            model=get_settings().arvan_model,
            prompt_version=PERSONALIZED_WORK_EXAMPLE_PROMPT_VERSION,
        )
    except (ArvanAIError, ValueError, TypeError):
        return PersonalizedStageContent(
            content=fallback,
            citations=[_public_citation(index, chunk) for index, chunk in enumerate(retrieval.chunks, start=1)],
            grounded=True,
            model=None,
            prompt_version=PERSONALIZED_WORK_EXAMPLE_PROMPT_VERSION,
        )
