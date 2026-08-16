import unittest

from sqlalchemy import func, select

from tests._env import setup_test_environment

setup_test_environment()

from src.db import Base, SessionLocal, engine
from src.models import Course, CourseKbDocument, CourseKbDocumentModule, CourseKbIndexJob, CourseModule, CourseVersion
from src.seed import seed_defaults
from src.services.kb_import import load_personal_development_mock_sources, sync_personal_development_mock_kb


class MarkdownKnowledgeBaseImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    def _course_version_and_modules(self, db):
        course = db.scalars(select(Course).where(Course.slug == "personal-development-ai")).one()
        version = db.scalars(
            select(CourseVersion).where(
                CourseVersion.course_id == course.id,
                CourseVersion.version_number == 2,
            )
        ).one()
        modules = list(
            db.scalars(
                select(CourseModule)
                .where(CourseModule.course_version_id == version.id)
                .order_by(CourseModule.module_number)
            ).all()
        )
        return course, version, {module.module_number: module for module in modules}

    def test_seed_uses_the_checked_in_markdown_as_traceable_module_sources(self) -> None:
        with SessionLocal() as db:
            seed_defaults(db)
            course, version, modules_by_number = self._course_version_and_modules(db)
            sources = load_personal_development_mock_sources(
                course_title=course.title,
                modules_by_number=modules_by_number,
            )
            documents = list(
                db.scalars(
                    select(CourseKbDocument)
                    .where(CourseKbDocument.course_version_id == version.id)
                    .order_by(CourseKbDocument.id)
                ).all()
            )
            scopes = list(
                db.scalars(
                    select(CourseKbDocumentModule).where(
                        CourseKbDocumentModule.course_version_id == version.id
                    )
                ).all()
            )
            queued_jobs = db.scalar(
                select(func.count())
                .select_from(CourseKbIndexJob)
                .where(CourseKbIndexJob.course_version_id == version.id)
            )

            self.assertEqual([item.module_number for item in sources], [None, 1, 2, 3, 4, 5])
            self.assertEqual(len(documents), 6)
            self.assertEqual(len(scopes), 5)
            self.assertEqual(queued_jobs, 6)
            self.assertEqual(
                {document.source_reference for document in documents},
                {source.source_reference for source in sources},
            )
            module_one = next(document for document in documents if document.source_reference.endswith("#module-1"))
            self.assertIn("سرفصل", module_one.content)
            self.assertEqual(module_one.source_type, "mock_markdown")
            self.assertEqual(course.title, "توسعه فردی با هوش مصنوعی")

    def test_repeated_sync_is_idempotent_and_does_not_enqueue_duplicate_work(self) -> None:
        with SessionLocal() as db:
            seed_defaults(db)
            course, version, modules_by_number = self._course_version_and_modules(db)
            first_document_count = db.scalar(
                select(func.count())
                .select_from(CourseKbDocument)
                .where(CourseKbDocument.course_version_id == version.id)
            )
            first_job_count = db.scalar(
                select(func.count())
                .select_from(CourseKbIndexJob)
                .where(CourseKbIndexJob.course_version_id == version.id)
            )

            summary = sync_personal_development_mock_kb(
                db,
                course=course,
                course_version=version,
                modules_by_number=modules_by_number,
            )
            db.commit()
            second_document_count = db.scalar(
                select(func.count())
                .select_from(CourseKbDocument)
                .where(CourseKbDocument.course_version_id == version.id)
            )
            second_job_count = db.scalar(
                select(func.count())
                .select_from(CourseKbIndexJob)
                .where(CourseKbIndexJob.course_version_id == version.id)
            )

        self.assertEqual(summary.created, 0)
        self.assertEqual(summary.updated, 0)
        self.assertEqual(summary.chunk_changes, 0)
        self.assertEqual(first_document_count, second_document_count)
        self.assertEqual(first_job_count, second_job_count)
