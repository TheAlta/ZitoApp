import unittest

from tests._env import setup_test_environment

setup_test_environment()

from src.api.routes import _learner_stage_content
from src.services.cms import CmsError, GeneratedModule, _quiz_balance_issue, _refine_module_assessment


def _quiz_content(questions):
    return {"intro": "", "blocks": [{"kind": "paragraph", "body": "متن"}, {"kind": "quiz", "items": questions}]}


def _module(options):
    stage = {"type": "module_assessment", "content_json": _quiz_content([{"id": "q1", "question": "موقعیت", "options": options}])}
    return GeneratedModule(number=1, title="سرفصل", description="", learning_objectives=[], tags=[], stages=[stage], knowledge_base="")


class LearnerQuizOrderTests(unittest.TestCase):
    def test_options_are_shuffled_stably_without_losing_or_changing_any(self):
        questions = [{"id": f"q{index}", "question": "؟", "options": ["درست", "غلط ۱", "غلط ۲", "غلط ۳"]} for index in range(8)]
        content = _quiz_content(questions)
        shown = _learner_stage_content(content, "41:7")
        items = shown["blocks"][1]["items"]
        self.assertTrue(all(sorted(item["options"]) == sorted(questions[0]["options"]) for item in items))
        self.assertTrue(any(item["options"][0] != "درست" for item in items))
        self.assertEqual(_learner_stage_content(content, "41:7"), shown)
        self.assertEqual(content["blocks"][1]["items"][0]["options"][0], "درست")
        self.assertEqual(shown["blocks"][0], content["blocks"][0])

    def test_content_without_a_quiz_is_returned_as_is(self):
        content = {"blocks": [{"kind": "paragraph", "body": "متن"}]}
        self.assertIs(_learner_stage_content(content, "1:1"), content)


class QuizBalanceTests(unittest.TestCase):
    def test_a_much_longer_correct_option_is_flagged(self):
        issue = _quiz_balance_issue(_module([
            "برای امتحان سه روز دیگر یک برنامه روزانه با مرور و تمرین و زمان مشخص پیشنهاد بده.",
            "برنامه‌ریزی کن.", "کمکم کن.", "یک متن بنویس.",
        ]))
        self.assertIn("لو می‌دهد", issue)

    def test_balanced_options_pass(self):
        self.assertIsNone(_quiz_balance_issue(_module([
            "زمان آزاد و سطح فعلی‌ام را می‌گویم و برنامه‌ی روزانه می‌خواهم.",
            "فهرست کامل فصل‌ها را می‌دهم و خلاصه‌ی همه را می‌خواهم.",
            "از آن می‌خواهم سخت‌ترین سؤال‌های امتحان را حدس بزند.",
            "برنامه‌ی یک هفته‌ای فشرده بدون روز استراحت می‌خواهم.",
        ])))


LONG_CORRECT = ["برای امتحان سه روز دیگر یک برنامه روزانه با مرور و تمرین و زمان مشخص پیشنهاد بده.", "برنامه‌ریزی کن.", "کمکم کن.", "یک متن بنویس."]
BALANCED = ["زمان آزاد و سطح فعلی‌ام را می‌گویم و برنامه‌ی روزانه می‌خواهم.", "فهرست فصل‌ها را می‌دهم و خلاصه‌ی همه را می‌خواهم.",
            "از آن می‌خواهم سخت‌ترین سؤال‌های امتحان را حدس بزند.", "برنامه‌ی یک هفته‌ای فشرده بدون استراحت می‌خواهم."]


class AssessmentRefinementTests(unittest.IsolatedAsyncioTestCase):
    async def _refine(self, options, reply):
        calls = []

        async def request_json(system_prompt, user_message):
            calls.append(user_message)
            if isinstance(reply, Exception):
                raise reply
            return reply

        refined = await _refine_module_assessment(_module(options), {"title": "دوره"}, request_json)
        return refined, calls

    async def test_giveaway_options_are_rewritten_and_the_answer_key_follows(self):
        refined, calls = await self._refine(LONG_CORRECT, {"items": [{"id": "q1", "question": "موقعیت واقعی یک دانشجو قبل از امتحان؟", "options": BALANCED}]})
        stage = refined.stages[0]
        self.assertEqual(len(calls), 1)
        self.assertEqual(stage["content_json"]["blocks"][1]["items"][0]["options"], BALANCED)
        self.assertEqual(stage["evaluation_config_json"]["questions"][0]["correct_option"], BALANCED[0])
        self.assertIsNone(_quiz_balance_issue(refined))

    async def test_balanced_quiz_is_left_alone_without_a_call(self):
        module = _module(BALANCED)
        refined, calls = await self._refine(BALANCED, {"items": []})
        self.assertEqual(calls, [])
        self.assertEqual(refined.stages, module.stages)

    async def test_a_failed_rewrite_keeps_the_original_quiz(self):
        refined, calls = await self._refine(LONG_CORRECT, CmsError("gateway down"))
        self.assertEqual(len(calls), 2)
        self.assertEqual(refined.stages[0]["content_json"]["blocks"][1]["items"][0]["options"], LONG_CORRECT)


if __name__ == "__main__":
    unittest.main()
