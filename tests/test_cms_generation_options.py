import unittest

from tests._env import setup_test_environment

setup_test_environment()

from src.services.cms import (
    _ai_generation_brief,
    _generation_options,
    _module_from_response,
    _supports_rich_module_generation,
    _stages_from_outline,
    stage_flow,
)


class CmsGenerationOptionsTests(unittest.TestCase):
    def test_gpt_uses_prompt_json_and_completion_limit(self) -> None:
        self.assertEqual(
            _generation_options("GPT-5.1", output_budget=2048),
            {"max_completion_tokens": 2048},
        )

    def test_other_models_keep_native_json_mode(self) -> None:
        self.assertEqual(
            _generation_options("GLM-5.3", output_budget=1100),
            {
                "response_format": {"type": "json_object"},
                "max_tokens": 1100,
                "reasoning_effort": "low",
            },
        )

    def test_only_gpt_41_uses_full_module_generation(self) -> None:
        self.assertTrue(_supports_rich_module_generation("GPT-4.1"))
        self.assertFalse(_supports_rich_module_generation("GPT-5.1"))
        self.assertFalse(_supports_rich_module_generation("GLM-5.3"))

    def test_assessment_key_is_derived_from_the_first_public_option(self) -> None:
        stages = []
        for stage_type in stage_flow(8):
            blocks = []
            if stage_type == "module_assessment":
                blocks = [{
                    "kind": "quiz",
                    "items": [{
                        "id": "q1",
                        "question": "Which option is correct?",
                        "options": ["First", "Second", "Third"],
                    }],
                }]
            stages.append({
                "type": stage_type,
                "title": stage_type,
                "content": {"intro": "Short content", "blocks": blocks, "activity": {}},
            })

        module = _module_from_response(
            {
                "title": "Synthetic module",
                "description": "Synthetic description",
                "learning_objectives": ["One objective"],
                "tags": ["synthetic"],
                "knowledge_base": "Synthetic knowledge base",
                "stages": stages,
            },
            number=1,
            stage_count=8,
        )

        assessment = next(stage for stage in module.stages if stage["type"] == "module_assessment")
        self.assertEqual(assessment["evaluation_config_json"]["questions"][0]["correct_option"], "First")
        self.assertTrue(assessment["content_json"]["coaching"]["enabled"])

    def test_assessment_derives_each_public_question_key(self) -> None:
        stages = []
        for stage_type in stage_flow(8):
            blocks = []
            if stage_type == "module_assessment":
                blocks = [{
                    "kind": "quiz",
                    "items": [
                        {"id": "q1", "question": "First?", "options": ["Right", "Wrong", "Wrong"]},
                        {"id": "q2", "question": "Second?", "options": ["Correct", "No", "No"]},
                    ],
                }]
            stages.append({
                "type": stage_type,
                "title": stage_type,
                "content": {"intro": "Short content", "blocks": blocks, "activity": {}},
            })

        module = _module_from_response(
            {
                "title": "Synthetic module",
                "description": "Synthetic description",
                "learning_objectives": ["One objective"],
                "tags": ["synthetic"],
                "knowledge_base": "Synthetic knowledge base",
                "stages": stages,
            },
            number=1,
            stage_count=8,
        )
        assessment = next(stage for stage in module.stages if stage["type"] == "module_assessment")
        self.assertEqual(len(assessment["evaluation_config_json"]["questions"]), 2)

    def test_gpt_outline_uses_a_safe_brief_and_builds_all_stages_locally(self) -> None:
        brief = {
            "title": "Course title",
            "topic": "Course topic",
            "goal": "Practice the topic",
            "duration": "Two weeks",
            "audience": "Beginners",
            "target_group": "Team members",
            "level": "Beginner",
            "module_count": 2,
            "estimated_learning_hours": 6,
            "module_stage_count": 8,
            "slug": "internal-slug",
            "domain": "internal-domain",
            "requires_final_exam": True,
        }

        ai_brief = _ai_generation_brief(brief)
        self.assertNotIn("slug", ai_brief)
        self.assertNotIn("domain", ai_brief)
        self.assertNotIn("requires_final_exam", ai_brief)

        module = _stages_from_outline(
            {
                "title": "A generated outline module",
                "description": "A generated outline description",
                "learning_objectives": ["Apply one concept"],
                "tags": ["topic"],
            },
            brief,
            number=1,
        )
        self.assertEqual(len(module.stages), 8)
        self.assertEqual(module.stages[-2]["type"], "module_assessment")
        self.assertIsNotNone(module.stages[-2]["evaluation_config_json"])
