import unittest

from sqlalchemy import select

from tests._env import setup_test_environment

setup_test_environment()

from src.db import Base, SessionLocal, engine
from src.models import (
    Course,
    CourseKbDocument,
    CourseKbDocumentModule,
    CourseModule,
    CourseModuleStageContent,
    CourseStageContent,
    CourseVersion,
    Exam,
    LearningStageTemplate,
)
from src.seed import EIGHT_STAGE_FLOW_TYPES, PHASE2_STAGE_TYPES, seed_defaults


class Phase2SeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    def test_fake_cms_seed_creates_published_course_contract(self) -> None:
        with SessionLocal() as db:
            seed_defaults(db)
            seed_defaults(db)

            course = db.scalars(
                select(Course).where(Course.slug == "personal-development-ai")
            ).one()
            legacy_version = db.scalars(
                select(CourseVersion).where(
                    CourseVersion.course_id == course.id,
                    CourseVersion.version_number == 1,
                )
            ).one()
            version = db.scalars(
                select(CourseVersion).where(
                    CourseVersion.course_id == course.id,
                    CourseVersion.version_number == 2,
                )
            ).one()
            active_version = db.scalars(
                select(CourseVersion).where(
                    CourseVersion.course_id == course.id,
                    CourseVersion.version_number == 3,
                )
            ).one()
            legacy_stages = db.scalars(
                select(CourseStageContent)
                .where(CourseStageContent.course_version_id == legacy_version.id)
                .order_by(CourseStageContent.stage_number)
            ).all()
            templates = db.scalars(
                select(LearningStageTemplate).order_by(LearningStageTemplate.default_order)
            ).all()
            modules = db.scalars(
                select(CourseModule)
                .where(CourseModule.course_version_id == version.id)
                .order_by(CourseModule.module_number)
            ).all()
            module_stages = db.scalars(
                select(CourseModuleStageContent)
                .join(CourseModuleStageContent.course_module)
                .where(CourseModule.course_version_id == version.id)
                .order_by(CourseModule.module_number, CourseModuleStageContent.stage_number)
            ).all()
            kb_docs = db.scalars(
                select(CourseKbDocument).where(CourseKbDocument.course_version_id == version.id)
            ).all()
            active_modules = db.scalars(
                select(CourseModule)
                .where(CourseModule.course_version_id == active_version.id)
                .order_by(CourseModule.module_number)
            ).all()
            active_module_stages = db.scalars(
                select(CourseModuleStageContent)
                .join(CourseModuleStageContent.course_module)
                .where(CourseModule.course_version_id == active_version.id)
                .order_by(CourseModule.module_number, CourseModuleStageContent.stage_number)
            ).all()
            active_kb_docs = db.scalars(
                select(CourseKbDocument).where(CourseKbDocument.course_version_id == active_version.id)
            ).all()
            kb_scopes = db.scalars(select(CourseKbDocumentModule)).all()
            exam = db.scalars(
                select(Exam).where(Exam.course_version_id == version.id)
            ).one()
            active_exam = db.scalars(
                select(Exam).where(Exam.course_version_id == active_version.id)
            ).one()

        self.assertEqual(course.status, "published")
        self.assertEqual(version.status, "published")
        self.assertEqual(active_version.status, "published")
        self.assertEqual(len(PHASE2_STAGE_TYPES), 20)
        self.assertEqual(len(EIGHT_STAGE_FLOW_TYPES), 8)
        self.assertEqual(len(legacy_stages), 20)
        self.assertEqual(len(templates), 23)
        self.assertEqual([item.code for item in templates[:3]], ["learning_path", "lesson_summary", "flashcards"])
        template_code_by_id = {item.id: item.code for item in templates}
        self.assertEqual(len(modules), 5)
        self.assertEqual(len(module_stages), 100)
        self.assertEqual(version.module_stage_count, 20)
        self.assertFalse(version.requires_final_exam)
        self.assertTrue(all(stage.review_status == "approved" for stage in module_stages))
        self.assertTrue(all(stage.content_json["contract_version"] == 1 for stage in module_stages))
        self.assertTrue(all(stage.content_json["ui_hint"]["avatar_visible"] for stage in module_stages))
        self.assertTrue(all("blocks" in stage.content_json for stage in module_stages))
        for module in modules:
            module_items = [item for item in module_stages if item.course_module_id == module.id]
            self.assertEqual([item.stage_number for item in module_items], list(range(1, 21)))
            self.assertEqual(template_code_by_id[module_items[0].template_id], "learning_path")
            self.assertEqual(template_code_by_id[module_items[1].template_id], "lesson_summary")
            self.assertEqual(template_code_by_id[module_items[2].template_id], "flashcards")
        audio_slot = module_stages[13].content_json["media_slots"][0]
        self.assertEqual(audio_slot["kind"], "audio")
        self.assertEqual(audio_slot["status"], "empty")
        self.assertIsNone(audio_slot["url"])
        self.assertEqual(len(kb_docs), 6)
        self.assertEqual(len(active_modules), 5)
        self.assertEqual(len(active_module_stages), 40)
        self.assertEqual(active_version.module_stage_count, 8)
        self.assertTrue(active_version.requires_final_exam)
        self.assertTrue(active_version.overview_json["learning_outcomes"])
        self.assertEqual(len(active_kb_docs), 6)
        active_audio_slot = active_module_stages[1].content_json["media_slots"][0]
        self.assertEqual(active_audio_slot["kind"], "audio")
        self.assertEqual(active_audio_slot["status"], "empty")
        self.assertIsNone(active_audio_slot["url"])
        active_template_codes = [template_code_by_id[item.template_id] for item in active_module_stages[:8]]
        self.assertEqual(
            active_template_codes,
            [item["type"] for item in EIGHT_STAGE_FLOW_TYPES],
        )
        for module in active_modules:
            module_items = [item for item in active_module_stages if item.course_module_id == module.id]
            self.assertEqual([item.stage_number for item in module_items], list(range(1, 9)))
            self.assertTrue(all(item.content_json["contract_version"] == 2 for item in module_items))
        assessment_stage = next(
            item
            for item in active_module_stages
            if item.stage_number == 7
        )
        self.assertIsNotNone(assessment_stage.evaluation_config_json)
        self.assertNotIn("correct_option", str(assessment_stage.content_json))
        self.assertEqual(len(kb_scopes), 10)
        self.assertTrue(all(item.source_type == "mock_markdown" for item in kb_docs))
        self.assertTrue(all(item.source_reference for item in kb_docs))
        self.assertTrue(all(item.source_type == "mock_markdown" for item in active_kb_docs))
        self.assertEqual(exam.passing_score, 70)
        self.assertEqual(len(exam.questions_json), 2)
        self.assertEqual(active_exam.status, "draft")
        self.assertEqual(active_exam.questions_json, [])
