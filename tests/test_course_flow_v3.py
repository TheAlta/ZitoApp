import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests._env import setup_test_environment

setup_test_environment()

from src.db import Base, SessionLocal, engine
from src.main import app
from src.models import UserModuleStageProgress
from src.seed import seed_defaults
from src.services.rag import run_pending_index_jobs


PROFILE_PAYLOAD = {
    "work_or_study_field": "طراحی محصول",
    "education_level": "کارشناسی",
    "learning_goal_interests": "ساخت عادت یادگیری",
    "ai_familiarity_level": "تازه‌کار",
    "daily_learning_minutes": 25,
    "preferred_career_path": "مدیر محصول",
    "referral_source": "دوست",
}


def login_and_enroll(client: TestClient, phone: str) -> int:
    otp = client.post("/api/auth/otp/request", json={"phone": phone})
    login = client.post(
        "/api/auth/otp/verify",
        json={
            "phone": phone,
            "code": otp.json()["mock_code"],
            "display_name": "کاربر نمونه",
        },
    )
    if login.status_code != 200:
        raise AssertionError(login.text)
    profile = client.patch("/api/me/profile", json=PROFILE_PAYLOAD)
    if profile.status_code != 200:
        raise AssertionError(profile.text)
    course = client.get("/api/courses").json()[0]
    enrollment = client.post(f"/api/courses/{course['id']}/enroll")
    if enrollment.status_code != 200:
        raise AssertionError(enrollment.text)
    return enrollment.json()["id"]


class CourseFlowV3Tests(unittest.TestCase):
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

    def test_course_overview_is_available_before_enrollment(self) -> None:
        with TestClient(app) as client:
            overview = client.get("/api/courses/slug/personal-development-ai")
            page = client.get("/app/courses/personal-development-ai")

        self.assertEqual(overview.status_code, 200)
        body = overview.json()
        self.assertEqual(body["version_number"], 3)
        self.assertEqual(body["module_count"], 5)
        self.assertEqual(body["module_stage_count"], 8)
        self.assertEqual(body["stage_count"], 40)
        self.assertTrue(body["requires_final_exam"])
        self.assertEqual(len(body["modules"]), 5)
        self.assertEqual(body["modules"][0]["stage_count"], 8)
        self.assertEqual(page.status_code, 200)
        self.assertIn('id="startCourse"', page.text)
        self.assertIn("/api/courses/slug/", page.text)

    def test_personalized_example_uses_safe_context_and_is_cached(self) -> None:
        model_response = json.dumps(
            {
                "title": "نمونه برای طراحی محصول",
                "scenario": "یک مسئله کوچک در تیم محصول را برای برنامه‌ریزی بررسی می‌کنی.",
                "application_steps": ["مسئله را روشن کن.", "گزینه‌ها را مقایسه کن."],
                "reflection_question": "این هفته کدام مسئله را بررسی می‌کنی؟",
                "source_numbers": [1],
            },
            ensure_ascii=False,
        )
        with TestClient(app) as client:
            enrollment_id = login_and_enroll(client, "09124440001")
            for stage_number in range(1, 6):
                completed = client.post(
                    f"/api/learning/enrollments/{enrollment_id}/stages/{stage_number}/complete",
                    json={"response": None},
                )
                self.assertEqual(completed.status_code, 200)

            with patch(
                "src.services.personalized_stage.ask_ai",
                new=AsyncMock(return_value=model_response),
            ) as ask_ai_mock:
                first = client.post(
                    f"/api/learning/enrollments/{enrollment_id}/stages/6/personalized-example"
                )
                second = client.post(
                    f"/api/learning/enrollments/{enrollment_id}/stages/6/personalized-example"
                )

        self.assertEqual(first.status_code, 200, first.text)
        self.assertFalse(first.json()["cached"])
        self.assertTrue(first.json()["grounded"])
        self.assertTrue(first.json()["citations"])
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()["cached"])
        self.assertEqual(ask_ai_mock.await_count, 1)
        _, request_body = ask_ai_mock.await_args.args
        request_data = json.loads(request_body)
        self.assertNotIn("phone", request_data["learner_context"])
        self.assertNotIn("referral_source", request_data["learner_context"]["learner"])
        self.assertNotIn("09124440001", request_body)

        with SessionLocal() as db:
            progress = db.scalars(
                select(UserModuleStageProgress)
                .where(UserModuleStageProgress.enrollment_id == enrollment_id)
                .order_by(UserModuleStageProgress.id)
            ).all()[5]
        self.assertEqual(progress.generated_content_json["title"], "نمونه برای طراحی محصول")
        self.assertTrue(progress.generated_content_sources_json)


if __name__ == "__main__":
    unittest.main()
