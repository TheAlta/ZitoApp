"""Versioned CMS authoring for Zito courses.

The service deliberately keeps generated content in a draft version until an
admin publishes it. Learner enrollments remain pinned to their original
course version, so publishing a revision cannot change an active path.
"""

from __future__ import annotations

import asyncio
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.lib.arvan_client import ArvanAIError, ask_ai
from src.models import (
    Course,
    CourseKbDocument,
    CourseKbDocumentModule,
    CourseModule,
    CourseModuleStageContent,
    CourseVersion,
    Exam,
    LearningStageTemplate,
)
from src.prompts import load_prompt
from src.services.json_utils import parse_json_object
from src.services.rag import document_content_checksum, ensure_course_rag_config, sync_document_chunks


CMS_OUTLINE_PROMPT_VERSION = "cms-course-outline-v1"
CMS_MODULE_PROMPT_VERSION = "cms-course-module-v1"
CMS_MODULE_STAGE_COUNT = 8
CMS_SUPPORTED_STAGE_COUNTS = {7, 8, 9}

_STAGE_FLOWS: dict[int, tuple[str, ...]] = {
    7: (
        "learning_path",
        "lesson_summary",
        "flashcards",
        "golden_tips",
        "common_mistakes",
        "module_assessment",
        "module_completion",
    ),
    8: (
        "learning_path",
        "lesson_summary",
        "flashcards",
        "golden_tips",
        "common_mistakes",
        "personalized_work_example",
        "module_assessment",
        "module_completion",
    ),
    9: (
        "learning_path",
        "lesson_summary",
        "flashcards",
        "golden_tips",
        "common_mistakes",
        "personalized_work_example",
        "qa",
        "module_assessment",
        "module_completion",
    ),
}

_STAGE_TITLES = {
    "learning_path": "مسیر یادگیری این سرفصل",
    "lesson_summary": "خلاصه درس",
    "flashcards": "فلش کارت‌های مرور سریع",
    "golden_tips": "نکات طلایی درس",
    "common_mistakes": "اشتباهات رایج",
    "personalized_work_example": "مثال در مسیر شغلی تو",
    "qa": "پرسش و پاسخ کلیدی",
    "module_assessment": "تمرین و آزمونک سرفصل",
    "module_completion": "پایان سرفصل",
}


class CmsError(ValueError):
    """A user-actionable course authoring error."""


@dataclass(frozen=True)
class GeneratedModule:
    number: int
    title: str
    description: str
    learning_objectives: list[str]
    tags: list[str]
    stages: list[dict[str, Any]]
    knowledge_base: str


@dataclass(frozen=True)
class GeneratedCurriculum:
    overview: dict[str, Any]
    modules: list[GeneratedModule]


def stage_flow(stage_count: int) -> tuple[str, ...]:
    try:
        return _STAGE_FLOWS[stage_count]
    except KeyError as exc:
        raise CmsError("تعداد ایستگاه هر سرفصل باید ۷، ۸ یا ۹ باشد.") from exc


def course_version_title(course: Course, version: CourseVersion) -> str:
    """Return the title snapshot carried by a version, with legacy fallback."""

    brief = version.authoring_brief_json if isinstance(version.authoring_brief_json, dict) else {}
    title = str(brief.get("title") or "").strip()
    return title or course.title


def course_version_domain(course: Course, version: CourseVersion) -> str:
    """Return the version's domain without rewriting the course's legacy value."""

    brief = version.authoring_brief_json if isinstance(version.authoring_brief_json, dict) else {}
    domain = str(brief.get("domain") or brief.get("topic") or "").strip()
    return domain or course.domain


def slugify_course(value: str) -> str:
    ascii_value = value.strip().lower()
    ascii_value = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    if not ascii_value:
        ascii_value = "course"
    return ascii_value[:100]


def _next_slug(db: Session, requested_slug: str) -> str:
    base = slugify_course(requested_slug)
    candidate = base
    suffix = 2
    while db.scalar(select(Course.id).where(Course.slug == candidate).limit(1)) is not None:
        candidate = f"{base[:100 - len(str(suffix)) - 1]}-{suffix}"
        suffix += 1
    return candidate


def _next_version_number(db: Session, course_id: int) -> int:
    current = db.scalar(
        select(func.max(CourseVersion.version_number)).where(CourseVersion.course_id == course_id)
    )
    return int(current or 0) + 1


