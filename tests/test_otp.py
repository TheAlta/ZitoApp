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
from src.models import PhoneOtpCode, User
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


class FakeSmsIrResponse:
    def __init__(self, status_code: int = 200, body: dict | None = None) -> None:
        self.status_code = status_code
        self._body = body or {"status": 1, "message": "موفق", "data": {"messageId": 89545112, "cost": 1.0}}

    def json(self) -> dict:
        return self._body


class FakeSmsIrClient:
    next_response = FakeSmsIrResponse()
    last_request: dict | None = None

    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, json: dict, headers: dict):
        FakeSmsIrClient.last_request = {"url": url, "json": json, "headers": headers}
        return FakeSmsIrClient.next_response


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
        FakeSmsIrClient.next_response = FakeSmsIrResponse()
        FakeSmsIrClient.last_request = None

        with patch("src.services.otp.httpx.AsyncClient", FakeSmsIrClient):
            await _send_smsir_code("09123456789", "123456")

        request = FakeSmsIrClient.last_request
        self.assertIsNotNone(request)
        self.assertEqual(request["url"], "https://api.sms.ir/v1/send/verify")
        self.assertEqual(request["headers"]["X-API-KEY"], "test-smsir-key")
        self.assertEqual(request["headers"]["Accept"], "text/plain")
        self.assertEqual(
            request["json"],
            {
                "mobile": "09123456789",
                "templateId": 123456,
                "parameters": [{"name": "Code", "value": "123456"}],
            },
        )

    async def test_smsir_adapter_rejects_logical_error_response(self) -> None:
        FakeSmsIrClient.next_response = FakeSmsIrResponse(body={"status": 113, "message": "قالب یافت نشد"})

        with patch("src.services.otp.httpx.AsyncClient", FakeSmsIrClient):
            with self.assertRaises(OtpError):
                await _send_smsir_code("09123456789", "123456")
