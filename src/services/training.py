import json
import re

from sqlalchemy.orm import Session

from src.lib.arvan_client import ask_ai
from src.models import User
from src.prompts import load_prompt
from src.services.json_utils import parse_json_object
from src.services.rag import build_user_context, retrieve_context


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
    raw = await ask_ai(prompt, user_message, temperature=0.3, response_format={"type": "json_object"})
    return parse_json_object(raw)


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
    return await ask_ai(system_prompt, user_message, temperature=0.2)