def create_course_draft(db: Session, brief: dict[str, Any]) -> tuple[Course, CourseVersion]:
    """Create a new, isolated draft; it is invisible to learners until publish."""
    title = str(brief.get("title") or "").strip()
    topic = str(brief.get("topic") or "").strip()
    if not title or not topic:
        raise CmsError("نام و موضوع دوره باید وارد شوند.")

    # CMS courses always use Zito's established eight-station learning flow.
    stage_count = CMS_MODULE_STAGE_COUNT
    brief = {**brief, "module_stage_count": stage_count}
    requested_slug = str(brief.get("slug") or title)
    course = Course(
        title=title,
        slug=_next_slug(db, requested_slug),
        domain=str(brief.get("domain") or topic)[:120],
        status="draft",
    )
    db.add(course)
    db.flush()
    version = CourseVersion(
        course_id=course.id,
        version_number=1,
        status="draft",
        source="cms",
        authoring_brief_json=brief,
        module_stage_count=stage_count,
        requires_final_exam=bool(brief.get("requires_final_exam", True)),
        generation_status="not_requested",
    )
    db.add(version)
    db.flush()
    return course, version


def create_course_revision(db: Session, course: Course) -> CourseVersion:
    """Clone the current published version into an editable, unlisted draft."""
    source = db.scalars(
        select(CourseVersion)
        .where(CourseVersion.course_id == course.id, CourseVersion.status == "published")
        .order_by(CourseVersion.version_number.desc())
    ).first()
    if not source:
        raise CmsError("برای این دوره نسخه منتشرشده‌ای برای ویرایش وجود ندارد.")
    version = CourseVersion(
        course_id=course.id,
        version_number=_next_version_number(db, course.id),
        status="draft",
        source="cms_revision",
        overview_json=deepcopy(source.overview_json),
        authoring_brief_json=deepcopy(source.authoring_brief_json),
        module_stage_count=CMS_MODULE_STAGE_COUNT,
        requires_final_exam=source.requires_final_exam,
        generation_status="edited",
        generation_model=source.generation_model,
        generation_prompt_version=source.generation_prompt_version,
    )
    db.add(version)
    db.flush()
    modules = db.scalars(
        select(CourseModule)
        .where(CourseModule.course_version_id == source.id)
        .order_by(CourseModule.module_number)
    ).all()
    for source_module in modules:
        module = CourseModule(
            course_version_id=version.id,
            module_number=source_module.module_number,
            title=source_module.title,
            description=source_module.description,
            learning_objectives_json=deepcopy(source_module.learning_objectives_json),
            tags_json=deepcopy(source_module.tags_json),
            status="draft",
        )
        db.add(module)
        db.flush()
        stages = db.scalars(
            select(CourseModuleStageContent)
            .where(CourseModuleStageContent.course_module_id == source_module.id)
            .order_by(CourseModuleStageContent.stage_number)
        ).all()
        for source_stage in stages:
            db.add(
                CourseModuleStageContent(
                    course_module_id=module.id,
                    template_id=source_stage.template_id,
                    stage_number=source_stage.stage_number,
                    title=source_stage.title,
                    content_json=deepcopy(source_stage.content_json),
                    evaluation_config_json=deepcopy(source_stage.evaluation_config_json),
                    status="draft",
                    ai_generation_status="inherited",
                    review_status="pending",
                    content_version=source_stage.content_version,
                )
            )
    db.flush()
    return version


def _as_strings(value: Any, *, limit: int = 8) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip()[:300] for item in value if str(item).strip()][:limit]


def _required_string(value: Any, label: str, maximum: int = 2000) -> str:
    text = str(value or "").strip()
    if not text:
        raise CmsError(f"AI برای «{label}» محتوای معتبری برنگرداند.")
    return text[:maximum]


