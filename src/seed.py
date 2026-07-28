from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from src.config import get_settings
from src.models import (
    Admin,
    Course,
    CourseKbDocument,
    CourseStageContent,
    CourseVersion,
    Exam,
)
from src.security import hash_password


PHASE2_SAMPLE_COURSE = {
    "title": "توسعه فردی با هوش مصنوعی",
    "slug": "personal-development-ai",
    "domain": "personal_development",
}

PHASE2_STAGE_TYPES = [
    {"number": 1, "type": "lesson_summary", "title": "خلاصه درس"},
    {"number": 2, "type": "flashcards", "title": "فلش کارت ها و مرور سریع مفاهیم"},
    {"number": 3, "type": "qa", "title": "پرسش و پاسخ"},
    {"number": 4, "type": "learning_path", "title": "نمایش مسیر یادگیری"},
    {"number": 5, "type": "mini_quiz", "title": "آزمون کوچک برای تثبیت یادگیری"},
    {"number": 6, "type": "multiple_choice", "title": "سوال های چهارگزینه ای"},
    {"number": 7, "type": "real_examples", "title": "مثال های واقعی"},
    {"number": 8, "type": "interactive_scenario", "title": "سناریوهای تعاملی"},
    {"number": 9, "type": "checklist", "title": "چک لیست اجرایی"},
    {"number": 10, "type": "practical_exercise", "title": "تمرین عملی"},
    {"number": 11, "type": "daily_mission", "title": "ماموریت روزانه و چالش کوچک"},
    {"number": 12, "type": "avatar_dialog", "title": "گفت و گو با آواتار"},
    {"number": 13, "type": "smart_review", "title": "مرور هوشمند"},
    {"number": 14, "type": "audio_summary", "title": "خلاصه صوتی درس"},
    {"number": 15, "type": "infographic", "title": "اینفوگرافیک مفاهیم مهم"},
    {"number": 16, "type": "mind_map", "title": "نقشه ذهنی"},
    {"number": 17, "type": "golden_tips", "title": "کارت های نکات طلایی"},
    {"number": 18, "type": "common_mistakes", "title": "اشتباهات رایج"},
    {"number": 19, "type": "personalized_path", "title": "مسیر شخصی سازی شده"},
    {"number": 20, "type": "final_project", "title": "پروژه نهایی و جمع بندی"},
]

PHASE2_SAMPLE_KB = [
    {
        "title": "اصول توسعه فردی با هوش مصنوعی",
        "content": (
            "این دوره به کاربر کمک می کند هدف یادگیری خود را مشخص کند، عادت مطالعه روزانه بسازد، "
            "از ابزارهای هوش مصنوعی برای برنامه ریزی و بازبینی استفاده کند و خروجی ها را با تفکر انتقادی بررسی کند."
        ),
        "tags": "phase2,personal-development,ai,learning",
    },
    {
        "title": "قواعد مسیر یادگیری مرحله ای",
        "content": (
            "مسیر یادگیری زیتو باید مرحله ای، کوتاه، قابل تمرین و قابل سنجش باشد. هر مرحله یک خروجی مشخص دارد "
            "و آواتار مربی فقط بر اساس محتوای تاییدشده دوره و دانش پایه همان دوره کاربر را راهنمایی می کند."
        ),
        "tags": "phase2,learning-path,rag,stage",
    },
    {
        "title": "نقش آواتار مربی در Zito",
        "content": (
            "آواتار مربی وظیفه دارد مسیر کاربر را حفظ کند، سوال های او را با RAG پاسخ دهد، تمرین ها را توضیح دهد "
            "و در پایان با ارزیابی ساختاریافته برای آزمون و صدور مدرک آماده اش کند."
        ),
        "tags": "phase2,avatar,tutor,controller",
    },
]


def seed_admin(db: Session) -> None:
    existing_admin = db.scalars(select(Admin).limit(1)).first()
    if existing_admin:
        return
    settings = get_settings()
    if settings.is_production and not settings.has_safe_admin_seed_password:
        raise RuntimeError("Cannot seed the first production admin with an unsafe ADMIN_PASSWORD.")
    db.add(Admin(username=settings.admin_username, password_hash=hash_password(settings.admin_password)))
    db.commit()


