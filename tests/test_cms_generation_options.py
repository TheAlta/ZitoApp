import asyncio
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from tests._env import setup_test_environment

setup_test_environment()

from src.services.cms import (
    _ai_generation_brief,
    _generation_options,
    _module_from_response,
    _request_generated_json,
    _supports_rich_module_generation,
    _stages_from_outline,
    _validate_generated_module_quality,
    CmsError,
    GeneratedModule,
    generate_curriculum,
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

    def test_gpt_41_uses_json_mode_without_unsupported_reasoning_option(self) -> None:
        self.assertEqual(
            _generation_options("GPT-4.1", output_budget=10000),
            {
                "response_format": {"type": "json_object"},
                "max_tokens": 10000,
            },
        )

    def test_malformed_json_is_retried_before_course_generation_fails(self) -> None:
        settings = {
            "model": "GPT-4.1",
            "api_base_url": "https://example.invalid/v1",
            "api_key": "test",
            "timeout_seconds": 180,
        }
        ai = AsyncMock(side_effect=['{"overview": {"summary": "broken"}', '{"overview": {}}'])

        with patch("src.services.cms.ask_ai", ai):
            result = asyncio.run(
                _request_generated_json(
                    "Return JSON only.",
                    "{}",
                    **settings,
                    output_budget=100,
                    task_label="نقشه دوره",
                    attempts=3,
                )
            )

        self.assertEqual(result, {"overview": {}})
        self.assertEqual(ai.await_count, 2)
        self.assertIn("previous response was not valid JSON", ai.await_args_list[1].args[0])

    def test_permanently_malformed_json_has_a_friendly_cms_error(self) -> None:
        settings = {
            "model": "GPT-4.1",
            "api_base_url": "https://example.invalid/v1",
            "api_key": "test",
            "timeout_seconds": 180,
        }
        ai = AsyncMock(return_value='{"overview": {"summary": "broken"}')

        with patch("src.services.cms.ask_ai", ai):
            with self.assertRaisesRegex(CmsError, "پاسخ ساختاریافته معتبر") as error:
                asyncio.run(
                    _request_generated_json(
                        "Return JSON only.",
                        "{}",
                        **settings,
                        output_budget=100,
                        task_label="نقشه دوره",
                        attempts=3,
                    )
                )

        self.assertNotIn("Expecting", str(error.exception))
        self.assertEqual(ai.await_count, 3)

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
            "generation_instructions": "Use realistic workplace scenarios.",
            "slug": "internal-slug",
            "domain": "internal-domain",
            "requires_final_exam": True,
        }

        ai_brief = _ai_generation_brief(brief)
        self.assertNotIn("slug", ai_brief)
        self.assertNotIn("domain", ai_brief)
        self.assertNotIn("requires_final_exam", ai_brief)
        self.assertEqual(ai_brief["generation_instructions"], "Use realistic workplace scenarios.")

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

    def test_shallow_generated_module_is_rejected(self) -> None:
        module = _stages_from_outline(
            {
                "title": "Shallow module",
                "description": "Only an outline, not a complete lesson.",
                "learning_objectives": ["Learn something"],
                "tags": ["test"],
            },
            {"title": "Course", "topic": "Topic", "goal": "Goal"},
            number=1,
        )
        with self.assertRaisesRegex(ValueError, "بیش از حد کوتاه"):
            _validate_generated_module_quality(module)

    def test_adaptive_content_counts_pass_quality_without_fixed_six_item_quotas(self) -> None:
        contents = {
            "learning_path": {"blocks": []},
            "lesson_summary": {"blocks": [
                {"kind": "cards", "items": [
                    {"title": f"section {index}", "body": "a" * 230}
                    for index in range(3)
                ]},
            ]},
            "flashcards": {"blocks": [{"kind": "flashcards", "items": [
                {"front": f"concept {index}", "back": "A detailed explanation with a practical application and context."}
                for index in range(4)
            ]}]},
            "golden_tips": {"blocks": [{"kind": "tips", "items": [
                "A detailed and practical recommendation for the learner."
            ] * 3}]},
            "common_mistakes": {"blocks": [{"kind": "mistakes", "items": [
                {"mistake": "A realistic mistake", "correction": "Use this better approach because it addresses the cause."}
            ] * 3}]},
            "personalized_work_example": {"blocks": [{"kind": "personalized_example"}]},
            "module_assessment": {"blocks": [{"kind": "quiz", "items": [
                {
                    "id": f"q{index}",
                    "question": f"A distinct scenario question number {index} with enough detail?",
                    "options": ["Correct", "Plausible", "Alternative"],
                }
                for index in range(3)
            ]}]},
            "module_completion": {"intro": "c" * 260, "blocks": [
                {"kind": "steps", "items": ["one", "two", "three"]},
            ]},
        }
        module = GeneratedModule(
            number=1,
            title="Adaptive module",
            description="Complete adaptive module",
            learning_objectives=["Apply the skill"],
            tags=["adaptive"],
            stages=[
                {"type": stage_type, "content_json": contents[stage_type]}
                for stage_type in stage_flow(8)
            ],
            knowledge_base="k" * 1800,
        )

        _validate_generated_module_quality(module)

    def test_personalized_stage_placeholder_is_restored_when_ai_omits_it(self) -> None:
        stages = []
        for stage_type in stage_flow(8):
            blocks = [{"kind": "steps", "items": ["Apply it"]}]
            if stage_type == "module_assessment":
                blocks = [{"kind": "quiz", "items": [{
                    "id": "q1",
                    "question": "Which practical option is correct?",
                    "options": ["Correct", "Wrong", "Other"],
                }]}]
            stages.append({
                "type": stage_type,
                "title": stage_type,
                "content": {"intro": "Intro", "blocks": blocks, "activity": {}},
            })

        module = _module_from_response({
            "title": "Personalized module",
            "description": "Description",
            "learning_objectives": ["Objective"],
            "tags": ["tag"],
            "knowledge_base": "Knowledge",
            "stages": stages,
        }, number=1, stage_count=8)

        personalized = next(
            stage for stage in module.stages
            if stage["type"] == "personalized_work_example"
        )
        blocks = personalized["content_json"]["blocks"]
        self.assertEqual(sum(block.get("kind") == "personalized_example" for block in blocks), 1)
        self.assertEqual(blocks[1]["kind"], "steps")

    def test_generation_prompts_define_adaptive_depth(self) -> None:
        outline = Path("src/prompts/course_outline_generation.md").read_text(encoding="utf-8")
        module = Path("src/prompts/course_module_generation.md").read_text(encoding="utf-8")

        self.assertIn("depth_profile", outline)
        self.assertIn("content_blueprint", outline)
        self.assertIn("planning response compact", outline)
        self.assertIn("stage is adaptive", module)
        self.assertIn('"personalized_example"', module)
        self.assertNotIn("exactly six", module.lower())

    def test_gpt_41_generates_each_module_with_ai_instead_of_static_stages(self) -> None:
        brief = {
            "title": "Deep course",
            "topic": "Deep topic",
            "goal": "Build a real skill",
            "duration": "Four weeks",
            "audience": "Learners",
            "target_group": "Professionals",
            "level": "Beginner",
            "module_count": 1,
            "estimated_learning_hours": 12,
            "generation_instructions": "Use complete explanations.",
        }
        outline = json.dumps({
            "overview": {
                "summary": "Course summary",
                "description": "Course description",
                "learning_outcomes": ["Outcome"],
                "career_outcomes": ["Career"],
                "daily_life_outcomes": ["Daily"],
            },
            "modules": [{
                "title": "Module one",
                "description": "Module description",
                "learning_objectives": ["Objective"],
                "tags": ["tag"],
            }],
        })
        generated_module = GeneratedModule(
            number=1,
            title="Module one",
            description="Module description",
            learning_objectives=["Objective"],
            tags=["tag"],
            stages=[],
            knowledge_base="k" * 2000,
        )
        settings = SimpleNamespace(
            arvan_mock_ai=False,
            effective_content_generation_model="GPT-4.1",
            effective_content_generation_api_base_url="https://example.invalid/v1",
            effective_content_generation_api_key="test",
            arvan_content_generation_timeout_seconds=180,
        )
        ai = AsyncMock(side_effect=[outline, "{}"])
        with (
            patch("src.services.cms.get_settings", return_value=settings),
            patch("src.services.cms.ask_ai", ai),
            patch("src.services.cms._module_from_response", return_value=generated_module),
            patch("src.services.cms._validate_generated_module_quality"),
            patch("src.services.cms._validate_curriculum_question_variety"),
        ):
            curriculum = asyncio.run(generate_curriculum(brief))

        self.assertEqual(curriculum.modules, [generated_module])
        self.assertEqual(ai.await_count, 2)
        module_request = ai.await_args_list[1]
        self.assertIn("generation_instructions", module_request.args[1])
        self.assertEqual(module_request.kwargs["max_tokens"], 10000)

    def test_failed_module_quality_is_retried_with_feedback(self) -> None:
        brief = {
            "title": "Deep course",
            "topic": "Deep topic",
            "goal": "Build a real skill",
            "duration": "Four weeks",
            "audience": "Learners",
            "target_group": "Professionals",
            "level": "Beginner",
            "module_count": 1,
            "estimated_learning_hours": 12,
        }
        outline = json.dumps({
            "overview": {
                "summary": "Course summary",
                "description": "Course description",
                "learning_outcomes": ["Outcome"],
                "career_outcomes": ["Career"],
                "daily_life_outcomes": ["Daily"],
            },
            "modules": [{"title": "Module one", "description": "Description"}],
        })
        generated_module = GeneratedModule(
            number=1,
            title="Module one",
            description="Description",
            learning_objectives=["Objective"],
            tags=["tag"],
            stages=[],
            knowledge_base="k" * 2000,
        )
        settings = SimpleNamespace(
            arvan_mock_ai=False,
            effective_content_generation_model="GPT-4.1",
            effective_content_generation_api_base_url="https://example.invalid/v1",
            effective_content_generation_api_key="test",
            arvan_content_generation_timeout_seconds=180,
        )
        ai = AsyncMock(side_effect=[outline, "{}", "{}"])
        with (
            patch("src.services.cms.get_settings", return_value=settings),
            patch("src.services.cms.ask_ai", ai),
            patch("src.services.cms._module_from_response", return_value=generated_module),
            patch(
                "src.services.cms._validate_generated_module_quality",
                side_effect=[CmsError("knowledge base is short"), None],
            ),
            patch("src.services.cms._validate_curriculum_question_variety"),
        ):
            curriculum = asyncio.run(generate_curriculum(brief))

        self.assertEqual(curriculum.modules, [generated_module])
        self.assertEqual(ai.await_count, 3)
        retry_payload = json.loads(ai.await_args_list[2].args[1])
        self.assertIn("knowledge base is short", retry_payload["repair_feedback"])
