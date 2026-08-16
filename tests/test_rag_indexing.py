import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from tests._env import setup_test_environment

setup_test_environment()

from src.db import Base, SessionLocal, engine
from src.models import (
    CourseKbDocument,
    CourseKbDocumentChunk,
    CourseKbDocumentModule,
    CourseKbIndexJob,
    CourseModule,
    CourseVersion,
)
from src.seed import seed_defaults
from src.services.rag import (
    document_content_checksum,
    retrieve_course_chunks,
    run_index_worker_once,
    sync_document_chunks,
)


class RAGIndexingContractTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed_defaults(db)

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    async def test_jobs_index_documents_and_retrieval_respects_scope_without_mutation(self) -> None:
        with SessionLocal() as db:
            queued_before = db.scalar(
                select(func.count()).select_from(CourseKbIndexJob).where(CourseKbIndexJob.status == "queued")
            )
        self.assertGreater(queued_before or 0, 0)
        processed = await run_index_worker_once(SessionLocal, limit=50)
        self.assertTrue(processed)
        self.assertTrue(all(job.status == "succeeded" for job in processed))

        with SessionLocal() as db:
            version = db.scalars(
                select(CourseVersion).where(CourseVersion.version_number == 2)
            ).one()
            modules = db.scalars(
                select(CourseModule)
                .where(CourseModule.course_version_id == version.id)
                .order_by(CourseModule.module_number)
            ).all()
            module_one, module_two = modules[:2]
            version_id = version.id
            course_id = version.course_id
            module_one_id = module_one.id
            module_two_id = module_two.id
            indexed_chunks = db.scalar(
                select(func.count())
                .select_from(CourseKbDocumentChunk)
                .where(CourseKbDocumentChunk.embedding_status == "indexed")
            )
            self.assertGreater(indexed_chunks or 0, 0)

            global_document = CourseKbDocument(
                course_id=course_id,
                course_version_id=version_id,
                title="Course global source",
                content="shared-global-token is available for every module in this course version.",
                content_checksum=document_content_checksum(
                    "shared-global-token is available for every module in this course version."
                ),
                source_type="test",
                status="approved",
            )
            other_module_document = CourseKbDocument(
                course_id=course_id,
                course_version_id=version_id,
                title="Other module only source",
                content="other-module-secret-token belongs only to the second module.",
                content_checksum=document_content_checksum(
                    "other-module-secret-token belongs only to the second module."
                ),
                source_type="test",
                status="approved",
            )
            db.add_all([global_document, other_module_document])
            db.flush()
            global_document_id = global_document.id
            other_module_document_id = other_module_document.id
            db.add(
                CourseKbDocumentModule(
                    document_id=other_module_document.id,
                    course_module_id=module_two_id,
                    course_version_id=version_id,
                )
            )
            sync_document_chunks(db, [global_document, other_module_document])
            db.commit()

        indexed_follow_up = await run_index_worker_once(SessionLocal, limit=50)
        self.assertTrue(indexed_follow_up)
        self.assertTrue(all(job.status == "succeeded" for job in indexed_follow_up))

        with SessionLocal() as db:
            before_counts = (
                db.scalar(select(func.count()).select_from(CourseKbDocumentChunk)),
                db.scalar(select(func.count()).select_from(CourseKbIndexJob)),
            )
            global_result = await retrieve_course_chunks(
                db,
                course_version_id=version_id,
                module_id=module_one_id,
                question="shared-global-token",
            )
            isolated_result = await retrieve_course_chunks(
                db,
                course_version_id=version_id,
                module_id=module_one_id,
                question="other-module-secret-token",
            )
            after_counts = (
                db.scalar(select(func.count()).select_from(CourseKbDocumentChunk)),
                db.scalar(select(func.count()).select_from(CourseKbIndexJob)),
            )

        self.assertEqual(global_result.method, "sqlite_test_cosine")
        self.assertIn(global_document_id, [chunk.document_id for chunk in global_result.chunks])
        self.assertIn("course_global", [chunk.scope for chunk in global_result.chunks])
        self.assertNotIn(other_module_document_id, [chunk.document_id for chunk in isolated_result.chunks])
        self.assertEqual(before_counts, after_counts)


class RAGWorkerLeaseTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed_defaults(db)

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    async def test_expired_running_job_is_recovered_without_being_lost(self) -> None:
        with SessionLocal() as db:
            expired = db.scalars(
                select(CourseKbIndexJob).where(CourseKbIndexJob.status == "queued")
            ).first()
            self.assertIsNotNone(expired)
            expired_id = expired.id
            expired.status = "running"
            expired.attempt_count = 1
            expired.started_at = datetime.now(timezone.utc) - timedelta(minutes=5)
            db.commit()

        outcomes = await run_index_worker_once(SessionLocal, limit=1)
        self.assertTrue(outcomes)

        with SessionLocal() as db:
            recovered = db.get(CourseKbIndexJob, expired_id)
            self.assertEqual(recovered.status, "retry")
            self.assertIn("lease expired", recovered.error_message)


if __name__ == "__main__":
    unittest.main()
