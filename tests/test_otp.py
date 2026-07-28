import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests._env import setup_test_environment

setup_test_environment()

from src.config import get_settings
from src.db import Base, SessionLocal, engine
from src.main import app
from src.models import PhoneOtpCode, User, UserProfile, UserSession
from src.services.otp import OtpError, _send_smsir_code


def request_and_verify(client: TestClient, phone: str, display_name: str = "Shayan") -> dict:
    request_response = client.post("/api/auth/otp/request", json={"phone": phone})
    if request_response.status_code != 200:
        raise AssertionError(request_response.text)
    code = request_response.json()["mock_code"]
    verify_response = client.post(
        "/api/auth/otp/verify",
        json={"phone": phone, "code": code, "display_name": display_name},
    )
    if verify_response.status_code != 200:
        raise AssertionError(verify_response.text)
    return verify_response.json()


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

    def test_otp_creates_canonical_user_and_http_only_session(self) -> None:
        with TestClient(app) as client:
            request_response = client.post("/api/auth/otp/request", json={"phone": "09123456789"})
            request_data = request_response.json()

            self.assertEqual(request_response.status_code, 200)
            self.assertEqual(request_data["provider"], "mock")
            self.assertRegex(request_data["mock_code"], r"^\d{6}$")

            with SessionLocal() as db:
                self.assertIsNone(
                    db.scalars(select(User).where(User.phone == "09123456789")).first()
                )

            verify_response = client.post(
                "/api/auth/otp/verify",
                json={
                    "phone": "09123456789",
                    "code": request_data["mock_code"],
                    "display_name": "Shayan",
                },
            )
            me_response = client.get("/api/me")
            profile_response = client.get("/api/me/profile")

        self.assertEqual(verify_response.status_code, 200)
        self.assertEqual(verify_response.json()["display_name"], "Shayan")
        self.assertIn("HttpOnly", verify_response.headers["set-cookie"])
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()["phone"], "09123456789")
        self.assertEqual(profile_response.status_code, 200)
        self.assertFalse(profile_response.json()["completed"])

        with SessionLocal() as db:
            user = db.scalars(select(User).where(User.phone == "09123456789")).one()
            otp = db.scalars(select(PhoneOtpCode).where(PhoneOtpCode.phone == user.phone)).one()
            sessions = db.scalars(select(UserSession).where(UserSession.user_id == user.id)).all()

            self.assertEqual(user.display_name, "Shayan")
            self.assertEqual(user.phone, "09123456789")
            self.assertIsNotNone(user.phone_verified_at)
            self.assertIsNone(db.get(UserProfile, user.id))
            self.assertIsNotNone(otp.consumed_at)
            self.assertEqual(len(sessions), 1)
            self.assertEqual(len(sessions[0].token_hash), 64)

    def test_repeat_login_keeps_one_user_identity(self) -> None:
        phone = "09123334444"
        with TestClient(app) as first_client:
            first_login = request_and_verify(first_client, phone, "First name")
        with TestClient(app) as second_client:
            second_login = request_and_verify(second_client, phone, "Updated name")

        self.assertEqual(first_login["user_id"], second_login["user_id"])
        with SessionLocal() as db:
            users = db.scalars(select(User).where(User.phone == phone)).all()
            sessions = db.scalars(
                select(UserSession).where(UserSession.user_id == first_login["user_id"])
            ).all()
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].display_name, "Updated name")
        self.assertEqual(len(sessions), 2)

    def test_wrong_or_reused_otp_is_rejected(self) -> None:
        with TestClient(app) as client:
            request_response = client.post("/api/auth/otp/request", json={"phone": "09122223333"})
            code = request_response.json()["mock_code"]

            wrong_response = client.post(
                "/api/auth/otp/verify",
                json={"phone": "09122223333", "code": "000000", "display_name": "User"},
            )
            first_verify = client.post(
                "/api/auth/otp/verify",
                json={"phone": "09122223333", "code": code, "display_name": "User"},
            )
            reused_response = client.post(
                "/api/auth/otp/verify",
                json={"phone": "09122223333", "code": code, "display_name": "User"},
            )

        self.assertEqual(wrong_response.status_code, 401)
        self.assertEqual(first_verify.status_code, 200)
        self.assertEqual(reused_response.status_code, 401)

    def test_soft_delete_keeps_user_and_revokes_login(self) -> None:
        with TestClient(app) as user_client:
            login = request_and_verify(user_client, "09125556666", "Soft delete")
            user_id = login["user_id"]

            with TestClient(app) as admin_client:
                login_response = admin_client.post(
                    "/api/admin/login",
                    json={
                        "username": "zito_admin",
                        "password": "local-test-admin-password",
                    },
                )
                self.assertEqual(login_response.status_code, 200)
                delete_response = admin_client.delete(f"/api/admin/users/{user_id}")
                self.assertEqual(delete_response.status_code, 200)

            self.assertEqual(user_client.get("/api/me").status_code, 401)

        with SessionLocal() as db:
            user = db.get(User, user_id)
            sessions = db.scalars(select(UserSession).where(UserSession.user_id == user_id)).all()
            self.assertIsNotNone(user)
            self.assertIsNotNone(user.deleted_at)
            self.assertTrue(all(session.revoked_at is not None for session in sessions))


