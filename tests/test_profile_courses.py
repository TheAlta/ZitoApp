import unittest

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests._env import setup_test_environment

setup_test_environment()

from src.config import get_settings
from src.db import Base, SessionLocal, engine
from src.main import app
from src.models import User, UserCourseEnrollment, UserProfile
from src.seed import seed_defaults


PROFILE_PAYLOAD = {
    "work_or_study_field": "Software engineering",
    "education_level": "Bachelor",
    "learning_goal_interests": "Practical AI",
    "ai_familiarity_level": "Beginner",
    "daily_learning_minutes": 30,
    "preferred_career_path": "AI product engineer",
    "referral_source": "Friend",
}


def login(client: TestClient, phone: str, display_name: str = "Learner") -> int:
    request_response = client.post("/api/auth/otp/request", json={"phone": phone})
    code = request_response.json()["mock_code"]
    verify_response = client.post(
        "/api/auth/otp/verify",
        json={"phone": phone, "code": code, "display_name": display_name},
    )
    if verify_response.status_code != 200:
        raise AssertionError(verify_response.text)
    return verify_response.json()["user_id"]


class ProfileAndCourseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed_defaults(db)

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    def setUp(self) -> None:
        get_settings.cache_clear()

    def test_profile_answers_are_persisted_incrementally_in_one_to_one_row(self) -> None:
        with TestClient(app) as client:
            user_id = login(client, "09120000001", "Single name")
            first_response = client.patch(
                "/api/me/profile",
                json={"work_or_study_field": PROFILE_PAYLOAD["work_or_study_field"]},
            )
            self.assertEqual(first_response.status_code, 200)
            self.assertFalse(first_response.json()["completed"])

            for field, value in list(PROFILE_PAYLOAD.items())[1:]:
                response = client.patch("/api/me/profile", json={field: value})
                self.assertEqual(response.status_code, 200)

            profile_response = client.get("/api/me/profile")

        self.assertTrue(profile_response.json()["completed"])
        self.assertEqual(profile_response.json()["display_name"], "Single name")
        self.assertEqual(profile_response.json()["daily_learning_minutes"], 30)

        with SessionLocal() as db:
            profile = db.get(UserProfile, user_id)
            user = db.get(User, user_id)
            profiles = db.scalars(select(UserProfile).where(UserProfile.user_id == user_id)).all()

        self.assertEqual(len(profiles), 1)
        self.assertEqual(profile.work_or_study_field, "Software engineering")
        self.assertEqual(profile.education_level, "Bachelor")
        self.assertEqual(profile.learning_goal_interests, "Practical AI")
        self.assertEqual(profile.ai_familiarity_level, "Beginner")
        self.assertEqual(profile.daily_learning_minutes, 30)
        self.assertEqual(profile.preferred_career_path, "AI product engineer")
        self.assertEqual(profile.referral_source, "Friend")
        self.assertIsNotNone(profile.completed_at)
        self.assertEqual(user.display_name, "Single name")
        self.assertEqual(user.phone, "09120000001")

    def test_profile_and_enrollment_require_authenticated_owner(self) -> None:
        with TestClient(app) as anonymous:
            self.assertEqual(anonymous.get("/api/me/profile").status_code, 401)
            self.assertEqual(anonymous.patch("/api/me/profile", json=PROFILE_PAYLOAD).status_code, 401)

        with TestClient(app) as client:
            login(client, "09120000002")
            courses = client.get("/api/courses").json()
            course = next(item for item in courses if item["slug"] == "personal-development-ai")
            incomplete_enroll = client.post(f"/api/courses/{course['id']}/enroll")
            self.assertEqual(incomplete_enroll.status_code, 409)
            profile_response = client.patch("/api/me/profile", json=PROFILE_PAYLOAD)
            self.assertEqual(profile_response.status_code, 200)
            first_enroll = client.post(f"/api/courses/{course['id']}/enroll")
            second_enroll = client.post(f"/api/courses/{course['id']}/enroll")

        self.assertEqual(first_enroll.status_code, 200)
        self.assertEqual(second_enroll.status_code, 200)
        self.assertEqual(first_enroll.json()["id"], second_enroll.json()["id"])

        with SessionLocal() as db:
            enrollments = db.scalars(
                select(UserCourseEnrollment).where(
                    UserCourseEnrollment.user_id == first_enroll.json()["user_id"]
                )
            ).all()
        self.assertEqual(len(enrollments), 1)
        self.assertEqual(enrollments[0].current_stage_number, 1)

    def test_temporary_training_uses_course_enrollment_progress(self) -> None:
        with TestClient(app) as client:
            user_id = login(client, "09120000003", "Training learner")
            self.assertEqual(
                client.patch("/api/me/profile", json=PROFILE_PAYLOAD).status_code,
                200,
            )
            course = next(
                item
                for item in client.get("/api/courses").json()
                if item["slug"] == "personal-development-ai"
            )
            self.assertEqual(
                client.post(f"/api/courses/{course['id']}/enroll").status_code,
                200,
            )
            lesson = client.post(f"/api/training/{user_id}/lesson")
            self.assertEqual(lesson.status_code, 200)
            evaluation = client.post(
                f"/api/training/{user_id}/answer",
                json={
                    "lesson": lesson.json()["lesson"],
                    "check_question": lesson.json()["check_question"],
                    "answer_text": (
                        "خروجی هوش مصنوعی را با منبع معتبر و بررسی انسانی کنترل می‌کنم "
                        "تا خطاهای احتمالی وارد تصمیم نهایی نشوند."
                    ),
                },
            )

        self.assertEqual(evaluation.status_code, 200)
        self.assertTrue(evaluation.json()["passed"])
        self.assertEqual(evaluation.json()["percentage"], 5)
        self.assertEqual(evaluation.json()["current_step"], 2)

        with SessionLocal() as db:
            enrollment = db.scalars(
                select(UserCourseEnrollment).where(
                    UserCourseEnrollment.user_id == user_id
                )
            ).one()
        self.assertEqual(enrollment.progress_percentage, 5)
        self.assertEqual(enrollment.current_stage_number, 2)
