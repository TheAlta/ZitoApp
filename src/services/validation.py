import json

from src.lib.arvan_client import ask_ai
from src.prompts import load_prompt
from src.services.json_utils import parse_json_object


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
    raw = await ask_ai(prompt, user_message, temperature=0, response_format={"type": "json_object"})
    parsed = parse_json_object(raw)
    return {"valid": bool(parsed.get("valid")), "reason": str(parsed.get("reason") or "")}


async def evaluate_training_answer(lesson: str, check_question: str, answer_text: str) -> dict:
    prompt = load_prompt("training_answer_evaluation.md")
    user_message = json.dumps(
        {"lesson": lesson, "check_question": check_question, "answer": answer_text},
        ensure_ascii=False,
    )
    raw = await ask_ai(prompt, user_message, temperature=0, response_format={"type": "json_object"})
    parsed = parse_json_object(raw)
    return {
        "passed": bool(parsed.get("passed")),
        "feedback": str(parsed.get("feedback") or ""),
        "score": int(parsed.get("score") or 0),
    }
