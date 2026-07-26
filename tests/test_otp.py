import unittest

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests._env import setup_test_environment

setup_test_environment()

from src.config import get_settings
from src.db import Base, SessionLocal, engine
from src.main import app
from src.models import PhoneOtpCode, User


class OtpFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    def setUp(self) -> None:
        get_settings.cache_clear()

    def test_mock_otp_request_and_verify_creates_phone_user(self) -> None:
        with TestClient(app) as client:
            request_response = client.post("/api/auth/otp/request", json={"phone": "09123456789"})
            self.assertEqual(request_response.status_code, 200)
            request_data = request_response.json()
            self.assertEqual(request_data["phone"], "09123456789")
            self.assertEqual(request_data["provider"], "mock")
            self.assertRegex(request_data["mock_code"], r"^\d{6}$")

            with SessionLocal() as db:
                otp = db.scalars(select(PhoneOtpCode).where(PhoneOtpCode.phone == "09123456789")).one()
                self.assertNotEqual(otp.code_hash, request_data["mock_code"])

            verify_response = client.post(
                "/api/auth/otp/verify",
                json={"phone": "09123456789", "code": request_data["mock_code"]},
            )

        self.assertEqual(verify_response.status_code, 200)
        verify_data = verify_response.json()
        self.assertEqual(verify_data["username"], "09123456789")
        self.assertEqual(verify_data["redirect_url"], "/app/")

        with SessionLocal() as db:
            user = db.scalars(select(User).where(User.username == "09123456789")).one()
            otp = db.scalars(select(PhoneOtpCode).where(PhoneOtpCode.phone == "09123456789")).one()
            self.assertEqual(user.id, verify_data["user_id"])
            self.assertIsNotNone(otp.consumed_at)

    def test_wrong_or_reused_otp_is_rejected(self) -> None:
        with TestClient(app) as client:
            request_response = client.post("/api/auth/otp/request", json={"phone": "09122223333"})
            code = request_response.json()["mock_code"]

            wrong_response = client.post(
                "/api/auth/otp/verify",
                json={"phone": "09122223333", "code": "000000"},
            )
            self.assertEqual(wrong_response.status_code, 401)

            first_verify = client.post(
                "/api/auth/otp/verify",
                json={"phone": "09122223333", "code": code},
            )
            self.assertEqual(first_verify.status_code, 200)

            reused_response = client.post(
                "/api/auth/otp/verify",
                json={"phone": "09122223333", "code": code},
            )
            self.assertEqual(reused_response.status_code, 401)
