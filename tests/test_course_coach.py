import asyncio
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests._env import setup_test_environment

setup_test_environment()

from src.db import Base, SessionLocal, engine
from src.main import app
from src.models import CoachMessage, CoachRetrievalEvent, CoachThread, UserCourseEnrollment
from src.seed import seed_defaults
from src.services.rag import run_pending_index_jobs


PROFILE_PAYLOAD = {
    "work_or_study_field": "طراحی محصول",
    "education_level": "کارشناسی",
    "learning_goal_interests": "ساخت عادت یادگیری پایدار",
    "ai_familiarity_level": "تازه‌کار",
    "daily_learning_minutes": 25,
    "preferred_career_path": "مدیر محصول",
    "referral_source": "دوست",
}


def login_and_enroll(client: TestClient, phone: str) -> int:
    otp = client.post("/api/auth/otp/request", json={"phone": phone})
    code = otp.json()["mock_code"]
    login = client.post(
        "/api/auth/otp/verify",
        json={"phone": phone, "code": code, "display_name": "کاربر آزمایشی"},
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


class CourseCoachTests(unittest.TestCase):
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

    def test_coach_uses_course_kb_and_persists_an_audit_trail(self) -> None:
        with TestClient(app) as client:
            enrollment_id = login_and_enroll(client, "09125550101")
            completed = client.post(
                f"/api/learning/enrollments/{enrollment_id}/stages/1/complete",
                json={"response": None},
            )
            self.assertTrue(completed.json()["coaching"]["enabled"])

            reply = client.post(
                f"/api/learning/enrollments/{enrollment_id}/coach/messages",
                json={
                    "message": "چطور هدف یادگیری را به یک اقدام کوچک تبدیل کنم؟",
                    "stage_number": 1,
                },
            )
            history = client.get(
                f"/api/learning/enrollments/{enrollment_id}/coach/messages"
            )

        self.assertEqual(reply.status_code, 200, reply.text)
        body = reply.json()
        self.assertTrue(body["grounded"])
        self.assertTrue(body["citations"])
        self.assertIn("اقدام کوچک", body["answer"])
        self.assertEqual(history.status_code, 200)
        self.assertEqual([item["role"] for item in history.json()["messages"]], ["user", "assistant"])

        with SessionLocal() as db:
            enrollment = db.get(UserCourseEnrollment, enrollment_id)
            thread = db.scalars(select(CoachThread).where(CoachThread.enrollment_id == enrollment_id)).one()
            messages = db.scalars(
                select(CoachMessage).where(CoachMessage.thread_id == thread.id).order_by(CoachMessage.id)
            ).all()
            event = db.scalars(
                select(CoachRetrievalEvent).where(
                    CoachRetrievalEvent.assistant_message_id == messages[-1].id
                )
            ).one()

        self.assertEqual(thread.user_id, enrollment.user_id)
        self.assertEqual(len(messages), 2)
        self.assertTrue(event.grounded)
        self.assertTrue(event.source_chunks_json)
        self.assertNotIn("phone", str(messages[-1].content_json).lower())

    def test_another_user_cannot_access_a_coach_thread(self) -> None:
        with TestClient(app) as owner:
            enrollment_id = login_and_enroll(owner, "09125550102")
        with TestClient(app) as stranger:
            login_and_enroll(stranger, "09125550103")
            history = stranger.get(
                f"/api/learning/enrollments/{enrollment_id}/coach/messages"
            )
            reply = stranger.post(
                f"/api/learning/enrollments/{enrollment_id}/coach/messages",
                json={"message": "یک سوال درباره درس", "stage_number": 1},
            )

        self.assertEqual(history.status_code, 404)
        self.assertEqual(reply.status_code, 404)


if __name__ == "__main__":
    unittest.main()
