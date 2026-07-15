import json

from src.lib.arvan_client import ask_ai
from src.prompts import load_prompt
from src.services.json_utils import parse_json_object


INVALID_TRAINING_ANSWERS = {
    "نمیگم",
    "نمی گم",
    "نمیدونم",
    "نمی دونم",
    "نمیخوام",
    "نمی خوام",
    "asdf",
    "test",
    "hello",
    "هلو",
    "درخت",
    "فلان",
}


def _normalized_text(value: str) -> str:
    return value.strip().replace("\u200c", " ").lower()


def _is_meaningful_training_text(value: str) -> bool:
    normalized = _normalized_text(value)
    compact = normalized.replace(" ", "")
    if len(compact) < 12:
        return False
    if any(token.replace(" ", "") in compact for token in INVALID_TRAINING_ANSWERS):
        return False
    letters = [char for char in compact if char.isalpha()]
    return len(letters) >= 8


def fallback_training_evaluation(answer_text: str) -> dict:
    passed = _is_meaningful_training_text(answer_text)
    return {
        "passed": passed,
        "feedback": (
            "جوابت قابل قبول است؛ می رویم مرحله بعد."
            if passed
            else "جوابت هنوز برای رفتن به مرحله بعد کافی نیست. لطفا در یک یا دو جمله واضح توضیح بده و یک مثال کوتاه بزن."
        ),
        "score": 75 if passed else 35,
    }


async def validate_initial_answer(question_text: str, answer_text: str, question_id: int | None = None) -> dict:
    prompt = load_prompt("initial_answer_validation.md")
    user_message = json.dumps(
        {"question_id": question_id, "question": question_text, "answer": answer_text},
        ensure_ascii=False,
    )
    raw = await ask_ai(prompt, user_message, temperature=0, response_format={"type": "json_object"})
    parsed = parse_json_object(raw)
    return {
        "valid": bool(parsed.get("valid")),
        "reason": str(parsed.get("reason") or ""),
        "normalized_answer": parsed.get("normalized_answer"),
    }


async def validate_training_question(user_question: str, user_context: str) -> dict:
    prompt = load_prompt("training_question_validation.md")
    user_message = json.dumps(
        {"user_context": user_context, "question": user_question},
        ensure_ascii=False,
    )
    try:
        raw = await ask_ai(prompt, user_message, temperature=0, response_format={"type": "json_object"})
        parsed = parse_json_object(raw)
    except Exception:
        valid = _is_meaningful_training_text(user_question) or len(_normalized_text(user_question).replace(" ", "")) >= 6
        return {
            "valid": valid,
            "reason": "سوال قابل بررسی است." if valid else "سوال خیلی کوتاه یا نامفهوم است.",
        }
    return {"valid": bool(parsed.get("valid")), "reason": str(parsed.get("reason") or "")}


async def evaluate_training_answer(lesson: str, check_question: str, answer_text: str) -> dict:
    prompt = load_prompt("training_answer_evaluation.md")
    user_message = json.dumps(
        {"lesson": lesson, "check_question": check_question, "answer": answer_text},
        ensure_ascii=False,
    )
    try:
        raw = await ask_ai(prompt, user_message, temperature=0, response_format={"type": "json_object"})
        parsed = parse_json_object(raw)
    except Exception:
        return fallback_training_evaluation(answer_text)
    return {
        "passed": bool(parsed.get("passed")),
        "feedback": str(parsed.get("feedback") or ""),
        "score": int(parsed.get("score") or 0),
    }
