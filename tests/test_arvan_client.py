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
