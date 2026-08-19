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
                "course_rag_configs",
                "course_kb_document_chunks",
                "course_kb_index_jobs",
                "coach_threads",
                "coach_messages",
                "coach_retrieval_events",
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
        kb_chunk_columns = {
            column["name"]
            for column in inspector.get_columns("course_kb_document_chunks")
        }
        coach_message_columns = {
            column["name"]
            for column in inspector.get_columns("coach_messages")
        }

        self.assertTrue({"course_version_id", "module_number", "learning_objectives_json", "tags_json"}.issubset(module_columns))
        self.assertTrue({"course_module_id", "template_id", "stage_number", "content_json"}.issubset(module_stage_columns))
        self.assertTrue({"enrollment_id", "module_stage_content_id", "status"}.issubset(module_progress_columns))
        self.assertTrue({"course_version_id", "content_checksum", "status"}.issubset(kb_columns))
        self.assertTrue(
            {
                "document_id",
                "course_version_id",
                "content",
                "embedding",
                "embedding_input_checksum",
                "embedding_status",
            }.issubset(kb_chunk_columns)
        )
        self.assertTrue({"thread_id", "module_stage_content_id", "role", "content"}.issubset(coach_message_columns))

    def test_enrollment_cannot_point_to_a_different_course_than_its_version(self) -> None:
        inspector = inspect(self.engine)
        foreign_keys = inspector.get_foreign_keys("user_course_enrollments")
        constraints = inspector.get_check_constraints("user_course_enrollments")
        indexes = inspector.get_indexes("user_course_enrollments")

        composite_version_fk = next(
            (
                item
                for item in foreign_keys
                if item["name"] == "fk_user_course_enrollments_version_course"
            ),
            None,
        )
        self.assertIsNotNone(composite_version_fk)
        self.assertEqual(composite_version_fk["constrained_columns"], ["course_version_id", "course_id"])
        self.assertEqual(composite_version_fk["referred_table"], "course_versions")
        self.assertEqual(composite_version_fk["referred_columns"], ["id", "course_id"])

        check_names = {item["name"] for item in constraints}
        self.assertIn("ck_user_course_enrollments_current_stage_number", check_names)
        self.assertIn("ck_user_course_enrollments_progress_percentage", check_names)
        self.assertIn(
            "ix_user_course_enrollments_user_status",
            {item["name"] for item in indexes},
        )
