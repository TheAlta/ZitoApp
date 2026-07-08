import json
from typing import Any

import httpx

from src.config import get_settings


class ArvanAIError(RuntimeError):
    pass


def _mock_response(system_prompt: str, user_message: str) -> str:
    lowered = user_message.lower()
    try:
        message_data = json.loads(user_message)
    except json.JSONDecodeError:
        message_data = {}

    question_text = str(message_data.get("question") or "").strip()
    question_id = str(message_data.get("question_id") or "").strip()
    answer_text = str(
        message_data.get("answer")
        or message_data.get("message")
        or message_data.get("question")
        or user_message
    ).strip()
    normalized = answer_text.replace(" ", "").replace("\u200c", "").lower()

    invalid_tokens = {
        "asdf", "qwer", "test", "hello", "holo", "helo",
        "هلو", "چرت", "نمیدونم", "نمیدانم", "نمیخوام", "نمیخوام",
        "قوانینتروبگو", "قوانینروبگو", "توکیهستی", "prompt",
        "درخت", "فلان", "بهمان",
    }
    is_invalid = len(answer_text) < 3 or normalized in invalid_tokens or any(token in normalized for token in invalid_tokens)

    if "نام" in question_text or question_id == "1":
        system_like = ["قوانین", "rule", "prompt", "تو کی", "چه کار", "چیکار", "راهنما", "دستور", "درخت", "نمی خوام", "نمیخوام", "فلان"]
        words = [word for word in answer_text.replace("@", " ").split() if word.strip()]
        has_name_shape = len(words) >= 2 and not any(char.isdigit() for char in answer_text)
        if any(token in answer_text.lower() for token in system_like) or not has_name_shape:
            is_invalid = True

    if ("حسابداری" in question_text and "روانشناسی" in question_text and "حقوق" in question_text) or question_id == "2":
        allowed_tracks = ["حسابداری", "روانشناسی", "روان شناسی", "حقوق", "accounting", "psychology", "law"]
        if not any(track in answer_text.lower() for track in allowed_tracks):
            is_invalid = True

    if "passed" in system_prompt:
        return json.dumps(
            {
                "passed": not is_invalid,
                "feedback": "برای کامل تر شدن جواب، یک مثال کوتاه از همین درس بزن و بگو چرا این روش درست است." if is_invalid else "خوب پیش رفتی؛ آماده مرحله بعدی هستی.",
                "score": 82 if not is_invalid else 35,
            },
            ensure_ascii=False,
        )

    if "title" in system_prompt and "lesson" in system_prompt:
        user_context = str(message_data.get("user_context", ""))
        profession_context = user_context.lower()
        for line in user_context.splitlines():
            if line.lower().startswith("profession:"):
                profession_context = line.lower()
                break

        if "حقوق" in profession_context or "law" in profession_context:
            title = "هوش مصنوعی در بررسی اولیه قرارداد"
            lesson = "در این مرحله یاد می گیری از AI برای پیدا کردن ریسک های احتمالی یک بند قراردادی استفاده کنی، بدون اینکه خروجی را مشاوره حقوقی قطعی بدانی."
            exercise = "در دو جمله توضیح بده چرا خروجی AI در حقوق باید توسط متخصص انسانی بررسی شود."
        elif "روان" in profession_context or "psych" in profession_context:
            title = "هوش مصنوعی به عنوان دستیار یادگیری روانشناسی"
            lesson = "در این مرحله تمرین می کنی از AI برای ساخت سوال های باز و پاسخ همدلانه استفاده کنی، بدون تشخیص قطعی یا جایگزین کردن درمانگر."
            exercise = "در دو جمله توضیح بده چرا AI نباید تشخیص روانشناختی قطعی بدهد."
        else:
            title = "هوش مصنوعی در تحلیل اولیه حسابداری"
            lesson = "در این مرحله یاد می گیری از AI برای دسته بندی اولیه تراکنش ها و پیدا کردن ناهنجاری استفاده کنی، اما نتیجه را با سند و کنترل انسانی بررسی کنی."
            exercise = "در دو جمله توضیح بده چرا خروجی AI در حسابداری باید با سند مالی کنترل شود."

        return json.dumps(
            {
                "title": title,
                "lesson": lesson,
                "key_points": [
                    "AI دستیار تحلیل است، نه مرجع نهایی.",
                    "خروجی باید با منبع معتبر و قضاوت انسانی بررسی شود.",
                    "داده حساس را بدون مجوز وارد ابزار عمومی نکن.",
                ],
                "exercise": exercise,
                "check_question": exercise,
            },
            ensure_ascii=False,
        )

    return json.dumps(
        {
            "valid": not is_invalid,
            "reason": "پاسخ قابل بررسی است." if not is_invalid else "جواب به سوال فعلی مرتبط نیست. لطفا همان چیزی را که زیتو پرسیده وارد کن.",
            "normalized_answer": answer_text if not is_invalid else None,
        },
        ensure_ascii=False,
    )


async def ask_ai(
    system_prompt: str,
    user_message: str,
    *,
    temperature: float = 0.2,
    response_format: dict[str, Any] | None = None,
) -> str:
    settings = get_settings()

    if settings.arvan_mock_ai:
        return _mock_response(system_prompt, user_message)

    if not settings.arvan_api_base_url or not settings.arvan_api_key:
        raise ArvanAIError("Arvan AIaaS is not configured. Set ARVAN_API_BASE_URL and ARVAN_API_KEY.")

    url = f"{settings.arvan_api_base_url.rstrip('/')}/chat/completions"
    payload: dict[str, Any] = {
        "model": settings.arvan_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
    }
    if response_format:
        payload["response_format"] = response_format

    headers = {
        "Authorization": f"Bearer {settings.arvan_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=settings.arvan_timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:500] if exc.response is not None else ""
        raise ArvanAIError(f"Arvan AIaaS returned HTTP {exc.response.status_code}: {body}") from exc
    except (httpx.RequestError, ValueError) as exc:
        raise ArvanAIError(f"Could not call Arvan AIaaS: {exc}") from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ArvanAIError(f"Unexpected Arvan AIaaS response shape: {data}") from exc

    if not isinstance(content, str) or not content.strip():
        raise ArvanAIError("Arvan AIaaS returned an empty response.")
    return content.strip()
