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
from src.models import PhoneOtpCode, User, UserProfileV2
from src.services.otp import OtpError, _send_smsir_code


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
                user_before_verify = db.scalars(select(User).where(User.phone == "09123456789")).first()
                self.assertIsNone(user_before_verify)

            verify_response = client.post(
                "/api/auth/otp/verify",
                json={"phone": "09123456789", "code": request_data["mock_code"], "full_name": "درخت"},
            )
            profile_response = client.get(f"/api/profile/{verify_response.json()['user_id']}")

        self.assertEqual(verify_response.status_code, 200)
        verify_data = verify_response.json()
        self.assertEqual(verify_data["phone"], "09123456789")
        self.assertEqual(verify_data["username"], "درخت")
        self.assertEqual(verify_data["redirect_url"], "/app/")
        self.assertEqual(profile_response.status_code, 200)
        self.assertFalse(profile_response.json()["completed"])
        self.assertEqual(profile_response.json()["full_name"], "درخت")

        with SessionLocal() as db:
            user = db.scalars(select(User).where(User.phone == "09123456789")).one()
            otp = db.scalars(select(PhoneOtpCode).where(PhoneOtpCode.phone == "09123456789")).one()
            phase2_profile = db.scalars(select(UserProfileV2).where(UserProfileV2.user_id == user.id)).first()
            self.assertEqual(user.id, verify_data["user_id"])
            self.assertEqual(user.full_name, "درخت")
            self.assertEqual(user.username, "درخت")
            self.assertIsNone(phase2_profile)
            self.assertIsNotNone(otp.consumed_at)

        with TestClient(app) as client:
            next_request = client.post("/api/auth/otp/request", json={"phone": "09123456789"})
            next_verify = client.post(
                "/api/auth/otp/verify",
                json={"phone": "09123456789", "code": next_request.json()["mock_code"], "full_name": "درخت"},
            )

        self.assertEqual(next_verify.status_code, 200)
        self.assertEqual(next_verify.json()["user_id"], verify_data["user_id"])

        with SessionLocal() as db:
            users = db.scalars(select(User).where(User.phone == "09123456789")).all()
            self.assertEqual(len(users), 1)

    def test_legacy_phone_login_without_otp_is_not_available(self) -> None:
        with TestClient(app) as client:
            response = client.post("/api/auth/phone", json={"phone": "09121112233"})

        self.assertEqual(response.status_code, 404)

    def test_otp_profile_and_repeat_login_keep_one_user_identity(self) -> None:
        phone = "09123334444"
        profile_payload = {
            "full_name": "شایان علیمی",
            "work_domain": "روانشناسی و هوش مصنوعی",
            "referral_source": "دوستان",
            "daily_study_minutes": 30,
        }

        with TestClient(app) as client:
            first_request = client.post("/api/auth/otp/request", json={"phone": phone}).json()
            first_login = client.post(
                "/api/auth/otp/verify",
                json={"phone": phone, "code": first_request["mock_code"], "full_name": profile_payload["full_name"]},
            )
            user_id = first_login.json()["user_id"]
            profile_response = client.post(f"/api/profile/{user_id}", json=profile_payload)

            second_request = client.post("/api/auth/otp/request", json={"phone": phone}).json()
            second_login = client.post(
                "/api/auth/otp/verify",
                json={"phone": phone, "code": second_request["mock_code"], "full_name": profile_payload["full_name"]},
            )

        self.assertEqual(first_login.status_code, 200)
        self.assertEqual(profile_response.status_code, 200)
        self.assertEqual(second_login.status_code, 200)
        self.assertEqual(second_login.json()["user_id"], user_id)
        self.assertEqual(second_login.json()["username"], "شایان علیمی")

        with SessionLocal() as db:
            users = db.scalars(select(User).where(User.phone == phone)).all()
            profile = db.scalars(select(UserProfileV2).where(UserProfileV2.user_id == user_id)).one()

        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].full_name, "شایان علیمی")
        self.assertEqual(users[0].username, "شایان علیمی")
        self.assertEqual(users[0].profession, "روانشناسی و هوش مصنوعی")
        self.assertEqual(profile.daily_study_minutes, 30)

    def test_wrong_or_reused_otp_is_rejected(self) -> None:
        with TestClient(app) as client:
            request_response = client.post("/api/auth/otp/request", json={"phone": "09122223333"})
            code = request_response.json()["mock_code"]

            wrong_response = client.post(
                "/api/auth/otp/verify",
                json={"phone": "09122223333", "code": "000000", "full_name": "کاربر"},
            )
            self.assertEqual(wrong_response.status_code, 401)

            first_verify = client.post(
                "/api/auth/otp/verify",
                json={"phone": "09122223333", "code": code, "full_name": "کاربر"},
            )
            self.assertEqual(first_verify.status_code, 200)

            reused_response = client.post(
                "/api/auth/otp/verify",
                json={"phone": "09122223333", "code": code, "full_name": "کاربر"},
            )
            self.assertEqual(reused_response.status_code, 401)


class FakeSmsIrPost:
    next_status_code = 200
    next_body = '{"status":1,"message":"موفق","data":{"messageId":89545112,"cost":1.0}}'
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
        self.previous_env = {key: os.environ.get(key) for key in [
            "OTP_MOCK",
            "SMSIR_API_URL",
            "SMSIR_API_KEY",
            "SMSIR_TEMPLATE_ID",
            "SMSIR_CODE_PARAMETER",
        ]}
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
        FakeSmsIrPost.next_body = '{"status":1,"message":"موفق","data":{"messageId":89545112,"cost":1.0}}'
        FakeSmsIrPost.last_request = None

        with patch("src.services.otp._post_smsir_verify", FakeSmsIrPost.post):
            await _send_smsir_code("09123456789", "123456")

        request = FakeSmsIrPost.last_request
        self.assertIsNotNone(request)
        self.assertEqual(request["url"], "https://api.sms.ir/v1/send/verify")
        self.assertEqual(request["headers"]["X-API-KEY"], "test-smsir-key")
        self.assertEqual(request["headers"]["Accept"], "text/plain")
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
        FakeSmsIrPost.next_body = '{"status":113,"message":"قالب یافت نشد"}'

        with patch("src.services.otp._post_smsir_verify", FakeSmsIrPost.post):
            with self.assertRaises(OtpError):
                await _send_smsir_code("09123456789", "123456")

    async def test_smsir_adapter_rejects_non_ascii_api_key_placeholder(self) -> None:
        os.environ["SMSIR_API_KEY"] = "کلید واقعی sms.ir"
        get_settings.cache_clear()

        with patch("src.services.otp._post_smsir_verify", FakeSmsIrPost.post):
            with self.assertRaisesRegex(OtpError, "SMSIR_API_KEY"):
                await _send_smsir_code("09123456789", "123456")
