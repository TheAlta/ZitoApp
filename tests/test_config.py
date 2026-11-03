import unittest

from pydantic import ValidationError

from tests._env import setup_test_environment

setup_test_environment()

from src.config import Settings  # noqa: E402


def production_settings(**overrides) -> Settings:
    values = {
        "app_env": "production",
        "auto_create_tables": False,
        "OTP_MOCK": False,
        "SMSIR_API_KEY": "sms-key",
        "SMSIR_TEMPLATE_ID": "1",
    }
    return Settings(_env_file=None, **{**values, **overrides})


class ProductionSafetyTests(unittest.TestCase):
    def test_production_starts_with_both_switches_off(self) -> None:
        self.assertTrue(production_settings().is_production)

    def test_production_refuses_mock_sign_in(self) -> None:
        with self.assertRaisesRegex(ValidationError, "OTP_MOCK"):
            production_settings(OTP_MOCK=True)

    def test_production_refuses_automatic_tables(self) -> None:
        with self.assertRaisesRegex(ValidationError, "AUTO_CREATE_TABLES"):
            production_settings(auto_create_tables=True)

    def test_local_work_keeps_both_switches(self) -> None:
        settings = Settings(_env_file=None, app_env="local", OTP_MOCK=True, auto_create_tables=True)
        self.assertTrue(settings.otp_mock)
        self.assertTrue(settings.auto_create_tables)


if __name__ == "__main__":
    unittest.main()
