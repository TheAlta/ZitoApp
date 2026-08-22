import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from tests._env import setup_test_environment

setup_test_environment()

from src.db import engine
from src.main import app


class UiContractTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    def test_zito_mascot_is_shared_by_landing_and_chat(self) -> None:
        with TestClient(app) as client:
            landing_response = client.get("/")
            chat_response = client.get("/app/")
            asset_response = client.get("/landing-static/zito-mascot.svg")
            logo_response = client.get("/landing-static/zito-logo.svg")
            obsolete_asset_responses = [
                client.get(f"/landing-static/{name}")
                for name in (
                    "logo-z.png",
                    "logo-z-transparent.png",
                    "rocket-svgrepo-com.svg",
                    "zito-avatar.png",
                    "zito-avatar-transparent.png",
                )
            ]

        self.assertEqual(landing_response.status_code, 200)
        self.assertEqual(chat_response.status_code, 200)
        self.assertEqual(asset_response.status_code, 200)
        self.assertEqual(asset_response.headers["content-type"], "image/svg+xml")
        self.assertEqual(logo_response.status_code, 200)
        self.assertEqual(logo_response.headers["content-type"], "image/svg+xml")
        self.assertTrue(all(response.status_code == 404 for response in obsolete_asset_responses))
        self.assertIn("/landing-static/zito-mascot.svg", landing_response.text)
        self.assertIn("/landing-static/zito-logo.svg", landing_response.text)
        self.assertIn("/landing-static/zito-logo.svg", chat_response.text)
        self.assertNotIn("/landing-static/logo-z-transparent.png", landing_response.text)
        self.assertNotIn("/landing-static/logo-z-transparent.png", chat_response.text)
        self.assertEqual(chat_response.text.count("/landing-static/zito-mascot.svg"), 3)
        self.assertIn("object-fit: contain", landing_response.text)
        self.assertIn("object-fit: contain", chat_response.text)
        self.assertIn("height: 188px", landing_response.text)
        self.assertIn("mascot-glow", landing_response.text)
        self.assertIn('id="resendOtp"', landing_response.text)
        self.assertIn('id="nameForm"', landing_response.text)
        self.assertIn("normalizeDigits", landing_response.text)
        self.assertIn("left: calc(50% + 56px)", landing_response.text)
        self.assertIn("left: calc(50% + 72px)", landing_response.text)

        admin_template = Path("src/templates/admin.html").read_text(encoding="utf-8")
        admin_login_template = Path("src/templates/admin_login.html").read_text(encoding="utf-8")
        self.assertIn("/landing-static/zito-logo.svg", admin_template)
        self.assertIn("/landing-static/zito-logo.svg", admin_login_template)

    def test_landing_uses_stacked_light_autofill_fields(self) -> None:
        with TestClient(app) as client:
            response = client.get("/")

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("flex-direction: column", html)
        self.assertIn("color-scheme: light", html)
        self.assertIn("Light cosmic theme", html)
        self.assertIn(".phone-input:-webkit-autofill", html)
        self.assertIn('label for="fullNameInput"', html)
        self.assertIn('label for="phoneInput"', html)
        self.assertIn("display_name: pendingFullName || null", html)
        self.assertIn("data.requires_display_name", html)
        self.assertIn("fetch('/api/me')", html)
        self.assertNotIn("localStorage.setItem('zito_user_id'", html)
        self.assertNotIn("fullName.split(/\\s+/)", html)
        self.assertLess(html.index('id="phoneInput"'), html.index('id="fullNameInput"'))

    def test_landing_has_a_continuous_zito_introduction_view(self) -> None:
        with TestClient(app) as client:
            response = client.get("/")
            ambient_script = client.get("/landing-static/ambient-audio.js")
            ambient_track = client.get("/landing-static/zito-ambient.mp3")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ambient_script.status_code, 200)
        self.assertEqual(ambient_track.status_code, 200)
        self.assertIn("audio/mpeg", ambient_track.headers["content-type"])
        self.assertIn('id="introView"', response.text)
        self.assertIn('id="introStart"', response.text)
        self.assertIn('id="soundToggle"', response.text)
        self.assertIn("زیتو چیه؟", response.text)
        self.assertIn("زیتو یه همراه هوشمند تو در مسیر یادگیریه.", response.text)
        self.assertIn("آماده‌ای برای شروع", response.text)
        self.assertIn("showIntro", response.text)
        self.assertIn("startAmbientSound", response.text)
        self.assertIn("stopAmbientSound", response.text)
        self.assertIn('rel="preload" href="/landing-static/zito-ambient.mp3"', response.text)
        self.assertIn("/landing-static/zito-ambient.mp3", ambient_script.text)
        self.assertIn("track.loop = true", ambient_script.text)
        self.assertIn("attemptAutoplay();", ambient_script.text)
        self.assertIn("zito:landing-sound-muted", ambient_script.text)

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
        self.assertIn('key: "daily_learning_time_text"', html)
        self.assertIn('key: "preferred_career_path"', html)
        self.assertIn('api("/api/me/profile"', html)
        self.assertIn('id="courseList"', html)
        self.assertIn('id="stagePathList"', html)
        self.assertIn('id="activeModuleStages"', html)
        self.assertIn('id="moduleStageMap"', html)
        self.assertIn('id="moduleStageRail"', html)
        self.assertIn('id="moduleCurrentStage"', html)
        self.assertIn('id="moduleNextStage"', html)
        self.assertIn("/api/learning/enrollments/current", html)
        self.assertIn("data-complete-stage", html)
        self.assertIn("path.modules", html)
        self.assertIn("module-path-list", html)
        self.assertIn("renderModuleStageOverview", html)
        self.assertIn("inspectModule", html)
        self.assertIn('aria-current="step"', html)
        self.assertIn("STAGE_LABELS", html)
        self.assertIn("holoFlow", html)
        self.assertIn("module-stage-map", html)
        self.assertIn("prefers-reduced-motion", html)
        self.assertIn("lesson.module_title", html)
        self.assertIn('id="changeCourse"', html)
        self.assertIn('id="coachForm"', html)
        self.assertIn('id="coachInput"', html)
        self.assertIn("/coach/messages", html)
        self.assertIn("coaching.enabled", html)
        self.assertIn("/app/courses/${encodeURIComponent(course.slug)}", html)
        self.assertIn("data-flashcard", html)
        self.assertIn("flashcard-stack", html)
        self.assertIn("flashcard-shadow", html)
        self.assertIn("data-flashcards", html)
        self.assertIn("data-flashcard-front", html)
        self.assertIn("flashcard-deal", html)
        self.assertIn("data-personalized-example", html)
        self.assertIn("data-assessment-question", html)
        self.assertNotIn("/api/training/", html)
        self.assertNotIn("${firstNameOf(profile.full_name)} سلام", html)
        self.assertNotIn("/api/onboarding/${userId}/answer", html)

    def test_course_overview_is_a_separate_single_scroll_ui(self) -> None:
        with TestClient(app) as client:
            response = client.get("/app/courses/personal-development-ai")

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn('id="startCourse"', html)
        self.assertIn("/api/courses/slug/", html)
        self.assertIn("scroll-behavior: smooth", html)
        self.assertIn('font-family: "YekanZito"', html)
        self.assertIn("learning-map", html)
        self.assertIn("/landing-static/zito-mascot.svg", html)
        self.assertIn("/api/courses/${course.id}/enroll", html)

    def test_final_exam_and_certificate_have_dedicated_ui_contracts(self) -> None:
        with TestClient(app) as client:
            chat_response = client.get("/app/")
            certificate_response = client.get("/certificate/ZITO-2026-DEMO")

        self.assertEqual(chat_response.status_code, 200)
        self.assertEqual(certificate_response.status_code, 200)
        chat = chat_response.text
        certificate = certificate_response.text
        self.assertIn('id="finalExamModal"', chat)
        self.assertIn('id="finalExamBody"', chat)
        self.assertIn("requestFinalExamStart", chat)
        self.assertIn("submitFinalExam", chat)
        self.assertIn("/final-exam/start", chat)
        self.assertIn("/final-exam/attempts/", chat)
        self.assertIn("مشاهده و چاپ مدرک", chat)
        self.assertIn("@media print", certificate)
        self.assertIn("/api/certificates/", certificate)
        self.assertIn("window.print()", certificate)
        self.assertIn("گواهی پایان دوره زیتو", certificate)

    def test_admin_renders_canonical_profile_without_legacy_answers(self) -> None:
        admin_template = Path("src/templates/admin.html").read_text(encoding="utf-8")
        admin_login_template = Path("src/templates/admin_login.html").read_text(encoding="utf-8")
        chat_template = Path("src/templates/chat.html").read_text(encoding="utf-8")
        self.assertIn("color-scheme: light", admin_template)
        self.assertIn("color-scheme: light", admin_login_template)
        self.assertIn("Light cosmic theme", chat_template)
        self.assertIn("user.education_level", admin_template)
        self.assertIn("user.learning_goal_interests", admin_template)
        self.assertIn("/api/admin/users/${id}/block", admin_template)
        self.assertIn("رفع مسدودیت", admin_template)
        self.assertNotIn("user.answers", admin_template)
        self.assertNotIn("/api/admin/answers/", admin_template)


if __name__ == "__main__":
    unittest.main()