class FakeSmsIrPost:
    next_status_code = 200
    next_body = '{"status":1,"message":"ok","data":{"messageId":89545112,"cost":1.0}}'
    last_request: dict | None = None

    @classmethod
    def post(cls, url: str, payload: dict, headers: dict, timeout_seconds: int):
        cls.last_request = {
            "url": url,
            "payload": payload,
            "headers": headers,
            "timeout_seconds": timeout_seconds,
        }
        return cls.next_status_code, cls.next_body


class SmsIrAdapterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.previous_env = {
            key: os.environ.get(key)
            for key in [
                "OTP_MOCK",
                "SMSIR_API_URL",
                "SMSIR_API_KEY",
                "SMSIR_TEMPLATE_ID",
                "SMSIR_CODE_PARAMETER",
            ]
        }
        os.environ["OTP_MOCK"] = "false"
        os.environ["SMSIR_API_URL"] = "https://api.sms.ir/v1"
        os.environ["SMSIR_API_KEY"] = "test-smsir-key"
        os.environ["SMSIR_TEMPLATE_ID"] = "123456"
        os.environ["SMSIR_CODE_PARAMETER"] = "Code"
        get_settings.cache_clear()

    def tearDown(self) -> None:
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()

    async def test_smsir_adapter_uses_verify_contract(self) -> None:
        FakeSmsIrPost.next_status_code = 200
        FakeSmsIrPost.next_body = '{"status":1,"message":"ok","data":{"messageId":1}}'
        FakeSmsIrPost.last_request = None

        with patch("src.services.otp._post_smsir_verify", FakeSmsIrPost.post):
            await _send_smsir_code("09123456789", "123456")

        request = FakeSmsIrPost.last_request
        self.assertIsNotNone(request)
        self.assertEqual(request["url"], "https://api.sms.ir/v1/send/verify")
        self.assertEqual(request["headers"]["X-API-KEY"], "test-smsir-key")
        self.assertEqual(
            request["payload"],
            {
                "mobile": "09123456789",
                "templateId": 123456,
                "parameters": [{"name": "Code", "value": "123456"}],
            },
        )

    async def test_smsir_adapter_rejects_logical_error_response(self) -> None:
        FakeSmsIrPost.next_status_code = 200
        FakeSmsIrPost.next_body = '{"status":113,"message":"template not found"}'

        with patch("src.services.otp._post_smsir_verify", FakeSmsIrPost.post):
            with self.assertRaises(OtpError):
                await _send_smsir_code("09123456789", "123456")

    async def test_smsir_adapter_rejects_non_ascii_api_key_placeholder(self) -> None:
        os.environ["SMSIR_API_KEY"] = "non-ascii-placeholder-\u06a9\u0644\u06cc\u062f"
        get_settings.cache_clear()

        with patch("src.services.otp._post_smsir_verify", FakeSmsIrPost.post):
            with self.assertRaisesRegex(OtpError, "SMSIR_API_KEY"):
                await _send_smsir_code("09123456789", "123456")
