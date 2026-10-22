import base64
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from tests._env import setup_test_environment

setup_test_environment()

from src.config import get_settings
from src.db import Base, SessionLocal, engine
from src.main import app
from src.seed import seed_defaults
from src.services.course_images import (
    ZITO_STYLE,
    CourseImageError,
    generate_course_image,
    image_generation_prompt,
)


class _Response:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("failed", request=httpx.Request("POST", "https://gateway.test"), response=httpx.Response(self.status_code))

    def json(self):
        return self._payload


class _Client:
    def __init__(self, response, drops=0, **kwargs):
        self.response = response
        self.post_args = None
        self.drops = drops
        self.calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, *args, **kwargs):
        self.post_args = (args, kwargs)
        self.calls += 1
        if self.calls <= self.drops:
            raise httpx.RemoteProtocolError("Server disconnected without sending a response.")
        return self.response


class CourseVideoBlockTests(unittest.TestCase):
    def test_video_block_renders_uncropped_and_stays_out_of_the_knowledge_base(self):
        from src.services.cms import _visible_content_text

        video = {"kind": "video", "title": "ویدیوی معرفی", "src": "/landing-static/course-media/intro.mp4"}
        self.assertEqual(_visible_content_text({"blocks": [{"kind": "paragraph", "body": "متن درس"}, video]}), ["paragraph", "متن درس"])
        lesson = Path("frontend/src/pages/Lesson.jsx").read_text(encoding="utf-8")
        self.assertIn('case "video":', lesson)
        # Only committed course media plays, uncropped, with native controls once started.
        self.assertIn(r"\/landing-static\/course-media\/", lesson)
        self.assertIn('objectFit: "contain"', lesson)
        self.assertIn("controls={started}", lesson)


class CourseImageTests(unittest.IsolatedAsyncioTestCase):
    def _settings(self):
        return SimpleNamespace(effective_content_generation_api_base_url="https://gateway.test/v1",
                               effective_content_generation_api_key="test", arvan_image_generation_model="image-test",
                               arvan_image_generation_timeout_seconds=2)

    async def _generate(self, client):
        with patch("src.services.course_images.get_settings", return_value=self._settings()), \
             patch("src.services.course_images.httpx.AsyncClient", side_effect=lambda **kwargs: client):
            return await generate_course_image("an educational image", "landscape")

    async def test_image_generation_reports_gateway_refusal(self):
        with self.assertRaisesRegex(CourseImageError, "HTTP 403"):
            await self._generate(_Client(_Response(403, {})))

    async def test_image_generation_reports_text_only_answer(self):
        payload = {"choices": [{"message": {"content": "I cannot draw that."}}]}
        with self.assertRaisesRegex(CourseImageError, "متن برگرداند"):
            await self._generate(_Client(_Response(200, payload)))

    async def test_image_generation_reads_data_uri_from_chat_completion(self):
        png = b"\x89PNG\r\n\x1a\n" + b"test"
        content = f"![image](data:image/png;base64,{base64.b64encode(png).decode()})"
        client = _Client(_Response(200, {"choices": [{"message": {"content": content}}]}))
        data, mime, extension = await self._generate(client)
        self.assertEqual(data, png)
        self.assertEqual((mime, extension), ("image/png", ".png"))
        args, kwargs = client.post_args
        self.assertEqual(args[0], "https://gateway.test/v1/chat/completions")
        self.assertEqual(kwargs["json"]["messages"][0]["content"],
                         f"an educational image\n\n{ZITO_STYLE}\nAspect ratio: 3:2 (landscape).")
        self.assertIn("#735f86", ZITO_STYLE)

    def test_prompt_carries_lesson_context_after_the_admin_instruction(self):
        prompt = image_generation_prompt("نمودار مراحل مذاکره", course_title="فروش تلفنی", module_title="کشف نیاز",
                                         stage_title="خلاصه درس", knowledge="پرسش باز نیاز مشتری را روشن می‌کند.")
        self.assertTrue(prompt.startswith("نمودار مراحل مذاکره\n"))
        self.assertIn("Course: فروش تلفنی", prompt)
        self.assertIn("Module: کشف نیاز", prompt)
        self.assertIn("Stage: خلاصه درس", prompt)
        self.assertIn("Lesson knowledge: پرسش باز نیاز مشتری را روشن می‌کند.", prompt)

    async def test_image_generation_retries_dropped_connections(self):
        png = b"\x89PNG\r\n\x1a\n" + b"test"
        content = f"![image](data:image/png;base64,{base64.b64encode(png).decode()})"
        payload = {"choices": [{"message": {"content": content}}]}
        client = _Client(_Response(200, payload), drops=2)
        self.assertEqual((await self._generate(client))[0], png)
        self.assertEqual(client.calls, 3)
        with self.assertRaisesRegex(CourseImageError, "قطع شد"):
            await self._generate(_Client(_Response(200, payload), drops=3))


class CourseImageApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed_defaults(db)

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    def _admin_client(self) -> TestClient:
        client = TestClient(app)
        response = client.post(
            "/api/admin/login",
            json={"username": "zito_admin", "password": "local-test-admin-password"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return client

    def _generated_course(self, client, slug):
        brief = {"title": "دوره تصویر", "topic": "فروش", "goal": "بهبود مذاکره با مشتری در جلسه فروش.",
                 "duration": "دو هفته", "audience": "فروشندگان", "target_group": "تیم فروش",
                 "level": "مقدماتی", "module_count": 2, "estimated_learning_hours": 6, "slug": slug}
        draft = client.post("/api/admin/courses", json=brief).json()
        base = f"/api/admin/courses/{draft['course_id']}/versions/{draft['version_number']}"
        self.assertEqual(client.post(f"{base}/generate").status_code, 202)
        return base, client.get(base).json()["modules"]

    def _stage_image_ids(self, client, base, module_index, stage_index):
        blocks = client.get(base).json()["modules"][module_index]["stages"][stage_index]["content"]["blocks"]
        return [block["asset_id"] for block in blocks if block.get("kind") == "image"]

    def test_images_are_drafted_reviewed_edited_and_published_to_their_stages(self):
        with self._admin_client() as client:
            base, modules = self._generated_course(client, "course-image-studio")
            first, second = modules[0], modules[1]
            quiz_stage, summary_stage, other_stage = first["stages"][6], first["stages"][1], second["stages"][2]

            mismatched = client.post(f"{base}/images", json={
                "module_id": second["id"], "stage_id": quiz_stage["id"], "prompt": "نمودار مراحل مذاکره"})
            self.assertEqual(mismatched.status_code, 422, mismatched.text)

            created = []
            for module, stage, size in ((first, quiz_stage, "landscape"), (first, quiz_stage, "portrait"),
                                        (first, summary_stage, "square"), (second, other_stage, "landscape")):
                response = client.post(f"{base}/images", json={
                    "module_id": module["id"], "stage_id": stage["id"], "prompt": "نمودار مراحل مذاکره", "size": size})
                self.assertEqual(response.status_code, 200, response.text)
                body = response.json()
                self.assertEqual((body["status"], body["knowledge_source"]), ("draft", "stage_content"))
                self.assertEqual((body["module_id"], body["stage_id"]), (module["id"], stage["id"]))
                created.append(body)

            # Drafts are listed for review but are not part of any stage yet.
            drafts = client.get("/api/admin/course-images", params={"status": "draft"}).json()
            self.assertEqual({item["id"] for item in drafts}, {item["id"] for item in created})
            self.assertEqual(self._stage_image_ids(client, base, 0, 6), [])
            with TestClient(app) as anonymous:
                self.assertEqual(anonymous.get(created[0]["src"]).status_code, 404)
            self.assertEqual(client.get(created[0]["src"]).headers["content-type"], "image/png")

            # Editing a draft replaces its file and prompt in place.
            media_root = Path(get_settings().generated_media_dir)
            files_before = set(media_root.iterdir())
            edited = client.post(f"/api/admin/course-images/{created[2]['id']}/regenerate",
                                 json={"prompt": "اینفوگرافیک ساده از خلاصه درس", "size": "landscape"})
            self.assertEqual(edited.status_code, 200, edited.text)
            self.assertEqual(edited.json()["prompt"], "اینفوگرافیک ساده از خلاصه درس")
            self.assertNotEqual(edited.json()["revision"], created[2]["revision"])
            files_after = set(media_root.iterdir())
            self.assertEqual((len(files_before - files_after), len(files_after - files_before)), (1, 1))

            deleted = client.delete(f"/api/admin/course-images/{created[3]['id']}")
            self.assertEqual(deleted.status_code, 200, deleted.text)

            published = client.post("/api/admin/course-images/publish",
                                    json={"asset_ids": [item["id"] for item in created[:3]]})
            self.assertEqual(published.status_code, 200, published.text)
            self.assertEqual(published.json()["published_count"], 3)
            # Two images in one stage keep their order and lead the stage's own blocks.
            self.assertEqual(self._stage_image_ids(client, base, 0, 6), [created[0]["id"], created[1]["id"]])
            quiz_blocks = client.get(base).json()["modules"][0]["stages"][6]["content"]["blocks"]
            self.assertEqual([block["kind"] for block in quiz_blocks[:2]], ["image", "image"])
            self.assertEqual(quiz_blocks[2:], quiz_stage["content"]["blocks"])
            self.assertEqual(self._stage_image_ids(client, base, 0, 1), [created[2]["id"]])
            self.assertEqual(self._stage_image_ids(client, base, 1, 2), [])
            self.assertEqual(client.get("/api/admin/course-images", params={"status": "draft"}).json(), [])

            locked = client.post(f"/api/admin/course-images/{created[0]['id']}/regenerate",
                                 json={"prompt": "نمودار مراحل مذاکره"})
            self.assertEqual(locked.status_code, 409, locked.text)

            # Removing a published image from its stage returns it to the review list.
            removed = client.delete(f"{base}/stages/{quiz_stage['id']}/images/{created[1]['id']}")
            self.assertEqual(removed.status_code, 200, removed.text)
            self.assertEqual(self._stage_image_ids(client, base, 0, 6), [created[0]["id"]])
            self.assertEqual([item["id"] for item in client.get(
                "/api/admin/course-images", params={"status": "draft"}).json()], [created[1]["id"]])

    def test_published_course_takes_images_and_serves_only_published_ones(self):
        with self._admin_client() as client:
            base, modules = self._generated_course(client, "course-image-live")
            module, stage = modules[0], modules[0]["stages"][2]
            self.assertEqual(client.post(f"{base}/publish").status_code, 200)

            created = client.post(f"{base}/images", json={
                "module_id": module["id"], "stage_id": stage["id"], "prompt": "نمودار مراحل مذاکره"})
            self.assertEqual(created.status_code, 200, created.text)
            image = created.json()
            self.assertIn(image["knowledge_source"], {"rag", "stage_content"})
            with TestClient(app) as anonymous:
                self.assertEqual(anonymous.get(image["src"]).status_code, 404)
                published = client.post("/api/admin/course-images/publish", json={"asset_ids": [image["id"]]})
                self.assertEqual(published.status_code, 200, published.text)
                served = anonymous.get(image["src"])
                self.assertEqual(served.status_code, 200)
                self.assertEqual(served.headers["content-type"], "image/png")
            version = client.get(base).json()
            self.assertEqual(version["status"], "published")
            self.assertEqual(version["modules"][0]["stages"][2]["content"]["blocks"][0]["asset_id"], image["id"])


if __name__ == "__main__":
    unittest.main()
