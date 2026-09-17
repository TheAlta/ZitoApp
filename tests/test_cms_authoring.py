import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from tests._env import setup_test_environment

setup_test_environment()

from src.db import Base, SessionLocal, engine
from src.lib.arvan_client import ArvanAIError
from src.main import app
from src.models import CourseKbDocument, CourseKbIndexJob, Exam
from src.seed import seed_defaults
from src.services.cms import CMS_MODULE_STAGE_COUNT, stage_flow
from src.services.rag import run_pending_index_jobs


COURSE_BRIEF = {
    "title": "مدیریت محصول برای تیم‌های کوچک",
    "topic": "مدیریت محصول",
    "goal": "تبدیل ایده‌های محصول به تصمیم‌های قابل آزمون و قابل اندازه‌گیری.",
    "duration": "چهار هفته، روزی سی دقیقه",
    "audience": "افراد علاقه‌مند به ساخت و بهبود محصول دیجیتال",
    "target_group": "بنیان‌گذاران و اعضای تیم محصول کوچک",
    "level": "مقدماتی تا متوسط",
    "module_count": 3,
    "estimated_learning_hours": 12,
    "generation_instructions": "مثال‌ها واقعی، توضیح‌ها مفصل و آزمونک‌ها غیرتکراری باشند.",
    "module_stage_count": 8,
    "slug": "product-management-small-teams",
}


class CmsAuthoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed_defaults(db)

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    def _admin_client(self) -> TestClient:
        client = TestClient(app)
        response = client.post(
            "/api/admin/login",
            json={"username": "zito_admin", "password": "local-test-admin-password"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return client

    def test_cms_uses_the_existing_eight_station_learning_flow(self) -> None:
        flow = stage_flow(CMS_MODULE_STAGE_COUNT)
        self.assertEqual(CMS_MODULE_STAGE_COUNT, 8)
        self.assertEqual(len(flow), 8)
        self.assertEqual(flow[-2:], ("module_assessment", "module_completion"))

    def test_cms_ignores_a_requested_station_count_and_keeps_eight(self) -> None:
        with self._admin_client() as client:
            created = client.post(
                "/api/admin/courses",
                json={
                    **COURSE_BRIEF,
                    "title": "Fixed station contract",
                    "slug": "fixed-station-contract",
                    "module_stage_count": 7,
                },
            )
            self.assertEqual(created.status_code, 201, created.text)
            self.assertEqual(created.json()["module_stage_count"], 8)
            self.assertEqual(created.json()["authoring_brief"]["module_stage_count"], 8)

    def test_admin_can_create_generate_and_edit_a_draft_course(self) -> None:
        with self._admin_client() as client:
            created = client.post("/api/admin/courses", json=COURSE_BRIEF)
            self.assertEqual(created.status_code, 201, created.text)
            draft = created.json()
            self.assertEqual(draft["status"], "draft")
            self.assertEqual(draft["generation_status"], "not_requested")
            self.assertEqual(
                draft["authoring_brief"]["generation_instructions"],
                COURSE_BRIEF["generation_instructions"],
            )
            self.assertEqual(draft["modules"], [])

            generated = client.post(
                f"/api/admin/courses/{draft['course_id']}/versions/{draft['version_number']}/generate"
            )
            self.assertEqual(generated.status_code, 200, generated.text)
            generated_body = generated.json()
            self.assertEqual(generated_body["generation_status"], "generated")
            self.assertEqual(len(generated_body["modules"]), COURSE_BRIEF["module_count"])
            self.assertTrue(all(len(module["stages"]) == 8 for module in generated_body["modules"]))
            self.assertTrue(all(module["status"] == "draft" for module in generated_body["modules"]))

            first_module = generated_body["modules"][0]
            module_edited = client.patch(
                f"/api/admin/courses/{draft['course_id']}/versions/{draft['version_number']}/modules/{first_module['id']}",
                json={
                    "title": "Product discovery foundations",
                    "description": "A reviewed module description for the course editor.",
                    "learning_objectives": ["Frame one customer problem clearly."],
                    "tags": ["discovery", "customer"],
                },
            )
            self.assertEqual(module_edited.status_code, 200, module_edited.text)
            edited_module = module_edited.json()["modules"][0]
            self.assertEqual(edited_module["title"], "Product discovery foundations")
            self.assertEqual(edited_module["tags"], ["discovery", "customer"])

            first_stage = edited_module["stages"][0]
            edited = client.patch(
                f"/api/admin/courses/{draft['course_id']}/versions/{draft['version_number']}/stages/{first_stage['id']}",
                json={"title": "نقشه شروع محصول", "content": {"intro": "متن ویرایش‌شده", "blocks": []}},
            )
            self.assertEqual(edited.status_code, 200, edited.text)
            edited_body = edited.json()
            self.assertEqual(edited_body["generation_status"], "edited")
            self.assertEqual(edited_body["modules"][0]["stages"][0]["title"], "نقشه شروع محصول")
            self.assertEqual(edited_body["modules"][0]["stages"][0]["content"]["intro"], "متن ویرایش‌شده")

    def test_curriculum_brief_change_requires_regeneration_before_publish(self) -> None:
        with self._admin_client() as client:
            created = client.post(
                "/api/admin/courses",
                json={**COURSE_BRIEF, "title": "Regeneration check", "slug": "regeneration-check"},
            )
            self.assertEqual(created.status_code, 201, created.text)
            draft = created.json()
            generated = client.post(
                f"/api/admin/courses/{draft['course_id']}/versions/{draft['version_number']}/generate"
            )
            self.assertEqual(generated.status_code, 200, generated.text)
            changed = client.patch(
                f"/api/admin/courses/{draft['course_id']}/versions/{draft['version_number']}/brief",
                json={
                    "title": "Research decisions for product teams",
                    "duration": "Five weeks, 45 minutes a day",
                    "estimated_learning_hours": 18,
                },
            )
            self.assertEqual(changed.status_code, 200, changed.text)
            self.assertEqual(changed.json()["generation_status"], "needs_regeneration")
            blocked_publish = client.post(
                f"/api/admin/courses/{draft['course_id']}/versions/{draft['version_number']}/publish"
            )
            self.assertEqual(blocked_publish.status_code, 422, blocked_publish.text)

    def test_gateway_failure_marks_draft_failed_without_a_server_error(self) -> None:
        with self._admin_client() as client:
            created = client.post(
                "/api/admin/courses",
                json={
                    **COURSE_BRIEF,
                    "title": "Gateway failure handling",
                    "slug": "gateway-failure-handling",
                },
            )
            self.assertEqual(created.status_code, 201, created.text)
            draft = created.json()

            with patch(
                "src.api.routes.generate_curriculum",
                new=AsyncMock(
                    side_effect=ArvanAIError(
                        "AI gateway returned HTTP 403: Account is debtor"
                    )
                ),
            ):
                generated = client.post(
                    f"/api/admin/courses/{draft['course_id']}/versions/"
                    f"{draft['version_number']}/generate"
                )

            self.assertEqual(generated.status_code, 422, generated.text)
            current = client.get(
                f"/api/admin/courses/{draft['course_id']}/versions/"
                f"{draft['version_number']}"
            )
            self.assertEqual(current.status_code, 200, current.text)
            self.assertEqual(current.json()["generation_status"], "failed")
            self.assertIn("HTTP 403", current.json()["generation_error"])


    def test_publishing_makes_a_course_available_and_queues_its_own_kb(self) -> None:
        publish_brief = {**COURSE_BRIEF, "title": "User research for product", "slug": "user-research-product"}
        with self._admin_client() as client:
            created = client.post("/api/admin/courses", json=publish_brief)
            self.assertEqual(created.status_code, 201, created.text)
            draft = created.json()
            generated = client.post(
                f"/api/admin/courses/{draft['course_id']}/versions/{draft['version_number']}/generate"
            )
            self.assertEqual(generated.status_code, 200, generated.text)
            published = client.post(
                f"/api/admin/courses/{draft['course_id']}/versions/{draft['version_number']}/publish"
            )
            self.assertEqual(published.status_code, 200, published.text)
            self.assertEqual(published.json()["course"]["status"], "published")
            self.assertEqual(published.json()["rag_status"], "queued")
            available = {course["slug"]: course for course in client.get("/api/courses").json()}
            self.assertIn("user-research-product", available)
            self.assertEqual(available["user-research-product"]["module_count"], 3)
            self.assertEqual(available["user-research-product"]["stage_count"], 24)
            rag_pending = client.get(
                f"/api/admin/courses/{draft['course_id']}/versions/{draft['version_number']}/rag-status"
            )
            self.assertEqual(rag_pending.status_code, 200, rag_pending.text)
            self.assertEqual(rag_pending.json()["status"], "queued")
            self.assertEqual(rag_pending.json()["document_count"], 3)
            self.assertEqual(rag_pending.json()["queued_job_count"], 3)

        with SessionLocal() as db:
            documents = db.scalar(
                select(func.count()).select_from(CourseKbDocument).where(
                    CourseKbDocument.source_type == "cms",
                    CourseKbDocument.course_id == draft["course_id"],
                )
            )
            queued = db.scalar(
                select(func.count())
                .select_from(CourseKbIndexJob)
                .join(CourseKbDocument, CourseKbDocument.id == CourseKbIndexJob.document_id)
                .where(
                    CourseKbIndexJob.status == "queued",
                    CourseKbDocument.source_type == "cms",
                    CourseKbDocument.course_id == draft["course_id"],
                )
            )
            self.assertEqual(documents, 3)
            self.assertEqual(queued, 3)

        with SessionLocal() as db:
            asyncio.run(run_pending_index_jobs(db, limit=50))
            db.commit()
        with SessionLocal() as db:
            pending_cms_jobs = db.scalar(
                select(func.count())
                .select_from(CourseKbIndexJob)
                .join(CourseKbDocument, CourseKbDocument.id == CourseKbIndexJob.document_id)
                .where(
                    CourseKbDocument.source_type == "cms",
                    CourseKbDocument.course_id == draft["course_id"],
                    CourseKbIndexJob.status != "succeeded",
                )
            )
        self.assertEqual(pending_cms_jobs, 0)

        with self._admin_client() as client:
            rag_ready = client.get(
                f"/api/admin/courses/{draft['course_id']}/versions/{draft['version_number']}/rag-status"
            )
            self.assertEqual(rag_ready.status_code, 200, rag_ready.text)
            self.assertEqual(rag_ready.json()["status"], "ready")
            self.assertEqual(rag_ready.json()["succeeded_job_count"], 3)

        with TestClient(app) as learner:
            otp = learner.post("/api/auth/otp/request", json={"phone": "09121112223"})
            self.assertEqual(otp.status_code, 200, otp.text)
            login = learner.post(
                "/api/auth/otp/verify",
                json={"phone": "09121112223", "code": otp.json()["mock_code"], "display_name": "CMS learner"},
            )
            self.assertEqual(login.status_code, 200, login.text)
            profile = learner.patch(
                "/api/me/profile",
                json={
                    "work_or_study_field": "product",
                    "education_level": "bachelor",
                    "learning_goal_interests": "user research",
                    "ai_familiarity_level": "beginner",
                    "daily_learning_time_text": "30 minutes",
                    "daily_learning_minutes": 30,
                    "preferred_career_path": "product manager",
                    "referral_source": "test",
                },
            )
            self.assertEqual(profile.status_code, 200, profile.text)
            enrollment = learner.post(f"/api/courses/{available['user-research-product']['id']}/enroll")
            self.assertEqual(enrollment.status_code, 200, enrollment.text)
            enrollment_id = enrollment.json()["id"]
            coach = learner.post(
                f"/api/learning/enrollments/{enrollment_id}/coach/messages",
                json={"message": "How should I start user research?", "stage_number": 1},
            )
            self.assertEqual(coach.status_code, 200, coach.text)
            self.assertTrue(coach.json()["grounded"])
            self.assertTrue(coach.json()["citations"])
            self.assertIn("User research for product", coach.json()["citations"][0]["title"])

    def test_admin_can_deactivate_soft_delete_and_restore_a_course(self) -> None:
        brief = {**COURSE_BRIEF, "title": "Course lifecycle", "slug": "course-lifecycle"}
        with self._admin_client() as client:
            draft = client.post("/api/admin/courses", json=brief).json()
            generated = client.post(
                f"/api/admin/courses/{draft['course_id']}/versions/1/generate"
            )
            self.assertEqual(generated.status_code, 200, generated.text)
            published = client.post(
                f"/api/admin/courses/{draft['course_id']}/versions/1/publish"
            )
            self.assertEqual(published.status_code, 200, published.text)
            course_id = draft["course_id"]
            version_number = draft["version_number"]

            deactivated = client.post(
                f"/api/admin/courses/{course_id}/versions/{version_number}/deactivate"
            )
            self.assertEqual(deactivated.status_code, 200, deactivated.text)
            self.assertEqual(deactivated.json()["course_status"], "inactive")
            self.assertNotIn(
                "course-lifecycle",
                {course["slug"] for course in client.get("/api/courses").json()},
            )

            reactivated = client.post(
                f"/api/admin/courses/{course_id}/versions/{version_number}/reactivate"
            )
            self.assertEqual(reactivated.status_code, 200, reactivated.text)
            self.assertEqual(reactivated.json()["course_status"], "published")

            deleted = client.post(
                f"/api/admin/courses/{course_id}/versions/{version_number}/soft-delete"
            )
            self.assertEqual(deleted.status_code, 200, deleted.text)
            self.assertEqual(deleted.json()["course_status"], "deleted")
            self.assertNotIn(
                "course-lifecycle",
                {course["slug"] for course in client.get("/api/courses").json()},
            )

            restored = client.post(
                f"/api/admin/courses/{course_id}/versions/{version_number}/restore"
            )
            self.assertEqual(restored.status_code, 200, restored.text)
            self.assertEqual(restored.json()["course_status"], "published")
            self.assertIn(
                "course-lifecycle",
                {course["slug"] for course in client.get("/api/courses").json()},
            )

    def test_published_course_is_edited_through_an_isolated_revision(self) -> None:
        revision_brief = {**COURSE_BRIEF, "title": "Revision source course", "slug": "revision-source-course"}
        with self._admin_client() as client:
            draft = client.post("/api/admin/courses", json=revision_brief).json()
            client.post(f"/api/admin/courses/{draft['course_id']}/versions/1/generate")
            published = client.post(f"/api/admin/courses/{draft['course_id']}/versions/1/publish")
            self.assertEqual(published.status_code, 200, published.text)
            source = published.json()["course"]

            revision = client.post(f"/api/admin/courses/{source['course_id']}/revisions")
            self.assertEqual(revision.status_code, 201, revision.text)
            revision_body = revision.json()
            self.assertEqual(revision_body["version_number"], 2)
            self.assertEqual(revision_body["status"], "draft")
            self.assertEqual(len(revision_body["modules"]), 3)
            self.assertTrue(all(module["status"] == "draft" for module in revision_body["modules"]))

            revision_stage = revision_body["modules"][0]["stages"][0]
            edited = client.patch(
                f"/api/admin/courses/{source['course_id']}/versions/2/stages/{revision_stage['id']}",
                json={"title": "Revision-only title", "content": revision_stage["content"]},
            )
            self.assertEqual(edited.status_code, 200, edited.text)
            original = client.get(f"/api/admin/courses/{source['course_id']}/versions/1")
            self.assertEqual(original.status_code, 200, original.text)
            self.assertNotEqual(original.json()["modules"][0]["stages"][0]["title"], "Revision-only title")

            renamed = client.patch(
                f"/api/admin/courses/{source['course_id']}/versions/2/brief",
                json={"title": "Renamed revision course", "domain": "revision domain"},
            )
            self.assertEqual(renamed.status_code, 200, renamed.text)
            self.assertEqual(renamed.json()["generation_status"], "needs_regeneration")
            regenerated = client.post(
                f"/api/admin/courses/{source['course_id']}/versions/2/generate"
            )
            self.assertEqual(regenerated.status_code, 200, regenerated.text)
            republished = client.post(f"/api/admin/courses/{source['course_id']}/versions/2/publish")
            self.assertEqual(republished.status_code, 200, republished.text)

            latest = {
                course["slug"]: course for course in client.get("/api/courses").json()
            }["revision-source-course"]
            self.assertEqual(latest["title"], "Renamed revision course")
            self.assertEqual(latest["domain"], "revision domain")
            original_after_publish = client.get(f"/api/admin/courses/{source['course_id']}/versions/1")
            self.assertEqual(original_after_publish.status_code, 200, original_after_publish.text)
            self.assertEqual(original_after_publish.json()["course_title"], "Revision source course")

        with SessionLocal() as db:
            version_two_id = republished.json()["course"]["id"]
            document_titles = db.scalars(
                select(CourseKbDocument.title)
                .where(CourseKbDocument.course_version_id == version_two_id)
                .order_by(CourseKbDocument.id)
            ).all()
            exam = db.scalar(
                select(Exam).where(Exam.course_version_id == version_two_id).limit(1)
            )
            self.assertTrue(document_titles)
            self.assertTrue(all(title.startswith("Renamed revision course | ") for title in document_titles))
            self.assertIsNotNone(exam)
            self.assertEqual(exam.title, "آزمون نهایی Renamed revision course")


if __name__ == "__main__":
    unittest.main()
