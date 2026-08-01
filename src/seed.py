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

PHASE2_STAGE_CONTENT = {
    1: {
        "intro": "در این مرحله تصویر فشرده‌ای از هدف‌گذاری، عادت‌سازی و استفاده مسئولانه از هوش مصنوعی می‌سازی.",
        "blocks": [
            {"kind": "highlight", "title": "ایده اصلی", "body": "هوش مصنوعی جای تصمیم تو را نمی‌گیرد؛ سرعت فکرکردن، برنامه‌ریزی و بازبینی را بیشتر می‌کند."},
            {"kind": "bullets", "title": "سه پایه مسیر", "items": ["هدف روشن و قابل اندازه‌گیری", "اقدام کوچک و تکرارشونده", "بازبینی انسانی خروجی AI"]},
        ],
        "activity": {"kind": "reflection", "title": "خروجی مرحله", "prompt": "یک هدف یادگیری و کوچک‌ترین اقدام امروزت را در ذهن مشخص کن."},
    },
    2: {
        "intro": "مفاهیم پایه را با کارت‌های کوتاه مرور کن.",
        "blocks": [
            {"kind": "cards", "title": "فلش‌کارت‌ها", "items": [
                {"title": "هدف هوشمند", "body": "مشخص، قابل سنجش، دست‌یافتنی، مرتبط و زمان‌دار."},
                {"title": "عادت کوچک", "body": "کاری که شروعش کمتر از پنج دقیقه زمان می‌برد."},
                {"title": "بازبینی", "body": "مقایسه خروجی با هدف و اصلاح قدم بعدی."},
            ]},
        ],
        "activity": {"kind": "recall", "title": "مرور فعال", "prompt": "بدون نگاه‌کردن، سه مفهوم کارت‌ها را برای خودت تکرار کن."},
    },
    3: {
        "intro": "چند پرسش پرتکرار درباره نقش AI در رشد فردی را مرور کن.",
        "blocks": [
            {"kind": "qa", "title": "پرسش و پاسخ", "items": [
                {"question": "آیا AI می‌تواند هدف را به جای من انتخاب کند؟", "answer": "نه؛ AI گزینه می‌سازد، اما ارزش‌ها و انتخاب نهایی متعلق به توست."},
                {"question": "اگر برنامه عقب افتاد چه کنم؟", "answer": "حجم قدم بعدی را کم کن و برنامه را بر اساس واقعیت امروز بازنویسی کن."},
                {"question": "چطور پاسخ اشتباه AI را تشخیص بدهم؟", "answer": "ادعاهای مهم را با منبع معتبر و قضاوت انسانی بررسی کن."},
            ]},
        ],
        "activity": {"kind": "question", "title": "مکث یادگیری", "prompt": "مهم‌ترین ابهامت درباره استفاده روزانه از AI چیست؟"},
    },
    4: {
        "intro": "این نقشه ترتیب حرکت از هدف تا بازبینی را نشان می‌دهد.",
        "blocks": [
            {"kind": "timeline", "title": "مسیر یادگیری", "items": ["تعریف هدف", "تقسیم به قدم‌های کوچک", "تمرین روزانه", "دریافت بازخورد", "بازبینی و اصلاح"]},
        ],
        "activity": {"kind": "planning", "title": "جایگاه فعلی", "prompt": "مشخص کن اکنون در کدام بخش این مسیر قرار داری."},
    },
    5: {
        "intro": "با یک آزمون کوتاه، برداشت اولیه‌ات را محک بزن. نمره‌دهی هوشمند در اسپرینت بعدی فعال می‌شود.",
        "blocks": [
            {"kind": "quiz", "title": "آزمون کوچک", "items": [
                {"question": "بهترین شروع برای یک عادت تازه چیست؟", "options": ["یک برنامه سنگین", "یک اقدام بسیار کوچک", "خرید ابزار بیشتر"]},
                {"question": "خروجی مهم AI را چگونه استفاده می‌کنیم؟", "options": ["بدون بررسی", "با بررسی و منبع", "فقط بر اساس طول پاسخ"]},
            ]},
        ],
        "activity": {"kind": "self_check", "title": "خودسنجی", "prompt": "گزینه‌ها را انتخاب کن و دلیل انتخابت را برای خودت توضیح بده."},
    },
    6: {
        "intro": "در این قالب، انتخاب بین چند گزینه به تثبیت تفاوت مفاهیم کمک می‌کند.",
        "blocks": [
            {"kind": "quiz", "title": "چهارگزینه‌ای", "items": [
                {"question": "کدام هدف قابل سنجش‌تر است؟", "options": ["بهتر شوم", "هر روز ۲۰ دقیقه مطالعه کنم", "خیلی تلاش کنم", "همه‌چیز را یاد بگیرم"]},
                {"question": "اولین واکنش به عقب‌افتادن چیست؟", "options": ["رهاکردن مسیر", "پنهان‌کردن نتیجه", "بازتنظیم قدم بعدی", "دو برابر کردن فشار"]},
            ]},
        ],
        "activity": {"kind": "choice", "title": "انتخاب آگاهانه", "prompt": "برای هر سؤال یک گزینه انتخاب کن."},
    },
    7: {
        "intro": "دو نمونه واقعی نشان می‌دهند چطور یک درخواست مبهم به اقدام قابل اجرا تبدیل می‌شود.",
        "blocks": [
            {"kind": "cards", "title": "مثال‌های واقعی", "items": [
                {"title": "مطالعه زبان", "body": "به جای «برنامه بده»، زمان آزاد و سطح فعلی مشخص می‌شود و برنامه هفتگی کوتاه ساخته می‌شود."},
                {"title": "آمادگی شغلی", "body": "شرح شغل به مهارت‌های کوچک تقسیم و برای هر مهارت یک تمرین قابل سنجش تعیین می‌شود."},
            ]},
        ],
        "activity": {"kind": "example", "title": "مثال خودت", "prompt": "یکی از هدف‌هایت را به ورودی مشخص برای AI تبدیل کن."},
    },
    8: {
        "intro": "در یک موقعیت تعاملی، قدم بعدی را انتخاب می‌کنی.",
        "blocks": [
            {"kind": "scenario", "title": "سناریو", "body": "سه روز از برنامه عقب افتاده‌ای و فقط ۱۵ دقیقه زمان داری.", "options": ["کل برنامه را کنار بگذارم", "یک تمرین ۱۰ دقیقه‌ای انتخاب کنم", "همه کارها را امشب انجام بدهم"]},
        ],
        "activity": {"kind": "scenario_choice", "title": "تصمیم", "prompt": "واقع‌بینانه‌ترین انتخاب را مشخص کن."},
    },
    9: {
        "intro": "این چک‌لیست، اجرای مسئولانه یک جلسه یادگیری با AI را ساده می‌کند.",
        "blocks": [
            {"kind": "checklist", "title": "چک‌لیست اجرایی", "items": ["هدف جلسه را نوشته‌ام", "محدودیت زمان را گفته‌ام", "خروجی را با نیازم مقایسه کرده‌ام", "ادعاهای مهم را بررسی کرده‌ام", "قدم بعدی را ثبت کرده‌ام"]},
        ],
        "activity": {"kind": "checklist", "title": "آماده اجرا", "prompt": "مواردی را که همین امروز انجام می‌دهی علامت بزن."},
    },
    10: {
        "intro": "وقت تبدیل دانسته‌ها به یک خروجی واقعی است.",
        "blocks": [
            {"kind": "steps", "title": "تمرین عملی", "items": ["یک هدف هفتگی انتخاب کن", "آن را به سه قدم کوچک تقسیم کن", "از AI برای نقد برنامه کمک بگیر", "نسخه نهایی را خودت اصلاح کن"]},
        ],
        "activity": {"kind": "deliverable", "title": "تحویل تمرین", "prompt": "یک برنامه سه‌مرحله‌ای برای هدف این هفته آماده کن."},
    },
    11: {
        "intro": "ماموریت امروز باید کوچک، روشن و قابل پایان باشد.",
        "blocks": [
            {"kind": "highlight", "title": "ماموریت روزانه", "body": "۱۵ دقیقه روی مهم‌ترین مهارتت کار کن و در پایان فقط یک جمله درباره نتیجه بنویس."},
            {"kind": "bullets", "title": "قانون چالش", "items": ["شروع کمتر از دو دقیقه", "بدون نیاز به ابزار تازه", "یک خروجی قابل مشاهده"]},
        ],
        "activity": {"kind": "mission", "title": "شروع ماموریت", "prompt": "زمان انجام ماموریت امروز را مشخص کن."},
    },
    12: {
        "intro": "این قالب جای گفت‌وگوی زنده با آواتار است. در این اسپرینت فقط نمای آن آماده شده است.",
        "blocks": [
            {"kind": "dialog", "title": "گفت‌وگوی نمونه", "items": [
                {"speaker": "زیتو", "body": "این هفته مهم‌ترین مانعت چه بود؟"},
                {"speaker": "تو", "body": "یک پاسخ کوتاه و واقعی آماده کن."},
                {"speaker": "زیتو", "body": "قدم بعدی را کوچک‌تر و قابل اجرا می‌کنیم."},
            ]},
        ],
        "activity": {"kind": "coach_preview", "title": "پیش‌نمایش کوچینگ", "prompt": "گفت‌وگوی واقعی آواتار در اسپرینت ۳ به RAG دوره متصل می‌شود."},
    },
    13: {
        "intro": "مرور هوشمند روی بخش‌هایی تمرکز می‌کند که احتمال فراموشی یا ابهام در آن‌ها بیشتر است.",
        "blocks": [
            {"kind": "cards", "title": "مرور هدفمند", "items": [
                {"title": "به‌یادآوری", "body": "سه مفهوم را بدون نگاه‌کردن نام ببر."},
                {"title": "کاربرد", "body": "برای یکی از مفاهیم مثال شخصی بساز."},
                {"title": "اصلاح", "body": "یک برداشت اشتباه احتمالی را پیدا کن."},
            ]},
        ],
        "activity": {"kind": "review", "title": "مرور امروز", "prompt": "سخت‌ترین مفهوم مسیر تا اینجا را مشخص کن."},
    },
    14: {
        "intro": "جایگاه فایل صوتی ساخته شده و بعداً فایل تأییدشده CMS در آن قرار می‌گیرد.",
        "blocks": [
            {"kind": "bullets", "title": "متن همراه صوت", "items": ["هدف روشن", "قدم کوچک", "بازخورد سریع", "اصلاح مستمر"]},
        ],
        "activity": {"kind": "listen", "title": "خلاصه صوتی", "prompt": "پس از اضافه‌شدن فایل، کاربر می‌تواند همین‌جا آن را گوش کند."},
    },
    15: {
        "intro": "قاب اینفوگرافیک آماده است و تصویر نهایی بعداً از CMS منتشر می‌شود.",
        "blocks": [
            {"kind": "cards", "title": "داده‌های اینفوگرافیک", "items": [
                {"title": "۱", "body": "هدف را مشخص کن"},
                {"title": "۲", "body": "تمرین را کوچک کن"},
                {"title": "۳", "body": "نتیجه را بازبینی کن"},
            ]},
        ],
        "activity": {"kind": "visual_review", "title": "مرور تصویری", "prompt": "رابطه سه گام را برای خودت توضیح بده."},
    },
    16: {
        "intro": "نقشه ذهنی، ارتباط هدف، عادت، ابزار و بازخورد را یکجا نشان می‌دهد.",
        "blocks": [
            {"kind": "mind_map", "title": "گره‌های نقشه", "center": "رشد فردی با AI", "items": ["هدف", "عادت روزانه", "تمرین", "بازخورد", "تفکر انتقادی"]},
        ],
        "activity": {"kind": "mapping", "title": "نقشه شخصی", "prompt": "یک گره مرتبط با شرایط خودت به نقشه اضافه کن."},
    },
    17: {
        "intro": "نکات طلایی، قواعدی هستند که در تمام مسیر قابل استفاده‌اند.",
        "blocks": [
            {"kind": "tips", "title": "کارت‌های طلایی", "items": ["درخواست دقیق، پاسخ مفیدتر می‌سازد.", "برنامه خوب باید با زمان واقعی تو سازگار باشد.", "خروجی AI پیش‌نویس است، نه حقیقت نهایی.", "تداوم کوچک از شروع سنگین ارزشمندتر است."]},
        ],
        "activity": {"kind": "favorite", "title": "نکته منتخب", "prompt": "یک نکته را برای استفاده روزانه انتخاب کن."},
    },
    18: {
        "intro": "شناخت خطاهای رایج کمک می‌کند سریع‌تر مسیر را اصلاح کنی.",
        "blocks": [
            {"kind": "mistakes", "title": "اشتباه و اصلاح", "items": [
                {"mistake": "هدف خیلی کلی", "correction": "خروجی و زمان را مشخص کن."},
                {"mistake": "اعتماد کامل به پاسخ AI", "correction": "منبع و منطق پاسخ را بررسی کن."},
                {"mistake": "برنامه فشرده", "correction": "حداقل اقدام پایدار را انتخاب کن."},
            ]},
        ],
        "activity": {"kind": "correction", "title": "اصلاح مسیر", "prompt": "رایج‌ترین اشتباه خودت را انتخاب و اصلاحش را مشخص کن."},
    },
    19: {
        "intro": "این نسخه نمونه، اجزای یک مسیر شخصی را با توجه به زمان و هدف کاربر نمایش می‌دهد.",
        "blocks": [
            {"kind": "timeline", "title": "برنامه پیشنهادی", "items": ["روز ۱: تعیین هدف", "روز ۲: تمرین کوچک", "روز ۳: بازخورد از AI", "روز ۴: اصلاح خروجی", "روز ۵: مرور و ثبت نتیجه"]},
            {"kind": "highlight", "title": "اصل شخصی‌سازی", "body": "شدت برنامه باید با زمان آزاد و سطح فعلی کاربر هماهنگ شود."},
        ],
        "activity": {"kind": "personal_plan", "title": "تنظیم مسیر", "prompt": "یک بخش برنامه را متناسب با شرایط خودت تغییر بده."},
    },
    20: {
        "intro": "در پروژه نهایی، آموخته‌ها را به یک برنامه کوتاه و قابل اجرا تبدیل می‌کنی.",
        "blocks": [
            {"kind": "steps", "title": "پروژه نهایی", "items": ["یک هدف واقعی انتخاب کن", "معیار موفقیت تعریف کن", "برنامه پنج‌روزه بساز", "نقش AI و نقاط بررسی انسانی را مشخص کن", "نتیجه مورد انتظار را بنویس"]},
            {"kind": "checklist", "title": "معیار تکمیل", "items": ["هدف روشن است", "قدم‌ها قابل اجرا هستند", "زمان‌بندی واقعی است", "بررسی انسانی تعریف شده است"]},
        ],
        "activity": {"kind": "final_project", "title": "جمع‌بندی مسیر", "prompt": "طرح نهایی را آماده کن. آزمون نهایی و مدرک در اسپرینت ۴ فعال می‌شود."},
    },
}

PHASE2_MEDIA_SLOTS = {
    1: [{"kind": "video", "label": "ویدیوی معرفی درس"}],
    7: [
        {"kind": "image", "label": "تصویر مثال واقعی"},
        {"kind": "video", "label": "ویدیوی تحلیل مثال"},
    ],
    14: [{"kind": "audio", "label": "خلاصه صوتی درس"}],
    15: [{"kind": "image", "label": "اینفوگرافیک مرحله"}],
    16: [{"kind": "image", "label": "تصویر نقشه ذهنی"}],
}

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
    content = PHASE2_STAGE_CONTENT[stage["number"]]
    media_slots = [
        {**slot, "status": "empty", "url": None}
        for slot in PHASE2_MEDIA_SLOTS.get(stage["number"], [])
    ]
    return {
        "contract_version": 1,
        **content,
        "media_slots": media_slots,
        "coaching_checkpoint": {
            "prompt": "درباره این مرحله سوالی داری؟",
            "mode": "preview",
            "enabled": False,
        },
        "ui_hint": {
            "template": stage["type"],
            "avatar_visible": True,
            "primary_action": "تکمیل مرحله و ادامه",
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
