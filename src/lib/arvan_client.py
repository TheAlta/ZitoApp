import json
import re
from typing import Any

import httpx

from src.config import get_settings


class ArvanAIError(RuntimeError):
    pass


def _source_sentences(retrieved_sources: Any) -> list[str]:
    """Extract readable source sentences from the coach's numbered RAG context."""
    if not isinstance(retrieved_sources, str):
        return []
    without_headers = re.sub(r"\[SOURCE \d+:[^\]]+\]\s*", "", retrieved_sources)
    return [
        sentence.strip(" -•\t")
        for sentence in re.split(r"[\n.!؟]+", without_headers)
        if len(sentence.strip()) >= 24
    ]


def _most_relevant_source_sentence(question: str, sentences: list[str]) -> str:
    ignored_words = {
        "از", "به", "در", "با", "برای", "را", "که", "این", "آن", "و", "یا", "یک", "چه",
        "چیه", "چیست", "شروع", "کنم", "شود", "است", "هست", "هم", "تا", "رو", "من",
    }
    terms = {
        item for item in re.findall(r"[\u0600-\u06ffa-zA-Z0-9]+", question.lower())
        if len(item) > 1 and item not in ignored_words
    }
    if not sentences:
        return ""
    return max(
        sentences,
        key=lambda sentence: (
            sum(term in sentence.lower() for term in terms),
            -abs(len(sentence) - 170),
        ),
    )


def _learner_practice_context(message_data: dict[str, Any]) -> str:
    context = message_data.get("learner_context")
    learner = context.get("learner") if isinstance(context, dict) else {}
    learner = learner if isinstance(learner, dict) else {}
    field = str(learner.get("work_or_study_field") or learner.get("preferred_career_path") or "").strip()
    daily_time = str(learner.get("daily_learning_time") or "").strip()
    if field and daily_time:
        return f"نمونه‌ات را از فضای {field} انتخاب کن و آن را در همان زمان روزانهٔ {daily_time} انجام بده."
    if field:
        return f"نمونه‌ات را از یک موقعیت واقعی در فضای {field} انتخاب کن."
    if daily_time:
        return f"تمرین را طوری کوچک نگه دار که در زمان روزانهٔ {daily_time} تمام شود."
    return "تمرین را با یک موقعیت واقعی و کوچک از کار یا زندگی خودت انجام بده."