def _sample_stage_content(stage: dict) -> dict:
    title = stage["title"]
    return {
        "summary": f"محتوای نمونه برای مرحله «{title}» در دوره توسعه فردی با هوش مصنوعی.",
        "learning_objective": "کاربر یک خروجی کوچک، قابل اجرا و قابل ارزیابی از این مرحله می سازد.",
        "avatar_instruction": (
            "زیتو باید با لحن مربی همراه، کوتاه و کاربردی توضیح بدهد و فقط بر اساس KB همین دوره راهنمایی کند."
        ),
        "items": [
            f"مفهوم اصلی مرحله {stage['number']} را با یک مثال ساده توضیح بده.",
            "یک تمرین کوتاه برای تبدیل مفهوم به اقدام روزانه ارائه کن.",
            "در پایان از کاربر یک پاسخ کوتاه و قابل سنجش بگیر.",
        ],
        "exercise": {
            "prompt": f"برداشت خودت از «{title}» را در دو جمله بنویس و یک اقدام عملی برای امروز مشخص کن.",
            "expected_signal": "پاسخ باید به مفهوم مرحله و یک اقدام قابل انجام اشاره کند.",
        },
        "ui_hint": {
            "template": stage["type"],
            "avatar_visible": True,
            "primary_action": "ادامه مسیر",
        },
    }


def seed_phase2_fake_course(db: Session) -> None:
    course = db.scalars(
        select(Course).where(Course.slug == PHASE2_SAMPLE_COURSE["slug"])
    ).first()
    if course:
        course.title = PHASE2_SAMPLE_COURSE["title"]
        course.domain = PHASE2_SAMPLE_COURSE["domain"]
        course.status = "published"
    else:
        course = Course(**PHASE2_SAMPLE_COURSE, status="published")
        db.add(course)
        db.flush()

    version = db.scalars(
        select(CourseVersion).where(
            CourseVersion.course_id == course.id,
            CourseVersion.version_number == 1,
        )
    ).first()
    now = datetime.now(timezone.utc)
    if version:
        version.status = "published"
        version.source = "seed"
        version.published_at = version.published_at or now
    else:
        version = CourseVersion(
            course_id=course.id,
            version_number=1,
            status="published",
            source="seed",
            published_at=now,
        )
        db.add(version)
        db.flush()

    existing_stages = {
        item.stage_number: item
        for item in db.scalars(
            select(CourseStageContent).where(CourseStageContent.course_version_id == version.id)
        ).all()
    }
    for stage in PHASE2_STAGE_TYPES:
        current = existing_stages.get(stage["number"])
        payload = _sample_stage_content(stage)
        if current:
            current.stage_type = stage["type"]
            current.title = stage["title"]
            current.content_json = payload
            current.status = "approved"
            current.ai_generation_status = "seeded"
            current.review_status = "approved"
            current.reviewed_by = "seed"
            current.generated_at = current.generated_at or now
            current.reviewed_at = current.reviewed_at or now
            current.content_version = 1
        else:
            db.add(
                CourseStageContent(
                    course_version_id=version.id,
                    stage_number=stage["number"],
                    stage_type=stage["type"],
                    title=stage["title"],
                    content_json=payload,
                    status="approved",
                    ai_generation_status="seeded",
                    review_status="approved",
                    reviewed_by="seed",
                    generated_at=now,
                    reviewed_at=now,
                    content_version=1,
                )
            )

    existing_kb = {
        item.title: item
        for item in db.scalars(select(CourseKbDocument).where(CourseKbDocument.course_id == course.id)).all()
    }
    for item in PHASE2_SAMPLE_KB:
        current = existing_kb.get(item["title"])
        if current:
            current.content = item["content"]
            current.tags = item["tags"]
            current.source_type = "seed"
        else:
            db.add(CourseKbDocument(course_id=course.id, source_type="seed", **item))

    exam = db.scalars(select(Exam).where(Exam.course_version_id == version.id)).first()
    questions_json = [
        {
            "type": "open",
            "question": "سه کاربرد عملی هوش مصنوعی در برنامه رشد شخصی خودت را توضیح بده.",
            "rubric": "پاسخ باید کاربردها را مشخص، قابل اجرا و مرتبط با هدف کاربر بیان کند.",
        },
        {
            "type": "scenario",
            "question": "اگر یک هفته از برنامه عقب افتادی، زیتو چطور باید مسیرت را اصلاح کند؟",
            "rubric": "پاسخ باید به بازبینی، کاهش فشار، اولویت بندی و ادامه مسیر اشاره کند.",
        },
    ]
    if exam:
        exam.title = "آزمون نهایی توسعه فردی با هوش مصنوعی"
        exam.questions_json = questions_json
        exam.passing_score = 70
        exam.status = "published"
    else:
        db.add(
            Exam(
                course_version_id=version.id,
                title="آزمون نهایی توسعه فردی با هوش مصنوعی",
                questions_json=questions_json,
                passing_score=70,
                status="published",
            )
        )

    db.commit()


def seed_defaults(db: Session) -> None:
    seed_admin(db)
    seed_phase2_fake_course(db)
