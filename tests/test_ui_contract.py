import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from tests._env import setup_test_environment

setup_test_environment()

from src.main import app


class UiContractTests(unittest.TestCase):
    def test_zito_mascot_is_shared_by_landing_and_chat(self) -> None:
        with TestClient(app) as client:
            landing_response = client.get("/")
            chat_response = client.get("/app/")
            asset_response = client.get("/landing-static/zito-mascot.svg")

        self.assertEqual(landing_response.status_code, 200)
        self.assertEqual(chat_response.status_code, 200)
        self.assertEqual(asset_response.status_code, 200)
        self.assertEqual(asset_response.headers["content-type"], "image/svg+xml")
        self.assertIn("/landing-static/zito-mascot.svg", landing_response.text)
        self.assertEqual(chat_response.text.count("/landing-static/zito-mascot.svg"), 2)
        self.assertIn("object-fit: contain", landing_response.text)
        self.assertIn("object-fit: contain", chat_response.text)
        self.assertIn("height: 188px", landing_response.text)
        self.assertIn("mascot-glow", landing_response.text)
        self.assertIn('id="resendOtp"', landing_response.text)
        self.assertIn('id="nameForm"', landing_response.text)
        self.assertIn("normalizeDigits", landing_response.text)
        self.assertIn("left: calc(50% + 56px)", landing_response.text)
        self.assertIn("left: calc(50% + 72px)", landing_response.text)

    def test_landing_uses_stacked_dark_autofill_fields(self) -> None:
        with TestClient(app) as client:
            response = client.get("/")

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("flex-direction: column", html)
        self.assertIn(".phone-input:-webkit-autofill", html)
        self.assertIn('label for="fullNameInput"', html)
        self.assertIn('label for="phoneInput"', html)
        self.assertIn("display_name: pendingFullName || null", html)
        self.assertIn("data.requires_display_name", html)
        self.assertIn("fetch('/api/me')", html)
        self.assertNotIn("localStorage.setItem('zito_user_id'", html)
        self.assertNotIn("fullName.split(/\\s+/)", html)
        self.assertLess(html.index('id="phoneInput"'), html.index('id="fullNameInput"'))

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
        self.assertNotIn("/api/onboarding/${userId}/answer", html)

    def test_admin_renders_canonical_profile_without_legacy_answers(self) -> None:
        admin_template = Path("src/templates/admin.html").read_text(encoding="utf-8")
        self.assertIn("user.education_level", admin_template)
        self.assertIn("user.learning_goal_interests", admin_template)
        self.assertNotIn("user.answers", admin_template)
        self.assertNotIn("/api/admin/answers/", admin_template)


if __name__ == "__main__":
    unittest.main()
