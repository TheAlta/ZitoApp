"""Contract for the single-page frontend: how it is served, built and wired to the API."""

import re
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from tests._env import setup_test_environment

setup_test_environment()

from src.db import engine
from src.main import app

FRONTEND = Path("frontend/src")
BUILD = Path("landing/app")


def source(name: str) -> str:
    return (FRONTEND / name).read_text(encoding="utf-8")


class UiContractTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    def test_every_page_route_serves_the_built_app_without_caching_the_shell(self) -> None:
        with TestClient(app) as client:
            for path in (
                "/",
                "/app",
                "/app/",
                "/app/learn",
                "/app/courses/marketing",
                "/app/final-exam",
                "/certificate",
                "/certificate/ZITO-2026-ABCDEF123456",
                "/admin",
                "/admin/login",
                "/admin/studio/3/2",
                "/admin/users/7",
            ):
                response = client.get(path)
                self.assertEqual(response.status_code, 200, path)
                self.assertIn('<div id="root"></div>', response.text, path)
                self.assertEqual(response.headers.get("cache-control"), "no-cache", path)
            self.assertEqual(client.get("/chat", follow_redirects=False).headers["location"], "/app/")

    def test_built_bundle_is_committed_and_self_contained(self) -> None:
        index = (BUILD / "index.html").read_text(encoding="utf-8")
        assets = re.findall(r'(?:src|href)="/landing-static/app/(assets/[^"]+)"', index)
        self.assertTrue(any(a.endswith(".js") for a in assets))
        self.assertTrue(any(a.endswith(".css") for a in assets))
        for asset in assets:
            self.assertTrue((BUILD / asset).exists(), asset)
        # Users in Iran cannot rely on foreign CDNs: fonts and scripts ship with the app.
        css = next((BUILD / a).read_text(encoding="utf-8") for a in assets if a.endswith(".css"))
        self.assertNotIn("fonts.googleapis", index + css)
        self.assertIn("Vazirmatn", css)
        self.assertTrue(list((BUILD / "assets").glob("vazirmatn-arabic-400-*.woff2")))

    def test_build_is_in_sync_with_the_design_stylesheet(self) -> None:
        tokens = source("styles/zito-ui.css")
        built = next(p for p in (BUILD / "assets").glob("index-*.css")).read_text(encoding="utf-8")
        for token in ("--accent-grad", "--mat-panel-fill", ".stage-foot", ".coach-page", ".cert-grid"):
            self.assertIn(token, tokens)
            self.assertIn(token, built)

    def test_routes_cover_every_page_of_the_design(self) -> None:
        routes = source("lib/routes.js")
        pages = source("pages/index.jsx")
        for name in (
            "landing", "certificate", "admin-login", "onboarding", "home", "courses", "course", "lesson",
            "coach", "final", "certs", "profile", "admin", "admin-new", "admin-studio", "admin-images", "admin-users",
            "admin-preview",
        ):
            self.assertIn(f'["{name}",', routes)
            self.assertRegex(pages, rf'(^|\s)"?{re.escape(name)}"?: \{{ render')

    def test_learner_screens_use_the_real_learning_api(self) -> None:
        learner = source("lib/learner.js")
        lesson = source("pages/Lesson.jsx")
        self.assertIn('"/api/learning/overview"', learner)
        self.assertIn('"/api/learning/enrollments/current"', learner)
        self.assertIn("/stages/${stageNumber}/complete", lesson)
        self.assertIn("/personalized-example", lesson)
        # The quiz sends chosen option texts keyed by question id; answer keys never reach the browser.
        self.assertIn("{ answers, selected_items: Object.values(answers) }", lesson)
        self.assertNotRegex(lesson, r"correct_(answer|option)")
        self.assertIn("/final-exam/start", source("pages/FinalExam.jsx"))
        self.assertIn("K.coach(enrollmentId)", source("pages/Coach.jsx"))

    def test_lesson_media_only_loads_trusted_sources(self) -> None:
        lesson = source("pages/Lesson.jsx")
        self.assertIn(r"/^\/api\/course-images\/\d+$/", lesson)
        self.assertIn(r"/^\/landing-static\/course-media\/[a-z0-9][a-z0-9._-]*\.(mp4|jpg|png|webp)$/i", lesson)

    def test_sign_in_keeps_the_login_then_signup_flow(self) -> None:
        landing = source("pages/Landing.jsx")
        store = source("lib/store.jsx")
        self.assertIn("حساب نداری؟ ثبت‌نام کن", landing)
        self.assertIn("requiresName", landing)
        self.assertIn('"/api/auth/otp/request"', store)
        self.assertIn('"/api/auth/otp/verify"', store)
        self.assertIn("display_name: displayName || null", store)
        # Landing ambient music survives the redesign and remembers mute per tab.
        self.assertIn("zito:landing-sound-muted", source("lib/ambient.js"))

    def test_cms_screens_cover_the_authoring_lifecycle(self) -> None:
        studio = source("pages/admin/Studio.jsx")
        for fragment in (
            "/generate", "/publish", "/revisions", "/brief", "/modules/", "/stages/", "deactivate", "reactivate",
            "soft-delete", "restore", "rag-retry-failed", "client_request_id", "generation_progress",
            "needs_regeneration", "generation_instructions",
        ):
            self.assertIn(fragment, studio)
        images = source("pages/admin/Images.jsx")
        for fragment in ("/images`", "/course-images/publish", "/regenerate"):
            self.assertIn(fragment, images)
        users = source("pages/admin/Users.jsx")
        for fragment in ("/block", "/unblock", "/restore", "include_deleted=true", "course_titles"):
            self.assertIn(fragment, users)

    def test_original_mascot_and_its_motions_are_served(self) -> None:
        mascot = source("ui/mascot.jsx")
        with TestClient(app) as client:
            paths = re.findall(r"`\$\{STATIC\}(/[^`?]+)", mascot)
            self.assertGreaterEqual(len(paths), 9)
            for path in paths:
                self.assertEqual(client.get(f"/landing-static{path}").status_code, 200, path)
        for motion in ("zito-lottie/zito-lottie.json", "zito-intro-lottie/zito-intro-lottie.json", "course-mascot-lottie/zito-course-mascot.json"):
            self.assertIn(motion, mascot)
        # The glass drop is no longer drawn as a character anywhere; the coach wears the original glasses.
        for page in Path(FRONTEND / "pages").rglob("*.jsx"):
            self.assertNotRegex(page.read_text(encoding="utf-8"), r"<Drop[^>]*\bface\b", page.name)
        self.assertIn("<MascotAvatar size={e} busy={t} coach />", source("ui/art.jsx"))
        self.assertIn('<Mascot motion="wave"', source("pages/Landing.jsx"))
        self.assertIn('<Mascot motion="intro"', source("pages/Landing.jsx"))

    def test_course_overview_keeps_the_previous_journey(self) -> None:
        overview = source("pages/CourseOverview.jsx")
        for heading in (
            "معرفی مسیر یادگیری زیتو",
            "آخر این مسیر قرار است کجا برسی؟",
            "نقشه و مسیر دوره",
            "این دوره چه چیزی را برایت متفاوت می‌کند؟",
            "گواهی پایان دوره زیتو",
            "مسیر آماده است",
        ):
            self.assertIn(heading, overview)
        self.assertIn('<Mascot motion="course"', overview)
        self.assertIn("animateMotion", overview)
        self.assertIn("useOverview(!preview)", overview)
        self.assertIn("/admin/preview/", source("pages/admin/Studio.jsx"))

    def test_checklist_and_scenario_choices_are_saved_with_the_stage(self) -> None:
        lesson = source("pages/Lesson.jsx")
        self.assertIn("{ selected_items: selected }", lesson)
        self.assertIn("pick(items.filter((_, k) => next[k]))", lesson)
        self.assertIn("pick([option])", lesson)
        self.assertNotIn("ذخیره نمی‌شود", lesson)

    def test_ended_sessions_return_to_sign_in(self) -> None:
        self.assertIn('"zito:unauthorized"', source("lib/api.js"))
        self.assertIn('addEventListener("zito:unauthorized"', source("lib/store.jsx"))
        exam = source("pages/FinalExam.jsx")
        self.assertIn('exam.status === "not_required"', exam)

    def test_session_cache_is_cleared_between_accounts(self) -> None:
        store = source("lib/store.jsx")
        self.assertGreaterEqual(store.count("clearCache()"), 3)


if __name__ == "__main__":
    unittest.main()
