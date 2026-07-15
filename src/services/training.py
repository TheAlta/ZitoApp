import json
import re

from sqlalchemy.orm import Session

from src.lib.arvan_client import ask_ai
from src.models import User
from src.prompts import load_prompt
from src.services.json_utils import parse_json_object
from src.services.rag import build_user_context, retrieve_context


FALLBACK_LESSONS = {
    "accounting": [
        {
            "title": "هوش مصنوعی در تحلیل اولیه حسابداری",
            "lesson": "در این مرحله یاد می گیری از هوش مصنوعی برای دسته بندی اولیه تراکنش ها، پیدا کردن خطاهای احتمالی و آماده کردن یک چک لیست بررسی استفاده کنی. خروجی AI تصمیم نهایی نیست و باید با سند مالی، قوانین داخلی و کنترل انسانی بررسی شود.",
            "key_points": [
                "AI دستیار تحلیل است، نه جایگزین حسابدار.",
                "هر خروجی باید با سند و عدد واقعی کنترل شود.",
                "اطلاعات محرمانه مالی را بدون مجوز وارد ابزار عمومی نکن.",
            ],
            "exercise": "در دو جمله توضیح بده چرا خروجی هوش مصنوعی در حسابداری باید با سند مالی بررسی شود.",
        },
        {
            "title": "ساخت چک لیست کنترل مالی با AI",
            "lesson": "AI می تواند برای ساخت چک لیست کنترل فاکتورها، مغایرت بانکی و دسته بندی هزینه ها کمک کند. بهترین استفاده زمانی است که سوال دقیق بدهی و از مدل بخواهی موارد قابل بررسی را فهرست کند.",
            "key_points": [
                "درخواست را دقیق و محدود بنویس.",
                "از AI خروجی مرحله ای و قابل کنترل بگیر.",
                "نتیجه را با استاندارد و تجربه حسابدار تطبیق بده.",
            ],
            "exercise": "یک مثال کوتاه بزن که AI چطور می تواند در کنترل یک فاکتور به حسابدار کمک کند.",
        },
    ],
    "psychology": [
        {
            "title": "هوش مصنوعی به عنوان دستیار یادگیری روانشناسی",
            "lesson": "در این مرحله یاد می گیری از AI برای ساخت سوال های باز، خلاصه سازی متن های آموزشی و تمرین پاسخ همدلانه استفاده کنی. AI نباید تشخیص قطعی بدهد و جای درمانگر یا متخصص را نمی گیرد.",
            "key_points": [
                "AI برای آموزش و تمرین خوب است، نه تشخیص قطعی.",
                "پاسخ ها باید همدلانه، غیرقضاوتی و امن باشند.",
                "در موضوعات حساس باید ارجاع به متخصص انسانی وجود داشته باشد.",
            ],
            "exercise": "در دو جمله توضیح بده چرا AI نباید تشخیص روانشناختی قطعی بدهد.",
        },
        {
            "title": "طراحی سوال باز با AI",
            "lesson": "AI می تواند به تو کمک کند برای مصاحبه، مطالعه موردی یا تمرین کلاسی سوال های باز طراحی کنی. سوال خوب باید طرف مقابل را به توضیح بیشتر دعوت کند و جهت دهنده یا قضاوتی نباشد.",
            "key_points": [
                "سوال باز با چرا و چگونه و چه احساسی شروع می شود.",
                "از برچسب زدن و تشخیص دادن دوری کن.",
                "پاسخ AI را از نظر لحن و امنیت بررسی کن.",
            ],
            "exercise": "یک نمونه سوال باز بنویس که برای گفت وگوی آموزشی روانشناسی مناسب باشد.",
        },
    ],
    "law": [
        {
            "title": "هوش مصنوعی در بررسی اولیه متن حقوقی",
            "lesson": "در این مرحله یاد می گیری از AI برای خلاصه کردن قرارداد، پیدا کردن بندهای مبهم و ساخت چک لیست ریسک استفاده کنی. خروجی AI مشاوره حقوقی قطعی نیست و باید توسط متخصص بررسی شود.",
            "key_points": [
                "AI می تواند ابهام ها را برجسته کند، اما حکم نهایی نمی دهد.",
                "متن قرارداد و قانون مرتبط باید توسط انسان بررسی شود.",
                "اطلاعات محرمانه موکل یا شرکت را بدون مجوز وارد ابزار عمومی نکن.",
            ],
            "exercise": "در دو جمله توضیح بده چرا خروجی AI در بررسی قرارداد باید توسط متخصص حقوقی بررسی شود.",
        },
        {
            "title": "ساخت چک لیست ریسک قرارداد",
            "lesson": "AI می تواند کمک کند بندهای مربوط به تعهدات، زمان بندی، جریمه، فسخ و محرمانگی را فهرست کنی. این فهرست شروع بررسی است و جای تحلیل حقوقی دقیق را نمی گیرد.",
            "key_points": [
                "از AI بخواه بندهای پرریسک را دسته بندی کند.",
                "نتیجه را با متن کامل قرارداد تطبیق بده.",
                "برای تصمیم نهایی نظر متخصص لازم است.",
            ],
            "exercise": "یک مثال کوتاه بزن که AI چطور می تواند در پیدا کردن ریسک یک قرارداد کمک کند.",
        },
    ],
}