def _module_from_response(data: dict[str, Any], number: int, stage_count: int) -> GeneratedModule:
    expected_flow = stage_flow(stage_count)
    raw_stages = data.get("stages")
    if not isinstance(raw_stages, list) or len(raw_stages) != stage_count:
        raise CmsError(f"AI باید برای هر سرفصل دقیقاً {stage_count} ایستگاه بسازد.")

    stages: list[dict[str, Any]] = []
    for index, stage_type in enumerate(expected_flow, start=1):
        raw_stage = raw_stages[index - 1] if isinstance(raw_stages[index - 1], dict) else {}
        if raw_stage.get("type") != stage_type:
            raise CmsError("ترتیب قالب‌های تولیدشده با مسیر آموزشی انتخاب‌شده هم‌خوان نیست.")
        content = raw_stage.get("content")
        if not isinstance(content, dict):
            raise CmsError(f"محتوای ایستگاه {index} معتبر نیست.")
        stages.append(
            {
                "stage_number": index,
                "type": stage_type,
                "title": _required_string(raw_stage.get("title") or _STAGE_TITLES[stage_type], "عنوان ایستگاه", 255),
                "content_json": content,
                "evaluation_config_json": raw_stage.get("evaluation_config") if isinstance(raw_stage.get("evaluation_config"), dict) else None,
            }
        )

    return GeneratedModule(
        number=number,
        title=_required_string(data.get("title"), "عنوان سرفصل", 255),
        description=_required_string(data.get("description"), "توضیح سرفصل"),
        learning_objectives=_as_strings(data.get("learning_objectives"), limit=6),
        tags=_as_strings(data.get("tags"), limit=10),
        stages=stages,
        knowledge_base=_required_string(data.get("knowledge_base"), "دانش پایه سرفصل", 12000),
    )


def _overview_from_response(data: dict[str, Any], brief: dict[str, Any]) -> dict[str, Any]:
    required = ("summary", "description")
    for field in required:
        _required_string(data.get(field), field)
    hours = int(brief.get("estimated_learning_hours") or 0)
    return {
        "summary": _required_string(data.get("summary"), "خلاصه دوره", 800),
        "description": _required_string(data.get("description"), "توضیح دوره", 3000),
        "estimated_learning_minutes": hours * 60 if hours > 0 else None,
        "estimated_duration_label": str(brief.get("duration") or "").strip(),
        "learning_outcomes": _as_strings(data.get("learning_outcomes"), limit=6),
        "career_outcomes": _as_strings(data.get("career_outcomes"), limit=5),
        "daily_life_outcomes": _as_strings(data.get("daily_life_outcomes"), limit=5),
        "final_exam_label": str(data.get("final_exam_label") or "آزمون نهایی دوره").strip()[:255],
        "topic": str(brief.get("topic") or "").strip(),
        "audience": str(brief.get("audience") or "").strip(),
        "target_group": str(brief.get("target_group") or "").strip(),
        "level": str(brief.get("level") or "").strip(),
    }


