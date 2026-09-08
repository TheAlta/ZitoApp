import json
import unittest

from tests._env import setup_test_environment

setup_test_environment()

from src.config import get_settings
from src.lib.arvan_client import ask_ai


class ArvanClientMockTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        get_settings.cache_clear()

    async def test_ask_ai_uses_mock_without_real_arvan_call(self) -> None:
        raw = await ask_ai(
            "تو ارزیاب هستی و فقط JSON برمی گردانی.",
            json.dumps(
                {
                    "question_id": 1,
                    "question": "نام و نام خانوادگی خود را بنویس.",
                    "answer": "علی رضایی",
                },
                ensure_ascii=False,
            ),
            temperature=0,
            response_format={"type": "json_object"},
        )

        data = json.loads(raw)

        self.assertTrue(data["valid"])
        self.assertEqual(data["normalized_answer"], "علی رضایی")

    async def test_course_coach_mock_uses_the_retrieved_marketing_source(self) -> None:
        raw = await ask_ai(
            "ZITO_COURSE_COACH_V2",
            json.dumps(
                {
                    "learner_question": "شروع بازاریابی چیه؟",
                    "learner_context": {
                        "learner": {
                            "work_or_study_field": "بازاریابی محصول",
                            "daily_learning_time": "30 دقیقه",
                        }
                    },
                    "retrieved_sources": (
                        "[SOURCE 1: بازاریابی]\n"
                        "بازاریابی از داشتن راه‌حل شروع نمی‌شود؛ از فهم مسئله و موقعیت استفاده مشتری شروع می‌شود. "
                        "ابتدا موقعیت استفاده، هزینه مسئله و جایگزین فعلی را بنویس، سپس درباره پیام و کانال تصمیم بگیر."
                    ),
                },
                ensure_ascii=False,
            ),
        )
        data = json.loads(raw)

        self.assertIn("فهم مسئله مشتری", data["answer"])
        self.assertIn("سه گفت‌وگوی کوتاه", data["answer"])
        self.assertIn("بازاریابی محصول", data["answer"])
        self.assertEqual(data["source_numbers"], [1])
        self.assertNotIn("بر اساس محتوای تاییدشده همین سرفصل", data["answer"])

    def test_embedding_endpoint_falls_back_to_the_chat_gateway(self) -> None:
        settings = get_settings()

        self.assertEqual(settings.effective_embedding_api_base_url, settings.arvan_api_base_url)
        self.assertTrue(settings.has_embedding_configuration)
