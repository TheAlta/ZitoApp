import unittest

from tests._env import setup_test_environment

setup_test_environment()

from src.services.cms import _generation_options, _module_from_response, stage_flow


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
