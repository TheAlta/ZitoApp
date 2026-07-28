import unittest

from fastapi.testclient import TestClient

from tests._env import setup_test_environment

setup_test_environment()

from src.main import app


class UiContractTests(unittest.TestCase):
    def test_landing_uses_stacked_dark_autofill_fields(self) -> None:
        with TestClient(app) as client:
            response = client.get("/")

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("flex-direction: column", html)
        self.assertIn(".phone-input:-webkit-autofill", html)
        self.assertIn('label for="fullNameInput"', html)
        self.assertIn('label for="phoneInput"', html)
        self.assertIn("display_name: pendingFullName", html)
        self.assertIn("fetch('/api/me')", html)
        self.assertNotIn("localStorage.setItem('zito_user_id'", html)
        self.assertNotIn("fullName.split(/\\s+/)", html)
        self.assertLess(html.index('id="fullNameInput"'), html.index('id="phoneInput"'))

    def test_chat_personalizes_avatar_welcome_without_second_greeting(self) -> None:
        with TestClient(app) as client:
            response = client.get("/app/")

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn('id="welcomeTitle"', html)
        self.assertIn('id="welcomeSub"', html)
        self.assertIn("سلام ${firstName}، من زیتو هستم", html)
        self.assertIn("خوشحالم که اینجایی", html)
        self.assertIn('question: "حوزه کاری یا رشته تحصیلی‌ات چیه؟"', html)
        self.assertIn('key: "education_level"', html)
        self.assertIn('key: "preferred_career_path"', html)
        self.assertIn('api("/api/me/profile"', html)
        self.assertNotIn("${firstNameOf(profile.full_name)} سلام", html)


if __name__ == "__main__":
    unittest.main()
