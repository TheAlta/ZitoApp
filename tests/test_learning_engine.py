import unittest

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests._env import setup_test_environment

setup_test_environment()

from src.db import Base, SessionLocal, engine
from src.main import app
from src.models import UserCourseEnrollment, UserStageProgress
from src.seed import seed_defaults


PROFILE_PAYLOAD = {
    "work_or_study_field": "Product design",
    "education_level": "Bachelor",
    "learning_goal_interests": "Personal development with AI",
    "ai_familiarity_level": "Beginner",
    "daily_learning_minutes": 25,
    "preferred_career_path": "Product leader",
    "referral_source": "Friend",
}


def login_and_enroll(client: TestClient, phone: str) -> tuple[int, int]:
    otp_response = client.post("/api/auth/otp/request", json={"phone": phone})
    code = otp_response.json()["mock_code"]
    login_response = client.post(
        "/api/auth/otp/verify",
        json={"phone": phone, "code": code, "display_name": "Sprint learner"},
    )
    user_id = login_response.json()["user_id"]
    profile_response = client.patch("/api/me/profile", json=PROFILE_PAYLOAD)
    if profile_response.status_code != 200:
        raise AssertionError(profile_response.text)
    course = client.get("/api/courses").json()[0]
    enrollment_response = client.post(f"/api/courses/{course['id']}/enroll")
    if enrollment_response.status_code != 200:
        raise AssertionError(enrollment_response.text)
    return user_id, enrollment_response.json()["id"]


class LearningEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed_defaults(db)

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    def test_enrollment_creates_exactly_twenty_ordered_progress_rows(self) -> None:
        with TestClient(app) as client:
            _, enrollment_id = login_and_enroll(client, "09121110001")

        with SessionLocal() as db:
            rows = db.scalars(
                select(UserStageProgress)
                .where(UserStageProgress.enrollment_id == enrollment_id)
                .order_by(UserStageProgress.stage_number)
            ).all()

        self.assertEqual([row.stage_number for row in rows], list(range(1, 21)))
        self.assertEqual(rows[0].status, "available")
        self.assertTrue(all(row.status == "locked" for row in rows[1:]))

    def test_progress_resumes_and_media_slots_are_empty_but_typed(self) -> None:
        with TestClient(app) as client:
            _, enrollment_id = login_and_enroll(client, "09121110002")
            for stage_number in range(1, 14):
                response = client.post(
                    f"/api/learning/enrollments/{enrollment_id}/stages/{stage_number}/complete",
                    json={"response": None},
                )
                self.assertEqual(response.status_code, 200)

            resumed_path = client.get("/api/learning/enrollments/current")
            current_stage = client.get(
                f"/api/learning/enrollments/{enrollment_id}/stages/current"
            )

        self.assertEqual(resumed_path.json()["current_stage_number"], 14)
        self.assertEqual(resumed_path.json()["progress_percentage"], 65)
        self.assertEqual(current_stage.json()["stage_type"], "audio_summary")
        media_slots = current_stage.json()["content"]["media_slots"]
        self.assertEqual(media_slots[0]["kind"], "audio")
        self.assertEqual(media_slots[0]["status"], "empty")
        self.assertIsNone(media_slots[0]["url"])

    def test_complete_all_stages_is_idempotent_and_finishes_at_one_hundred_percent(self) -> None:
        with TestClient(app) as client:
            _, enrollment_id = login_and_enroll(client, "09121110003")
            last_response = None
            for stage_number in range(1, 21):
                last_response = client.post(
                    f"/api/learning/enrollments/{enrollment_id}/stages/{stage_number}/complete",
                    json={"response": None},
                )
                self.assertEqual(last_response.status_code, 200)

            repeated = client.post(
                f"/api/learning/enrollments/{enrollment_id}/stages/20/complete",
                json={"response": None},
            )
            completed_stage = client.get(
                f"/api/learning/enrollments/{enrollment_id}/stages/current"
            )

        self.assertTrue(last_response.json()["course_completed"])
        self.assertEqual(last_response.json()["progress_percentage"], 100)
        self.assertIsNone(last_response.json()["next_stage_number"])
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.json()["progress_percentage"], 100)
        self.assertTrue(completed_stage.json()["course_completed"])
        self.assertEqual(completed_stage.json()["stage_number"], 20)

        with SessionLocal() as db:
            enrollment = db.get(UserCourseEnrollment, enrollment_id)
            rows = db.scalars(
                select(UserStageProgress).where(
                    UserStageProgress.enrollment_id == enrollment_id,
                    UserStageProgress.status == "completed",
                )
            ).all()
        self.assertEqual(enrollment.status, "completed")
        self.assertEqual(enrollment.progress_percentage, 100)
        self.assertEqual(len(rows), 20)

    def test_another_user_cannot_read_or_complete_an_enrollment(self) -> None:
        with TestClient(app) as owner:
            _, enrollment_id = login_and_enroll(owner, "09121110004")
        with TestClient(app) as stranger:
            login_and_enroll(stranger, "09121110005")
            path_response = stranger.get(f"/api/learning/enrollments/{enrollment_id}")
            stage_response = stranger.get(
                f"/api/learning/enrollments/{enrollment_id}/stages/current"
            )
            complete_response = stranger.post(
                f"/api/learning/enrollments/{enrollment_id}/stages/1/complete",
                json={"response": None},
            )

        self.assertEqual(path_response.status_code, 404)
        self.assertEqual(stage_response.status_code, 404)
        self.assertEqual(complete_response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