def _mock_course_coach_response(message_data: dict[str, Any], fallback_text: str) -> str:
    """Provide useful, source-bound coaching while local AI is deliberately mocked."""
    question = str(message_data.get("learner_question") or fallback_text).strip()
    sentences = _source_sentences(message_data.get("retrieved_sources"))
    source_text = " ".join(sentences)
    normalized_question = question.replace("ي", "ی").replace("ك", "ک").lower()
    relevant_sentence = _most_relevant_source_sentence(question, sentences)
    learner_context = _learner_practice_context(message_data)

    is_marketing = "بازاریابی" in source_text or "مشتری" in source_text
    asks_to_start = any(token in normalized_question for token in ("شروع", "از کجا", "چطور شروع"))

    if is_marketing and asks_to_start:
        answer = (
            "شروع بازاریابی از فهم مسئله مشتری است، نه تبلیغ یا فهرست‌کردن ویژگی‌های محصول. "
            "برای یک گروه مشخص، یک موقعیت استفاده را بنویس: مشتری می‌خواهد چه کاری انجام دهد، "
            "کجا گیر می‌کند و الان از چه راه‌حلی استفاده می‌کند. سپس با سه گفت‌وگوی کوتاه یا مشاهده رفتار، "
            f"دنبال شاهد همان مسئله باش؛ بعد از آن درباره پیام یا کانال تصمیم بگیر. {learner_context}"
        )
        action = "امروز یک گروه مشتری و یک موقعیت استفاده را در سه جمله ثبت کن."
    elif is_marketing and any(token in normalized_question for token in ("کانال", "تبلیغ", "پیام")):
        answer = (
            "در این سرفصل، کانال یا پیام را بعد از روشن‌شدن مسئله مشتری انتخاب می‌کنیم. "
            f"نکته مرتبط منبع این است: «{relevant_sentence or 'ابتدا موقعیت، مانع و راه‌حل فعلی مشتری را ثبت کن.'}» "
            f"یک فرض ساده بنویس: برای کدام گروه، با چه پیامی و در کدام کانال می‌خواهی چه رفتاری را بسنجی. {learner_context}"
        )
        action = "یک فرض یک‌خطی برای مخاطب، پیام و رفتار مطلوب بنویس."
    elif relevant_sentence:
        answer = (
            f"نکته اصلی این مرحله: {relevant_sentence} "
            f"برای تبدیل آن به یادگیری واقعی، یک اقدام کوچک و قابل مشاهده انتخاب کن و نتیجه‌اش را در مرحله بعد مرور کن. {learner_context}"
        )
        action = "یک اقدام کوچک مشخص کن و نتیجه‌اش را کوتاه یادداشت کن."
    else:
        answer = "منبع تاییدشده این مرحله برای پاسخ دقیق کافی نیست؛ پرسش را به مفهوم یا تمرین همین درس نزدیک‌تر کن."
        action = "یکی از نکته‌های همین درس را انتخاب کن و درباره کاربردش بپرس."

    return json.dumps(
        {
            "answer": answer,
            "grounded": bool(sentences),
            "source_numbers": [1] if sentences else [],
            "suggested_action": action,
        },
        ensure_ascii=False,
    )


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

    if "ZITO_FINAL_EXAM_GENERATION_V1" in system_prompt:
        return json.dumps(
            {
                "questions": [
                    {
                        "id": "final-q-1",
                        "type": "open",
                        "question": "توضیح بده چرا هوش مصنوعی در مسیر توسعه فردی باید دستیار تصمیم‌گیری باشد، نه جایگزین قضاوت انسانی.",
                        "rubric": "تفاوت کمک AI با تصمیم انسانی، بررسی نتیجه و مسئولیت‌پذیری را توضیح دهد.",
                        "max_score": 34,
                    },
                    {
                        "id": "final-q-2",
                        "type": "scenario",
                        "question": "فرض کن برای یک هدف یادگیری، AI چند پیشنهاد داده است. مسیر کوتاه و مسئولانه تو برای انتخاب و اجرای یک پیشنهاد چیست؟",
                        "rubric": "هدف روشن، بررسی پیشنهادها، اقدام کوچک و بازبینی نتیجه را پوشش دهد.",
                        "max_score": 33,
                    },
                    {
                        "id": "final-q-3",
                        "type": "open",
                        "question": "دو کاری را بنویس که برای حفظ حریم خصوصی و کیفیت خروجی AI در یک تمرین واقعی انجام می‌دهی.",
                        "rubric": "پرهیز از داده حساس و کنترل خروجی با منبع یا قضاوت انسانی را بیان کند.",
                        "max_score": 33,
                    },
                ]
            },
            ensure_ascii=False,
        )

    if "ZITO_FINAL_EXAM_GRADING_V1" in system_prompt:
        exam = message_data.get("exam") if isinstance(message_data, dict) else {}
        questions = exam.get("questions") if isinstance(exam, dict) else []
        answers = message_data.get("answers") if isinstance(message_data, dict) else {}
        answers = answers if isinstance(answers, dict) else {}
        meaningful = bool(questions) and all(
            len(str(answers.get(item.get("id"), "")).strip().split()) >= 4
            for item in questions
            if isinstance(item, dict)
        )
        score = 82 if meaningful else 45
        question_feedback = []
        for index, item in enumerate(questions if isinstance(questions, list) else []):
            if not isinstance(item, dict):
                continue
            max_score = int(item.get("max_score") or 0)
            earned = [28, 27, 27][index] if meaningful and index < 3 else min(max_score, 15)
            question_feedback.append(
                {
                    "question_id": str(item.get("id") or ""),
                    "score": earned,
                    "feedback": (
                        "پاسخ روشن است و مسیر عملی و مسئولانه‌ای را نشان می‌دهد."
                        if meaningful
                        else "پاسخ را با توضیح، مثال یا گام عملی دقیق‌تر کامل کن."
                    ),
                }
            )
        return json.dumps(
            {
                "score": score,
                "feedback": (
                    "آفرین، مفاهیم اصلی دوره را با نگاه عملی و مسئولانه جمع‌بندی کردی."
                    if meaningful
                    else "هنوز برای عبور از آزمون نیاز به پاسخ‌های کامل‌تر و کاربردی‌تر داری."
                ),
                "question_feedback": question_feedback,
            },
            ensure_ascii=False,
        )

    if "ZITO_PERSONALIZED_WORK_EXAMPLE_V1" in system_prompt:
        learner_context = message_data.get("learner_context") if isinstance(message_data, dict) else {}
        learner = learner_context.get("learner") if isinstance(learner_context, dict) else {}
        module = learner_context.get("module") if isinstance(learner_context, dict) else {}
        field = str(learner.get("work_or_study_field") or learner.get("preferred_career_path") or "مسیر حرفه‌ای تو")
        module_title = str(module.get("title") or "این سرفصل")
        return json.dumps(
            {
                "title": f"یک موقعیت کاربردی در {field}",
                "scenario": (
                    f"فرض کن در {field} می‌خواهی آموخته‌های «{module_title}» را به یک تصمیم روزانه تبدیل کنی. "
                    "ابتدا مسئله را کوتاه و بدون داده حساس تعریف می‌کنی، سپس از AI برای پیشنهاد اولیه کمک می‌گیری "
                    "و نتیجه را با شرایط واقعی و بررسی انسانی تطبیق می‌دهی."
                ),
                "application_steps": [
                    "یک مسئله کوچک و واقعی را مشخص کن.",
                    "از AI فقط برای تولید گزینه‌های اولیه کمک بگیر.",
                    "گزینه‌ها را با داده‌ها و مسئولیت حرفه‌ای خودت بررسی کن.",
                ],
                "reflection_question": "کدام بخش این مثال را می‌توانی همین هفته در مسیر خودت امتحان کنی؟",
                "source_numbers": [1],
            },
            ensure_ascii=False,
        )

    if "ZITO_COURSE_COACH_V" in system_prompt:
        return _mock_course_coach_response(message_data, answer_text)
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
        domain_context = user_context.lower()
        for line in user_context.splitlines():
            if line.lower().startswith("work or study field:"):
                domain_context = line.lower()
                break

        if "حقوق" in domain_context or "law" in domain_context:
            title = "هوش مصنوعی در بررسی اولیه قرارداد"
            lesson = "در این مرحله یاد می گیری از AI برای پیدا کردن ریسک های احتمالی یک بند قراردادی استفاده کنی، بدون اینکه خروجی را مشاوره حقوقی قطعی بدانی."
            exercise = "در دو جمله توضیح بده چرا خروجی AI در حقوق باید توسط متخصص انسانی بررسی شود."
        elif "روان" in domain_context or "psych" in domain_context:
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
    max_tokens: int | None = None,
    max_completion_tokens: int | None = None,
    reasoning_effort: str | None = None,
    model: str | None = None,
    api_base_url: str | None = None,
    api_key: str | None = None,
    timeout_seconds: int | None = None,
) -> str:
    settings = get_settings()

    if settings.arvan_mock_ai:
        return _mock_response(system_prompt, user_message)

    effective_base_url = api_base_url or settings.arvan_api_base_url
    effective_api_key = api_key or settings.arvan_api_key
    if not effective_base_url or not effective_api_key:
        raise ArvanAIError("AI gateway is not configured. Set its API base URL and key.")

    url = f"{effective_base_url.rstrip('/')}/chat/completions"
    payload: dict[str, Any] = {
        "model": model or settings.arvan_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
    }
    if response_format:
        payload["response_format"] = response_format
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if max_completion_tokens is not None:
        payload["max_completion_tokens"] = max_completion_tokens
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort

    headers = {
        "Authorization": f"Bearer {effective_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(
            timeout=timeout_seconds or settings.arvan_timeout_seconds,
            trust_env=False,
        ) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:500] if exc.response is not None else ""
        raise ArvanAIError(f"AI gateway returned HTTP {exc.response.status_code}: {body}") from exc
    except (httpx.RequestError, ValueError) as exc:
        raise ArvanAIError(f"Could not call AI gateway ({type(exc).__name__}): {exc}") from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ArvanAIError(f"Unexpected AI gateway response shape: {data}") from exc

    if not isinstance(content, str) or not content.strip():
        raise ArvanAIError("AI gateway returned an empty response.")
    return content.strip()

