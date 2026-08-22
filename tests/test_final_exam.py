import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests._env import setup_test_environment

setup_test_environment()

from src.db import Base, SessionLocal, engine
from src.main import app
from src.models import Certificate, UserCourseEnrollment
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


def login_and_enroll(client: TestClient, phone: str) -> int:
    otp_response = client.post("/api/auth/otp/request", json={"phone": phone})
    code = otp_response.json()["mock_code"]
    login_response = client.post(
        "/api/auth/otp/verify",
        json={"phone": phone, "code": code, "display_name": "Final exam learner"},
    )
    if login_response.status_code != 200:
        raise AssertionError(login_response.text)
    if client.patch("/api/me/profile", json=PROFILE_PAYLOAD).status_code != 200:
        raise AssertionError("Could not complete learner profile.")
    course = client.get("/api/courses").json()[0]
    enrollment_response = client.post(f"/api/courses/{course['id']}/enroll")
    if enrollment_response.status_code != 200:
        raise AssertionError(enrollment_response.text)
    return enrollment_response.json()["id"]


def complete_stage(client: TestClient, enrollment_id: int, stage_number: int) -> None:
    response_payload = None
    if stage_number % 8 == 7:
        lesson = client.get(f"/api/learning/enrollments/{enrollment_id}/stages/current")
        quiz = next(
            block for block in lesson.json()["content"]["blocks"] if block.get("kind") == "quiz"
        )
        response_payload = {
            "answers": {item["id"]: item["options"][0] for item in quiz["items"]}
        }
    response = client.post(
        f"/api/learning/enrollments/{enrollment_id}/stages/{stage_number}/complete",
        json={"response": response_payload},
    )
    if response.status_code != 200:
        raise AssertionError(response.text)


def complete_course(client: TestClient, enrollment_id: int) -> None:
    for stage_number in range(1, 41):
        complete_stage(client, enrollment_id, stage_number)


class FinalExamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed_defaults(db)

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    def test_final_exam_is_locked_before_course_completion(self) -> None:
        with TestClient(app) as client:
            enrollment_id = login_and_enroll(client, "09121220001")
            response = client.post(f"/api/learning/enrollments/{enrollment_id}/final-exam/start")

        self.assertEqual(response.status_code, 409)

    def test_passing_exam_issues_one_publicly_verifiable_certificate(self) -> None:
        with TestClient(app) as client:
            enrollment_id = login_and_enroll(client, "09121220002")
            complete_course(client, enrollment_id)

            state = client.get(f"/api/learning/enrollments/{enrollment_id}/final-exam")
            attempt = client.post(f"/api/learning/enrollments/{enrollment_id}/final-exam/start")
            self.assertEqual(state.status_code, 200)
            self.assertEqual(state.json()["status"], "available")
            self.assertEqual(attempt.status_code, 200)
            attempt_payload = attempt.json()
            self.assertEqual(len(attempt_payload["questions"]), 3)
            self.assertNotIn("rubric", attempt_payload["questions"][0])

            answers = {
                question["id"]: "ابتدا هدف را روشن می‌کنم، گزینه‌ها را بررسی می‌کنم و نتیجه را با قضاوت انسانی بازبینی می‌کنم."
                for question in attempt_payload["questions"]
            }
            captured_request = {}

            async def capture_grading_request(system_prompt, user_message, **_kwargs):
                captured_request["system_prompt"] = system_prompt
                captured_request["user_message"] = user_message
                return json.dumps(
                    {
                        "score": 82,
                        "feedback": "پاسخ‌ها کامل و مسئولانه هستند.",
                        "question_feedback": [
                            {"question_id": "final-q-1", "score": 28, "feedback": "پاسخ روشن است."},
                            {"question_id": "final-q-2", "score": 27, "feedback": "مثال عملی دارد."},
                            {"question_id": "final-q-3", "score": 27, "feedback": "کنترل انسانی را پوشش می‌دهد."},
                        ],
                    },
                    ensure_ascii=False,
                )

            with patch("src.services.final_exam.ask_ai", new=capture_grading_request):
                result = client.post(
                    f"/api/learning/enrollments/{enrollment_id}/final-exam/attempts/{attempt_payload['id']}/submit",
                    json={"answers": answers},
                )
            repeated = client.post(
                f"/api/learning/enrollments/{enrollment_id}/final-exam/attempts/{attempt_payload['id']}/submit",
                json={"answers": answers},
            )
            certificate = client.get(f"/api/learning/enrollments/{enrollment_id}/certificate")
            certificate_number = result.json()["certificate"]["certificate_number"]
            verification = client.get(f"/api/certificates/{certificate_number}")

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()["passed"])
        self.assertEqual(result.json()["score"], 82)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.json()["certificate"]["certificate_number"], certificate_number)
        self.assertEqual(certificate.status_code, 200)
        self.assertEqual(verification.status_code, 200)
        self.assertTrue(verification.json()["valid"])
        self.assertNotIn("09121220002", captured_request["user_message"])
        self.assertNotIn("Final exam learner", captured_request["user_message"])
        self.assertNotIn("Product design", captured_request["user_message"])
        self.assertIn("ZITO_FINAL_EXAM_GRADING_V1", captured_request["system_prompt"])
        with SessionLocal() as db:
            enrollment = db.get(UserCourseEnrollment, enrollment_id)
            certificates = db.scalars(
                select(Certificate).where(Certificate.exam_attempt_id == attempt_payload["id"])
            ).all()
        self.assertEqual(enrollment.status, "completed")
        self.assertEqual(len(certificates), 1)

    def test_failed_attempt_can_start_a_new_attempt(self) -> None:
        with TestClient(app) as client:
            enrollment_id = login_and_enroll(client, "09121220003")
            complete_course(client, enrollment_id)
            first_attempt = client.post(
                f"/api/learning/enrollments/{enrollment_id}/final-exam/start"
            ).json()
            failed = client.post(
                f"/api/learning/enrollments/{enrollment_id}/final-exam/attempts/{first_attempt['id']}/submit",
                json={"answers": {question["id"]: "نه" for question in first_attempt["questions"]}},
            )
            second_attempt = client.post(
                f"/api/learning/enrollments/{enrollment_id}/final-exam/start"
            ).json()

        self.assertEqual(failed.status_code, 200)
        self.assertFalse(failed.json()["passed"])
        self.assertEqual(failed.json()["score"], 45)
        self.assertNotEqual(first_attempt["id"], second_attempt["id"])
        self.assertEqual(second_attempt["attempt_number"], 2)

    def test_another_user_cannot_access_an_attempt(self) -> None:
        with TestClient(app) as owner:
            enrollment_id = login_and_enroll(owner, "09121220004")
            complete_course(owner, enrollment_id)
            attempt = owner.post(
                f"/api/learning/enrollments/{enrollment_id}/final-exam/start"
            ).json()

        with TestClient(app) as stranger:
            login_and_enroll(stranger, "09121220005")
            state = stranger.get(f"/api/learning/enrollments/{enrollment_id}/final-exam")
            submit = stranger.post(
                f"/api/learning/enrollments/{enrollment_id}/final-exam/attempts/{attempt['id']}/submit",
                json={"answers": {}},
            )

        self.assertEqual(state.status_code, 404)
        self.assertEqual(submit.status_code, 404)


if __name__ == "__main__":
    unittest.main()
