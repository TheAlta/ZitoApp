import unittest

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests._env import setup_test_environment

setup_test_environment()

from src.db import Base, SessionLocal, engine
from src.main import app
from src.models import Course, CourseVersion, UserCourseEnrollment, UserModuleStageProgress, UserStageProgress
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


def complete_module_stage(client: TestClient, enrollment_id: int, stage_number: int):
    response = None
    if stage_number % 8 == 7:
        lesson = client.get(f"/api/learning/enrollments/{enrollment_id}/stages/current")
        if lesson.status_code != 200:
            raise AssertionError(lesson.text)
        quiz = next(
            block
            for block in lesson.json()["content"]["blocks"]
            if block.get("kind") == "quiz"
        )
        response = {
            "answers": {
                item["id"]: item["options"][0]
                for item in quiz["items"]
            }
        }
    return client.post(
        f"/api/learning/enrollments/{enrollment_id}/stages/{stage_number}/complete",
        json={"response": response},
    )


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

    def test_enrollment_creates_module_scoped_progress_rows(self) -> None:
        with TestClient(app) as client:
            _, enrollment_id = login_and_enroll(client, "09121110001")

        with SessionLocal() as db:
            rows = db.scalars(
                select(UserModuleStageProgress)
                .where(UserModuleStageProgress.enrollment_id == enrollment_id)
                .order_by(UserModuleStageProgress.id)
            ).all()

        self.assertEqual(len(rows), 40)
        self.assertEqual(rows[0].status, "available")
        self.assertTrue(all(row.status == "locked" for row in rows[1:]))

    def test_progress_resumes_and_media_slots_are_empty_but_typed(self) -> None:
        with TestClient(app) as client:
            _, enrollment_id = login_and_enroll(client, "09121110002")
            for stage_number in range(1, 9):
                response = complete_module_stage(client, enrollment_id, stage_number)
                self.assertEqual(response.status_code, 200)

            resumed_path = client.get("/api/learning/enrollments/current")
            current_stage = client.get(
                f"/api/learning/enrollments/{enrollment_id}/stages/current"
            )

        self.assertEqual(resumed_path.json()["current_stage_number"], 9)
        self.assertEqual(resumed_path.json()["progress_percentage"], 20)
        self.assertEqual(current_stage.json()["stage_type"], "learning_path")
        self.assertEqual(current_stage.json()["module_number"], 2)
        self.assertEqual(current_stage.json()["module_stage_number"], 1)
        media_slots = current_stage.json()["content"]["media_slots"]
        self.assertEqual(media_slots[0]["kind"], "video")
        self.assertEqual(media_slots[0]["status"], "empty")
        self.assertIsNone(media_slots[0]["url"])

    def test_complete_all_stages_is_idempotent_and_finishes_at_one_hundred_percent(self) -> None:
        with TestClient(app) as client:
            _, enrollment_id = login_and_enroll(client, "09121110003")
            last_response = None
            for stage_number in range(1, 41):
                last_response = complete_module_stage(client, enrollment_id, stage_number)
                self.assertEqual(last_response.status_code, 200)

            repeated = complete_module_stage(client, enrollment_id, 40)
            completed_stage = client.get(
                f"/api/learning/enrollments/{enrollment_id}/stages/current"
            )

        self.assertFalse(last_response.json()["course_completed"])
        self.assertTrue(last_response.json()["path"]["final_exam_available"])
        self.assertEqual(last_response.json()["progress_percentage"], 100)
        self.assertIsNone(last_response.json()["next_stage_number"])
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.json()["progress_percentage"], 100)
        self.assertFalse(completed_stage.json()["course_completed"])
        self.assertTrue(completed_stage.json()["final_exam_available"])
        self.assertEqual(completed_stage.json()["stage_number"], 40)

        with SessionLocal() as db:
            enrollment = db.get(UserCourseEnrollment, enrollment_id)
            rows = db.scalars(
                select(UserModuleStageProgress).where(
                    UserModuleStageProgress.enrollment_id == enrollment_id,
                    UserModuleStageProgress.status == "completed",
                )
            ).all()
        self.assertEqual(enrollment.status, "awaiting_final_exam")
        self.assertEqual(enrollment.progress_percentage, 100)
        self.assertEqual(len(rows), 40)

    def test_module_assessment_blocks_progress_until_the_learner_passes(self) -> None:
        with TestClient(app) as client:
            _, enrollment_id = login_and_enroll(client, "09121110007")
            for stage_number in range(1, 7):
                self.assertEqual(
                    complete_module_stage(client, enrollment_id, stage_number).status_code,
                    200,
                )

            failed = client.post(
                f"/api/learning/enrollments/{enrollment_id}/stages/7/complete",
                json={"response": None},
            )
            current_after_failure = client.get(
                f"/api/learning/enrollments/{enrollment_id}/stages/current"
            )
            passed = complete_module_stage(client, enrollment_id, 7)

        self.assertEqual(failed.status_code, 200)
        self.assertFalse(failed.json()["stage_completed"])
        self.assertEqual(failed.json()["assessment"]["score"], 0)
        self.assertFalse(failed.json()["assessment"]["passed"])
        self.assertEqual(current_after_failure.json()["stage_number"], 7)
        self.assertEqual(current_after_failure.json()["assessment"]["attempt_count"], 1)
        self.assertEqual(passed.status_code, 200)
        self.assertTrue(passed.json()["stage_completed"])
        self.assertTrue(passed.json()["assessment"]["passed"])
        self.assertEqual(passed.json()["next_stage_number"], 8)

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

    def test_existing_flat_version_one_enrollment_remains_compatible(self) -> None:
        with TestClient(app) as client:
            otp_response = client.post("/api/auth/otp/request", json={"phone": "09121110006"})
            login_response = client.post(
                "/api/auth/otp/verify",
                json={
                    "phone": "09121110006",
                    "code": otp_response.json()["mock_code"],
                    "display_name": "Legacy learner",
                },
            )
            user_id = login_response.json()["user_id"]
            self.assertEqual(client.patch("/api/me/profile", json=PROFILE_PAYLOAD).status_code, 200)

            with SessionLocal() as db:
                course = db.scalars(select(Course).where(Course.slug == "personal-development-ai")).one()
                version_one = db.scalars(
                    select(CourseVersion).where(
                        CourseVersion.course_id == course.id,
                        CourseVersion.version_number == 1,
                    )
                ).one()
                enrollment = UserCourseEnrollment(
                    user_id=user_id,
                    course_id=course.id,
                    course_version_id=version_one.id,
                    status="active",
                    current_stage_number=1,
                    progress_percentage=0,
                )
                db.add(enrollment)
                db.commit()
                enrollment_id = enrollment.id

            path_response = client.get("/api/learning/enrollments/current")
            stage_response = client.get(
                f"/api/learning/enrollments/{enrollment_id}/stages/current"
            )

        self.assertEqual(path_response.status_code, 200)
        self.assertEqual(path_response.json()["total_stage_count"], 20)
        self.assertEqual(path_response.json()["module_count"], 0)
        self.assertEqual(stage_response.json()["stage_type"], "lesson_summary")
        with SessionLocal() as db:
            legacy_rows = db.scalars(
                select(UserStageProgress).where(UserStageProgress.enrollment_id == enrollment_id)
            ).all()
        self.assertEqual(len(legacy_rows), 20)


if __name__ == "__main__":
    unittest.main()
