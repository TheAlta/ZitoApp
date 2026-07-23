import unittest

from sqlalchemy import select

from tests._env import setup_test_environment

setup_test_environment()

from src.db import Base, SessionLocal, engine
from src.models import Course, CourseKbDocument, CourseStageContent, CourseVersion, Exam
from src.seed import PHASE2_STAGE_TYPES, seed_defaults


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
            version = db.scalars(
                select(CourseVersion).where(
                    CourseVersion.course_id == course.id,
                    CourseVersion.version_number == 1,
                )
            ).one()
            stages = db.scalars(
                select(CourseStageContent)
                .where(CourseStageContent.course_version_id == version.id)
                .order_by(CourseStageContent.stage_number)
            ).all()
            kb_docs = db.scalars(
                select(CourseKbDocument).where(CourseKbDocument.course_id == course.id)
            ).all()
            exam = db.scalars(
                select(Exam).where(Exam.course_version_id == version.id)
            ).one()

        self.assertEqual(course.status, "published")
        self.assertEqual(version.status, "published")
        self.assertEqual(len(PHASE2_STAGE_TYPES), 20)
        self.assertEqual(len(stages), 20)
        self.assertEqual([stage.stage_number for stage in stages], list(range(1, 21)))
        self.assertTrue(all(stage.review_status == "approved" for stage in stages))
        self.assertEqual(len(kb_docs), 3)
        self.assertEqual(exam.passing_score, 70)
        self.assertEqual(len(exam.questions_json), 2)
