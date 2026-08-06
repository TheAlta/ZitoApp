import unittest

from sqlalchemy import create_engine, inspect

from tests._env import setup_test_environment

setup_test_environment()

import src.models  # Ensure all SQLAlchemy tables are registered on Base.metadata.
from src.db import Base


class CanonicalSchemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine("sqlite://")
        Base.metadata.create_all(bind=cls.engine)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.engine.dispose()

    def test_user_identity_and_profile_have_one_source_of_truth(self) -> None:
        inspector = inspect(self.engine)
        tables = set(inspector.get_table_names())
        user_columns = {
            column["name"]: column
            for column in inspector.get_columns("users")
        }
        profile_columns = {
            column["name"]: column
            for column in inspector.get_columns("user_profiles")
        }

        self.assertNotIn("username", user_columns)
        self.assertNotIn("full_name", user_columns)
        self.assertNotIn("profession", user_columns)
        self.assertFalse(user_columns["phone"]["nullable"])
        self.assertFalse(user_columns["display_name"]["nullable"])
        self.assertTrue(user_columns["blocked_at"]["nullable"])

        self.assertEqual(
            set(profile_columns),
            {
                "user_id",
                "work_or_study_field",
                "education_level",
                "learning_goal_interests",
                "ai_familiarity_level",
                "daily_learning_time_text",
                "daily_learning_minutes",
                "preferred_career_path",
                "referral_source",
                "completed_at",
                "created_at",
                "updated_at",
            },
        )
        self.assertTrue(profile_columns["user_id"]["primary_key"])

        for legacy_table in {
            "answers",
            "questions",
            "knowledge_documents",
            "profile_builder_answers",
            "user_profiles_v2",
            "user_progress",
        }:
            self.assertNotIn(legacy_table, tables)

    def test_module_scoped_learning_contract_is_present(self) -> None:
        inspector = inspect(self.engine)
        tables = set(inspector.get_table_names())
        self.assertTrue(
            {
                "learning_stage_templates",
                "course_modules",
                "course_module_stage_contents",
                "course_kb_document_modules",
                "user_module_stage_progress",
            }.issubset(tables)
        )

        module_columns = {column["name"] for column in inspector.get_columns("course_modules")}
        module_stage_columns = {
            column["name"]
            for column in inspector.get_columns("course_module_stage_contents")
        }
        module_progress_columns = {
            column["name"]
            for column in inspector.get_columns("user_module_stage_progress")
        }
        kb_columns = {column["name"] for column in inspector.get_columns("course_kb_documents")}

        self.assertTrue({"course_version_id", "module_number", "learning_objectives_json", "tags_json"}.issubset(module_columns))
        self.assertTrue({"course_module_id", "template_id", "stage_number", "content_json"}.issubset(module_stage_columns))
        self.assertTrue({"enrollment_id", "module_stage_content_id", "status"}.issubset(module_progress_columns))
        self.assertIn("course_version_id", kb_columns)
