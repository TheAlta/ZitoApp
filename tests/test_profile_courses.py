import unittest

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests._env import setup_test_environment

setup_test_environment()

from src.config import get_settings
from src.db import Base, SessionLocal, engine
from src.main import app
from src.models import ProfileBuilderAnswer, User, UserCourseEnrollment, UserProfileV2
from src.seed import seed_defaults


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

    def _create_user(self) -> int:
        with SessionLocal() as db:
            user = User(username="09120000000")
            db.add(user)
            db.commit()
            db.refresh(user)
            return user.id

    def test_profile_submit_saves_v2_profile_and_builder_answers(self) -> None:
        user_id = self._create_user()
        payload = {
            "full_name": "امیر مسعود",
            "work_domain": "توسعه فردی",
            "referral_source": "اینستاگرام",
            "daily_study_minutes": 30,
            "learning_goal": "یادگیری کاربردی هوش مصنوعی",
            "experience_level": "مبتدی",
            "preferred_learning_style": "تمرین عملی",
        }

        with TestClient(app) as client:
            response = client.post(f"/api/profile/{user_id}", json=payload)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["completed"])
        self.assertEqual(data["full_name"], "امیر مسعود")
        self.assertEqual(data["daily_study_minutes"], 30)

        with SessionLocal() as db:
            profile = db.scalars(select(UserProfileV2).where(UserProfileV2.user_id == user_id)).one()
            answers = db.scalars(select(ProfileBuilderAnswer).where(ProfileBuilderAnswer.user_id == user_id)).all()
            user = db.get(User, user_id)

        self.assertEqual(profile.work_domain, "توسعه فردی")
        self.assertEqual(user.full_name, "امیر مسعود")
        self.assertEqual(user.profession, "توسعه فردی")
        self.assertEqual(len(answers), 7)

    def test_courses_and_enrollment_use_fake_cms_seed(self) -> None:
        user_id = self._create_user()

        with TestClient(app) as client:
            courses_response = client.get("/api/courses")
            self.assertEqual(courses_response.status_code, 200)
            courses = courses_response.json()
            course = next(item for item in courses if item["slug"] == "personal-development-ai")
            self.assertEqual(course["stage_count"], 20)

            first_enroll = client.post(f"/api/courses/{course['id']}/enroll", params={"user_id": user_id})
            second_enroll = client.post(f"/api/courses/{course['id']}/enroll", params={"user_id": user_id})

        self.assertEqual(first_enroll.status_code, 200)
        self.assertEqual(second_enroll.status_code, 200)
        self.assertEqual(first_enroll.json()["id"], second_enroll.json()["id"])

        with SessionLocal() as db:
            enrollments = db.scalars(
                select(UserCourseEnrollment).where(UserCourseEnrollment.user_id == user_id)
            ).all()

        self.assertEqual(len(enrollments), 1)
        self.assertEqual(enrollments[0].current_stage_number, 1)
        self.assertEqual(enrollments[0].progress_percentage, 0)
