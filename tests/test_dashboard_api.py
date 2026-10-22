"""Read endpoints added for the redesigned dashboard, CMS and coach."""

import asyncio
import unittest

from fastapi.testclient import TestClient

from tests._env import setup_test_environment

setup_test_environment()

from src.config import get_settings
from src.db import Base, SessionLocal, engine
from src.main import app
from src.seed import seed_defaults
from src.services.rag import run_pending_index_jobs
from tests.test_course_flow_v3 import PROFILE_PAYLOAD, login_and_enroll


def admin_login(client: TestClient) -> None:
    settings = get_settings()
    response = client.post("/api/admin/login", json={"username": settings.admin_username, "password": settings.admin_password})
    if response.status_code != 200:
        raise AssertionError(response.text)


class DashboardApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed_defaults(db)
            asyncio.run(run_pending_index_jobs(db, limit=50))
            db.commit()

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    def test_overview_lists_enrollments_progress_and_activity(self) -> None:
        with TestClient(app) as client:
            enrollment_id = login_and_enroll(client, "09125550101")
            stage = client.get(f"/api/learning/enrollments/{enrollment_id}/stages/current").json()
            done = client.post(f"/api/learning/enrollments/{enrollment_id}/stages/{stage['stage_number']}/complete", json={})
            self.assertEqual(done.status_code, 200, done.text)
            overview = client.get("/api/learning/overview")
            me = client.get("/api/me").json()

        self.assertEqual(overview.status_code, 200, overview.text)
        body = overview.json()
        self.assertEqual(len(body["enrollments"]), 1)
        row = body["enrollments"][0]
        self.assertEqual(row["id"], enrollment_id)
        self.assertTrue(row["is_current"])
        self.assertEqual(row["status"], "learning")
        self.assertEqual(row["completed_stage_count"], 1)
        self.assertGreater(row["total_stage_count"], row["completed_stage_count"])
        self.assertGreater(row["module_count"], 0)
        self.assertEqual(body["certificates"], [])
        kinds = [item["kind"] for item in body["activity"]]
        self.assertIn("stage", kinds)
        self.assertIn("start", kinds)
        self.assertIsNotNone(me["created_at"])

    def test_overview_requires_a_learner_session(self) -> None:
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/learning/overview").status_code, 401)

    def test_course_overview_exposes_brief_fields_for_the_catalog(self) -> None:
        with TestClient(app) as client:
            slug = client.get("/api/courses").json()[0]["slug"]
            body = client.get(f"/api/courses/slug/{slug}").json()
        for key in ("level", "target_group", "estimated_learning_hours"):
            self.assertIn(key, body)
        self.assertIn("tag", body["modules"][0])

    def test_admin_me_stats_and_user_courses(self) -> None:
        with TestClient(app) as client:
            login_and_enroll(client, "09125550102")
            user_id = client.get("/api/me").json()["id"]
            client.post("/api/auth/logout")
            admin_login(client)
            me = client.get("/api/admin/me").json()
            stats = client.get("/api/admin/stats").json()
            detail = client.get(f"/api/admin/users/{user_id}").json()
            versions = client.get("/api/admin/courses").json()

        self.assertEqual(me["username"], get_settings().admin_username)
        self.assertGreaterEqual(stats["enrollment_count"], 1)
        self.assertIn("average_progress", stats)
        self.assertEqual(len(detail["course_titles"]), 1)
        self.assertIn("published_at", versions[0])
        self.assertIn("created_at", versions[0])

    def test_generation_reports_progress_to_the_studio(self) -> None:
        with TestClient(app) as client:
            admin_login(client)
            draft = client.post(
                "/api/admin/courses",
                json={
                    "title": "دوره‌ی آزمایشی پیشرفت",
                    "topic": "مذاکره",
                    "goal": "مذاکره‌ی بهتر",
                    "duration": "۱ هفته",
                    "audience": "کارشناسان",
                    "target_group": "کارشناسان فروش",
                    "level": "مقدماتی",
                    "module_count": 2,
                    "estimated_learning_hours": 2,
                    "requires_final_exam": False,
                },
            ).json()
            base = f"/api/admin/courses/{draft['course_id']}/versions/{draft['version_number']}"
            started = client.post(f"{base}/generate")
            self.assertEqual(started.status_code, 202, started.text)
            version = client.get(base).json()

        progress = version["generation_progress"]
        self.assertEqual(version["generation_status"], "generated")
        self.assertEqual(progress["done"], progress["total"])
        texts = [item["text"] for item in progress["log"]]
        self.assertTrue(texts[0].startswith("درخواست تولید"))
        self.assertTrue(any(text.startswith("سرفصل 2") for text in texts))
        self.assertTrue(texts[-1].startswith("پیش‌نویس کامل شد"))

    def test_profile_payload_constant_is_shared(self) -> None:
        self.assertIn("work_or_study_field", PROFILE_PAYLOAD)


if __name__ == "__main__":
    unittest.main()