def _track_key(user: User) -> str:
    profile = f"{user.profession or ''} " + " ".join(answer.answer_text for answer in user.answers)
    normalized = profile.lower().replace("\u200c", " ")
    if "روان" in normalized or "psych" in normalized:
        return "psychology"
    if "حقوق" in normalized or "law" in normalized:
        return "law"
    return "accounting"


def fallback_lesson(user: User) -> dict:
    track = _track_key(user)
    lessons = FALLBACK_LESSONS[track]
    step = user.progress.current_step if user.progress else 1
    lesson = dict(lessons[(max(step, 1) - 1) % len(lessons)])
    lesson["check_question"] = lesson["exercise"]
    return lesson


def fallback_training_answer(user: User, question: str) -> str:
    track = _track_key(user)
    if track == "psychology":
        domain = "روانشناسی"
        example = "مثلا می توانی از AI بخواهی چند سوال باز و غیرقضاوتی برای تمرین یک گفت وگوی آموزشی بسازد."
    elif track == "law":
        domain = "حقوق"
        example = "مثلا می توانی از AI بخواهی بندهای مبهم یک قرارداد را فهرست کند، اما تصمیم نهایی باید با متخصص باشد."
    else:
        domain = "حسابداری"
        example = "مثلا می توانی از AI بخواهی تراکنش ها را اولیه دسته بندی کند، اما نتیجه باید با سند مالی کنترل شود."

    return (
        f"فعلا پاسخ را بر اساس مسیر {domain} و بدون Knowledge Base کامل می دهم: "
        "هوش مصنوعی در این مسیر نقش دستیار آموزشی و تحلیلی دارد، نه مرجع نهایی. "
        f"{example} "
        "اگر آماده ای، جواب تمرین همین مرحله را بنویس تا برویم مرحله بعد."
    )


def looks_like_question(message: str) -> bool:
    normalized = message.strip().lower()
    if "?" in normalized or "؟" in normalized:
        return True
    return bool(
        re.search(
            r"(^|\s)(چرا|چطور|چگونه|چیست|چی|چه\s|کدام|آیا|ایا|میشه|می\s*شود|why|how|what|which)(\s|$)",
            normalized,
        )
    )


async def generate_lesson(db: Session, user: User) -> dict:
    prompt = load_prompt("training_lesson_generation.md")
    user_context = build_user_context(user)
    rag_context = retrieve_context(db, f"{user.profession or ''} هوش مصنوعی AI {user_context}")
    user_message = json.dumps(
        {
            "user_context": user_context,
            "rag_context": rag_context,
            "current_progress": {
                "step": user.progress.current_step if user.progress else 1,
                "percentage": user.progress.percentage if user.progress else 0,
            },
            "allowed_tracks": ["حسابداری و هوش مصنوعی", "روانشناسی و هوش مصنوعی", "حقوق و هوش مصنوعی"],
        },
        ensure_ascii=False,
    )
    try:
        raw = await ask_ai(prompt, user_message, temperature=0.3, response_format={"type": "json_object"})
        lesson = parse_json_object(raw)
    except Exception:
        return fallback_lesson(user)

    required_fields = ("title", "lesson", "exercise", "check_question")
    if not all(str(lesson.get(field) or "").strip() for field in required_fields):
        return fallback_lesson(user)
    if not isinstance(lesson.get("key_points"), list) or not lesson["key_points"]:
        lesson["key_points"] = fallback_lesson(user)["key_points"]
    return lesson


async def answer_training_question(db: Session, user: User, question: str) -> str:
    user_context = build_user_context(user)
    rag_context = retrieve_context(db, f"{user.profession or ''} هوش مصنوعی AI {question}")
    system_prompt = (
        "تو مربی آموزشی زیتو هستی. فقط در سه مسیر حسابداری، روانشناسی و حقوق با محور هوش مصنوعی آموزش می دهی. "
        "با تکیه بر context بازیابی شده و پروفایل کاربر پاسخ بده. "
        "اگر سوال خارج از این سه حوزه بود، محترمانه کاربر را به انتخاب یکی از همین سه مسیر برگردان. "
        "پاسخ باید کوتاه، کاربردی، فارسی و آموزشی باشد."
    )
    user_message = json.dumps(
        {"user_context": user_context, "rag_context": rag_context, "question": question},
        ensure_ascii=False,
    )
    try:
        return await ask_ai(system_prompt, user_message, temperature=0.2)
    except Exception:
        return fallback_training_answer(user, question)