def _mock_stage_content(stage_type: str, module: dict[str, Any], brief: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    title = str(module["title"])
    topic = str(brief["topic"])
    objective = str((module.get("learning_objectives") or ["یک مهارت کاربردی"])[0])
    base = {
        "intro": f"در این بخش از {title} یاد می‌گیری چگونه {objective} را در موضوع {topic} به یک اقدام واقعی تبدیل کنی.",
        "coaching": {"prompt": "هر سوالی درباره این بخش داری از زیتو بپرس.", "mode": "live", "enabled": True},
        "ui_hint": {"template": stage_type, "avatar_visible": True, "primary_action": "ثبت و ادامه"},
        "module": {"title": title},
    }
    if stage_type == "learning_path":
        base["blocks"] = [{"kind": "timeline", "title": "مسیر این سرفصل", "items": ["مسئله را روشن کن", "یک اقدام کوچک انتخاب کن", "نتیجه را مرور کن"]}]
        base["activity"] = {"kind": "planning", "title": "نقطه شروع", "prompt": f"یک موقعیت واقعی مرتبط با {title} انتخاب کن."}
    elif stage_type == "flashcards":
        base["blocks"] = [{"kind": "flashcards", "title": "مرور مفاهیم", "items": [{"front": title, "back": f"کاربرد آن در {topic}"}, {"front": "قدم کوچک", "back": "اقدامی که قابل انجام و قابل سنجش باشد."}]}]
        base["activity"] = {"kind": "review", "title": "مرور", "prompt": "یک مفهوم را با زبان خودت توضیح بده."}
    elif stage_type == "golden_tips":
        base["blocks"] = [{"kind": "tips", "title": "نکات کاربردی", "items": ["از مسئله واقعی شروع کن.", "نتیجه را با شواهد بررسی کن.", "قدم بعدی را کوچک نگه دار."]}]
        base["activity"] = {"kind": "selection", "title": "تمرین", "prompt": "یکی از نکات را برای این هفته انتخاب کن."}
    elif stage_type == "common_mistakes":
        base["blocks"] = [{"kind": "mistakes", "title": "خطا و راه اصلاح", "items": [{"mistake": "شروع با راه‌حل بدون شناخت مسئله", "correction": "اول موقعیت و نیاز واقعی را ثبت کن."}]}]
        base["activity"] = {"kind": "reflection", "title": "بازبینی", "prompt": "یک خطای احتمالی خودت را بنویس."}
    elif stage_type == "personalized_work_example":
        base["blocks"] = [{"kind": "paragraph", "title": "مثال حل‌شده", "body": f"یک نمونه کاربردی از {title} در محیط کار یا تحصیل تو."}, {"kind": "personalized_example", "title": "مثال مخصوص مسیر تو", "body": "زیتو در حال آماده‌سازی مثال شخصی‌سازی‌شده است."}]
        base["activity"] = {"kind": "application", "title": "حالا نوبت توست", "prompt": "این مثال را با یک موقعیت واقعی خودت تطبیق بده."}
    elif stage_type == "qa":
        base["blocks"] = [{"kind": "qa", "title": "پرسش‌های کلیدی", "items": [{"question": f"اولین قدم در {title} چیست؟", "answer": "شناخت مسئله و انتخاب یک اقدام کوچک و قابل مشاهده."}]}]
        base["activity"] = {"kind": "reflection", "title": "پرسش شخصی", "prompt": "مهم‌ترین سوال خودت را از زیتو بپرس."}
    elif stage_type == "module_assessment":
        question_id = "q1"
        options = ["شناخت مسئله و اقدام کوچک", "شروع مستقیم با ابزار", "نادیده گرفتن بازخورد"]
        base["blocks"] = [{"kind": "quiz", "title": "آزمونک", "items": [{"id": question_id, "question": f"برای شروع {title} کدام گزینه بهتر است؟", "options": options}]}]
        base["activity"] = {"kind": "assessment", "title": "ثبت پاسخ", "prompt": "به سوال پاسخ بده."}
        return base, {"pass_score": 60, "questions": [{"id": question_id, "correct_option": options[0], "weight": 100}]}
    elif stage_type == "module_completion":
        base["blocks"] = [{"kind": "highlight", "title": "جمع‌بندی", "body": f"تو مسیر اصلی {title} را تمام کردی و آماده سرفصل بعدی هستی."}]
        base["activity"] = {"kind": "continue", "title": "ادامه مسیر", "prompt": "یک نکته کاربردی را با خودت به مرحله بعد ببر."}
    else:
        base["blocks"] = [{"kind": "highlight", "title": title, "body": f"خلاصه‌ای کاربردی از {title} در موضوع {topic}."}]
        base["activity"] = {"kind": "reflection", "title": "تمرین درس", "prompt": "یک کاربرد واقعی بنویس."}
    return base, None


def _mock_curriculum(brief: dict[str, Any]) -> GeneratedCurriculum:
    module_count = int(brief["module_count"])
    stage_count = CMS_MODULE_STAGE_COUNT
    modules: list[GeneratedModule] = []
    for number in range(1, module_count + 1):
        module = {
            "title": f"سرفصل {number}: {brief['topic']}",
            "description": f"یک گام کاربردی از دوره {brief['title']} با تمرکز بر {brief['goal']}.",
            "learning_objectives": [f"کاربرد {brief['topic']} را در یک موقعیت واقعی تشخیص دهد."],
            "tags": [str(brief["topic"]), "کاربردی"],
        }
        stages = []
        for stage_number, stage_type in enumerate(stage_flow(stage_count), start=1):
            content, evaluation = _mock_stage_content(stage_type, module, brief)
            stages.append({"stage_number": stage_number, "type": stage_type, "title": _STAGE_TITLES[stage_type], "content_json": content, "evaluation_config_json": evaluation})
        modules.append(GeneratedModule(number=number, stages=stages, knowledge_base=f"دانش پایه سرفصل {number}: {module['description']}", **module))
    overview = {
        "summary": f"مسیر کاربردی {brief['title']} برای رسیدن به {brief['goal']}.",
        "description": f"این دوره با {module_count} سرفصل، مخاطب را از مفاهیم پایه تا کاربرد واقعی {brief['topic']} همراهی می‌کند.",
        "learning_outcomes": ["تبدیل مفهوم به اقدام", "مرور نتیجه و بهبود مسیر"],
        "career_outcomes": ["استفاده عملی در محیط کار یا تحصیل"],
        "daily_life_outcomes": ["ساخت عادت یادگیری کوتاه و پایدار"],
        "final_exam_label": "آزمون نهایی دوره",
    }
    return GeneratedCurriculum(_overview_from_response(overview, brief), modules)


async def generate_curriculum(brief: dict[str, Any]) -> GeneratedCurriculum:
    """Generate an outline then each module with the CMS model contract."""
    stage_count = CMS_MODULE_STAGE_COUNT
    brief = {**brief, "module_stage_count": stage_count}
    if get_settings().arvan_mock_ai:
        return _mock_curriculum(brief)

    settings = get_settings()
    model = settings.effective_content_generation_model
    outline_raw = await ask_ai(
        load_prompt("course_outline_generation.md"),
        json.dumps({"brief": brief}, ensure_ascii=False),
        temperature=0.35,
        response_format={"type": "json_object"},
        model=model,
        api_base_url=settings.effective_content_generation_api_base_url,
        api_key=settings.effective_content_generation_api_key,
        timeout_seconds=settings.arvan_content_generation_timeout_seconds,
        max_tokens=1100,
        reasoning_effort="low",
    )
    outline = parse_json_object(outline_raw)
    raw_modules = outline.get("modules")
    module_count = int(brief.get("module_count") or 0)
    if not isinstance(raw_modules, list) or len(raw_modules) != module_count:
        raise CmsError("AI تعداد سرفصل‌های درخواستی را تولید نکرد.")
    overview = _overview_from_response(outline.get("overview") if isinstance(outline.get("overview"), dict) else {}, brief)

    async def generate_module(number: int, module_outline: Any) -> GeneratedModule:
        if not isinstance(module_outline, dict):
            raise CmsError("فهرست سرفصل‌های تولیدشده معتبر نیست.")
        module_raw = await ask_ai(
            load_prompt("course_module_generation.md"),
            json.dumps(
                {
                    "brief": brief,
                    "module": module_outline,
                    "module_number": number,
                    "stage_flow": [
                        {"type": stage_type, "title": _STAGE_TITLES[stage_type]}
                        for stage_type in stage_flow(stage_count)
                    ],
                },
                ensure_ascii=False,
            ),
            temperature=0.35,
            response_format={"type": "json_object"},
            model=model,
            api_base_url=settings.effective_content_generation_api_base_url,
            api_key=settings.effective_content_generation_api_key,
            timeout_seconds=settings.arvan_content_generation_timeout_seconds,
            max_tokens=2600,
            reasoning_effort="low",
        )
        return _module_from_response(parse_json_object(module_raw), number, stage_count)

    modules = list(
        await asyncio.gather(
            *(generate_module(number, module_outline) for number, module_outline in enumerate(raw_modules, start=1))
        )
    )
    return GeneratedCurriculum(overview=overview, modules=modules)


def replace_draft_curriculum(db: Session, version: CourseVersion, curriculum: GeneratedCurriculum) -> None:
    """Replace only draft generated content; published versions are immutable."""
    if version.status == "published":
        raise CmsError("نسخه منتشرشده قابل بازنویسی نیست؛ یک نسخه جدید بساز.")
    expected_count = CMS_MODULE_STAGE_COUNT
    stage_flow(expected_count)
    template_by_code = {
        item.code: item
        for item in db.scalars(
            select(LearningStageTemplate).where(LearningStageTemplate.is_active.is_(True))
        ).all()
    }
    required_templates = set(stage_flow(expected_count))
    missing = sorted(required_templates - set(template_by_code))
    if missing:
        raise CmsError(f"قالب‌های آموزشی فعال نیستند: {', '.join(missing)}")

    for module in list(version.modules):
        db.delete(module)
    db.flush()

    for generated in curriculum.modules:
        module = CourseModule(
            course_version_id=version.id,
            module_number=generated.number,
            title=generated.title,
            description=generated.description,
            learning_objectives_json=generated.learning_objectives,
            tags_json=generated.tags,
            status="draft",
        )
        db.add(module)
        db.flush()
        for stage in generated.stages:
            db.add(
                CourseModuleStageContent(
                    course_module_id=module.id,
                    template_id=template_by_code[stage["type"]].id,
                    stage_number=stage["stage_number"],
                    title=stage["title"],
                    content_json=stage["content_json"],
                    evaluation_config_json=stage["evaluation_config_json"],
                    status="draft",
                    ai_generation_status="generated",
                    review_status="pending",
                    generated_at=datetime.now(timezone.utc),
                )
            )
    version.overview_json = curriculum.overview
    version.generation_status = "generated"
    version.generation_model = get_settings().effective_content_generation_model
    version.generation_prompt_version = f"{CMS_OUTLINE_PROMPT_VERSION}+{CMS_MODULE_PROMPT_VERSION}"
    version.generation_error = None
    version.generated_at = datetime.now(timezone.utc)
    db.flush()


def _visible_content_text(value: Any) -> list[str]:
    """Turn learner-facing stage JSON into an auditable KB source.

    Answer keys live in ``evaluation_config_json`` and never pass through this
    function, so the coach cannot disclose them from retrieval context.
    """
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            parts.extend(_visible_content_text(item))
        return parts
    if not isinstance(value, dict):
        return []
    parts: list[str] = []
    for key, item in value.items():
        if key in {"coaching", "ui_hint", "media_slots"}:
            continue
        parts.extend(_visible_content_text(item))
    return parts


def _module_knowledge_source(module: CourseModule) -> str:
    parts = [
        f"عنوان سرفصل: {module.title}",
        f"توضیح: {module.description or ''}",
        "اهداف: " + " | ".join(str(item) for item in module.learning_objectives_json or []),
    ]
    for stage in sorted(module.stage_contents, key=lambda item: item.stage_number):
        parts.append(f"ایستگاه {stage.stage_number}: {stage.title}")
        parts.extend(_visible_content_text(stage.content_json))
    unique: list[str] = []
    seen: set[str] = set()
    for part in parts:
        normalized = " ".join(str(part).split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return "\n\n".join(unique)[:24000]


def _final_exam_questions(course: Course, version: CourseVersion, modules: list[CourseModule]) -> list[dict[str, Any]]:
    brief = version.authoring_brief_json if isinstance(version.authoring_brief_json, dict) else {}
    goal = str(brief.get("goal") or "هدف اصلی دوره")
    module_titles = "، ".join(module.title for module in modules[:3])
    course_title = course_version_title(course, version)
    return [
        {
            "id": "final-q-1",
            "type": "open",
            "question": f"توضیح بده چگونه آموخته‌های «{course_title}» را برای {goal} به یک اقدام قابل سنجش تبدیل می‌کنی.",
            "rubric": "مسئله روشن، اقدام کوچک، معیار سنجش و مرور نتیجه را بیان کند.",
            "max_score": 34,
        },
        {
            "id": "final-q-2",
            "type": "scenario",
            "question": f"در یک موقعیت واقعی، از کدام بخش‌های دوره ({module_titles}) استفاده می‌کنی و چرا؟",
            "rubric": "حداقل دو مفهوم دوره را به یک موقعیت واقعی و تصمیم قابل دفاع وصل کند.",
            "max_score": 33,
        },
        {
            "id": "final-q-3",
            "type": "open",
            "question": "برای ادامه یادگیری بعد از پایان دوره چه بازخوردی جمع می‌کنی و چگونه مسیرت را اصلاح می‌کنی؟",
            "rubric": "یک روش مشخص برای ثبت شواهد، بازبینی و اصلاح اقدام بعدی ارائه کند.",
            "max_score": 33,
        },
    ]


def publish_draft_version(db: Session, course: Course, version: CourseVersion) -> int:
    """Validate and publish one immutable course version, then queue its KB."""
    if version.status == "published":
        raise CmsError("این نسخه قبلاً منتشر شده است.")
    if version.generation_status in {"generating", "needs_regeneration", "failed"}:
        raise CmsError("پیش‌نویس با چارچوب فعلی آماده انتشار نیست؛ ابتدا تولید AI را کامل کن.")
    brief = version.authoring_brief_json if isinstance(version.authoring_brief_json, dict) else {}
    expected_module_count = int(brief.get("module_count") or 0)
    expected_stage_count = version.module_stage_count or CMS_MODULE_STAGE_COUNT
    if expected_stage_count != CMS_MODULE_STAGE_COUNT:
        raise CmsError("نسخه‌های CMS باید با جریان ثابت ۸ ایستگاه تولید شوند؛ ابتدا دوباره تولید کن.")
    expected_flow = stage_flow(expected_stage_count)
    modules = db.scalars(
        select(CourseModule)
        .where(CourseModule.course_version_id == version.id)
        .order_by(CourseModule.module_number)
    ).all()
    if not modules or len(modules) != expected_module_count:
        raise CmsError("تعداد سرفصل‌های آماده با تعداد سرفصل‌های درخواستی یکسان نیست.")
    if [module.module_number for module in modules] != list(range(1, expected_module_count + 1)):
        raise CmsError("شماره‌گذاری سرفصل‌ها پیوسته نیست.")

    all_stages = db.scalars(
        select(CourseModuleStageContent)
        .where(CourseModuleStageContent.course_module_id.in_([module.id for module in modules]))
        .order_by(CourseModuleStageContent.course_module_id, CourseModuleStageContent.stage_number)
    ).all()
    by_module: dict[int, list[CourseModuleStageContent]] = {}
    for stage in all_stages:
        by_module.setdefault(stage.course_module_id, []).append(stage)
    template_ids = {
        item.id: item.code
        for item in db.scalars(select(LearningStageTemplate)).all()
    }
    for module in modules:
        stages = by_module.get(module.id, [])
        if len(stages) != expected_stage_count:
            raise CmsError(f"سرفصل «{module.title}» همه ایستگاه‌های لازم را ندارد.")
        if [stage.stage_number for stage in stages] != list(range(1, expected_stage_count + 1)):
            raise CmsError(f"شماره ایستگاه‌های «{module.title}» پیوسته نیست.")
        if [template_ids.get(stage.template_id) for stage in stages] != list(expected_flow):
            raise CmsError(f"قالب ایستگاه‌های «{module.title}» با مسیر آموزشی انتخاب‌شده هم‌خوان نیست.")
        for stage in stages:
            if not isinstance(stage.content_json, dict) or not stage.content_json.get("blocks"):
                raise CmsError(f"محتوای «{stage.title}» کامل نیست.")

    now = datetime.now(timezone.utc)
    for module in modules:
        module.status = "approved"
    for stage in all_stages:
        stage.status = "approved"
        stage.review_status = "approved"
        stage.reviewed_by = "cms_publish"
        stage.reviewed_at = now

    stale_documents = db.scalars(
        select(CourseKbDocument).where(
            CourseKbDocument.course_version_id == version.id,
            CourseKbDocument.source_type == "cms",
        )
    ).all()
    for document in stale_documents:
        db.delete(document)
    db.flush()

    documents: list[CourseKbDocument] = []
    course_title = course_version_title(course, version)
    for module in modules:
        document = CourseKbDocument(
            course_id=course.id,
            course_version_id=version.id,
            title=f"{course_title} | {module.title}",
            content=_module_knowledge_source(module),
            content_checksum="",
            tags=",".join(str(item) for item in module.tags_json or [])[:255],
            source_type="cms",
            source_reference=f"cms:course:{course.id}:version:{version.id}:module:{module.module_number}",
            status="approved",
        )
        document.content_checksum = document_content_checksum(document.content)
        db.add(document)
        db.flush()
        db.add(
            CourseKbDocumentModule(
                document_id=document.id,
                course_module_id=module.id,
                course_version_id=version.id,
            )
        )
        documents.append(document)

    config = ensure_course_rag_config(db, version.id)
    config.knowledge_base_ref = f"cms:course:{course.id}:version:{version.id}"
    config.status = "ready"
    index_changes = sync_document_chunks(db, documents, enqueue_jobs=True)

    if version.requires_final_exam:
        db.add(
            Exam(
                course_version_id=version.id,
                title=f"آزمون نهایی {course_title}",
                questions_json=_final_exam_questions(course, version, modules),
                passing_score=70,
                status="published",
            )
        )
    version.status = "published"
    version.published_at = now
    version.generation_status = "published"
    course.status = "published"
    db.flush()
    return index_changes
