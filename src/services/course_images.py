import base64
import binascii
import json
import re
import struct
import zlib
from pathlib import Path
from uuid import uuid4

import httpx

from sqlalchemy.orm import Session

from src.config import get_settings
from src.models import CourseModule, CourseModuleStageContent, CourseVersion
from src.services.cms import _visible_content_text
from src.services.rag import retrieve_course_chunks


SIZE_DIMENSIONS = {"square": "1024x1024", "landscape": "1536x1024", "portrait": "1024x1536"}
SIZE_HINTS = {"square": "Aspect ratio: 1:1 (square).", "landscape": "Aspect ratio: 3:2 (landscape).",
              "portrait": "Aspect ratio: 2:3 (portrait)."}
# Every generated image follows the Zito brand palette (landing/zito-glass.css tokens).
ZITO_STYLE = (
    "Visual style (mandatory, overrides any other style request): Zito brand theme. Calm, minimal, premium "
    "educational illustration with soft rounded shapes, frosted-glass (glassmorphism) cards with thin white rims, "
    "gentle soft shadows and generous whitespace. Background: warm milk/cream (#fff9f3, #f7f1ea) with a subtle "
    "lilac-to-peach gradient. Palette only: plum #735f86, soft plum #9683a7, lilac #ece5f2 and #dcd0e8, "
    "peach #f2ddd2 and #e5beab, cool blue #8ca9c7; text in dark ink #342b3c. No saturated, neon or pure-black "
    "colors, no photorealism, no logos or watermarks. Any text in the image must be Persian, right-to-left, "
    "large and legible."
)
MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_ATTEMPTS = 3
KNOWLEDGE_CHAR_LIMIT = 1800
DATA_URI_PATTERN = re.compile(r"data:image/[a-zA-Z0-9.+-]+;base64,([A-Za-z0-9+/=]+)")


class CourseImageError(RuntimeError):
    pass


async def lesson_knowledge(
    db: Session,
    version: CourseVersion,
    module: CourseModule,
    stage: CourseModuleStageContent,
    prompt: str,
) -> tuple[str, str]:
    """Return lesson text to ground an image, and where it came from.

    A published version answers from its indexed (vectorised) knowledge base; a draft has no
    index yet, so its own stage text stands in.
    """
    parts: list[str] = []
    source = "stage_content"
    if version.status == "published":
        retrieval = await retrieve_course_chunks(
            db, course_version_id=version.id, module_id=module.id,
            question=f"{module.title} - {stage.title} - {prompt}",
        )
        if retrieval.chunks:
            parts = [chunk.content for chunk in retrieval.chunks[:4]]
            source = "rag"
    if not parts:
        parts = _visible_content_text(stage.content_json if isinstance(stage.content_json, dict) else {})
    knowledge = " ".join(" ".join(str(part).split()) for part in parts)
    return knowledge[:KNOWLEDGE_CHAR_LIMIT], source


def image_generation_prompt(
    prompt: str, *, course_title: str, module_title: str, stage_title: str, knowledge: str
) -> str:
    lines = [
        prompt.strip(),
        "",
        "Lesson context (use it so the illustration is accurate for this lesson; show the ideas visually "
        "and never paste this text into the image):",
        f"Course: {course_title}",
        f"Module: {module_title}",
        f"Stage: {stage_title}",
    ]
    if knowledge:
        lines.append(f"Lesson knowledge: {knowledge}")
    return "\n".join(lines)


def _mock_image(size: str) -> bytes:
    """Flat placeholder PNG so the CMS flow works while local AI is mocked."""
    width, height = (int(value) // 4 for value in SIZE_DIMENSIONS[size].split("x"))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    rows = (b"\x00" + bytes((152, 114, 206)) * width) * height
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


async def generate_course_image(prompt: str, size: str) -> tuple[bytes, str, str]:
    settings = get_settings()
    if size not in SIZE_DIMENSIONS:
        raise CourseImageError("اندازه تصویر انتخاب‌شده معتبر نیست.")
    if getattr(settings, "arvan_mock_ai", False):
        return _mock_image(size), "image/png", ".png"
    base_url = settings.effective_content_generation_api_base_url.rstrip("/")
    api_key = settings.effective_content_generation_api_key
    if not base_url or not api_key:
        raise CourseImageError("تنظیمات درگاه تولید تصویر کامل نیست.")
    # The gateway has no /images/generations route; its image models answer on
    # /chat/completions with the picture embedded as a base64 data URI.
    try:
        # trust_env=False keeps the request off any system proxy, like the chat and embedding clients.
        async with httpx.AsyncClient(
            timeout=settings.arvan_image_generation_timeout_seconds, trust_env=False
        ) as client:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    response = await client.post(
                        f"{base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={"model": settings.arvan_image_generation_model,
                              "messages": [{"role": "user", "content": f"{prompt.strip()}\n\n{ZITO_STYLE}\n{SIZE_HINTS[size]}"}]},
                    )
                    break
                except httpx.TimeoutException:
                    raise
                except httpx.TransportError:
                    # The gateway intermittently drops long image requests without a response.
                    if attempt == MAX_ATTEMPTS:
                        raise
    except httpx.TimeoutException as exc:
        raise CourseImageError("تولید تصویر بیش از زمان مجاز طول کشید؛ دوباره تلاش کن.") from exc
    except httpx.HTTPError as exc:
        raise CourseImageError("اتصال به درگاه تولید تصویر چند بار قطع شد؛ کمی بعد دوباره تلاش کن.") from exc
    if response.status_code >= 400:
        raise CourseImageError(f"درگاه تولید تصویر درخواست را نپذیرفت (HTTP {response.status_code}).")
    try:
        content = response.json()["choices"][0]["message"]["content"]
        match = DATA_URI_PATTERN.search(content if isinstance(content, str) else json.dumps(content))
        raw = base64.b64decode(match.group(1), validate=True)
    except (ValueError, KeyError, IndexError, TypeError, AttributeError, binascii.Error) as exc:
        raise CourseImageError("مدل به‌جای تصویر متن برگرداند؛ پرامت را تصویری‌تر بنویس و دوباره تلاش کن.") from exc
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise CourseImageError("حجم تصویر خروجی معتبر نیست (حداکثر ۱۵ مگابایت).")
    signatures = ((b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
                  (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
                  (b"RIFF", "image/webp", ".webp"))
    for signature, mime, extension in signatures:
        if raw.startswith(signature):
            if mime == "image/webp" and raw[8:12] != b"WEBP":
                continue
            return raw, mime, extension
    raise CourseImageError("فرمت تصویر خروجی پشتیبانی نمی‌شود؛ PNG، JPEG یا WebP لازم است.")


def save_image_file(raw: bytes, extension: str) -> tuple[str, Path]:
    settings = get_settings()
    root = Path(settings.generated_media_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    name = f"{uuid4().hex}{extension}"
    path = root / name
    with path.open("xb") as stream:
        stream.write(raw)
    return name, path


def delete_image_file(file_name: str) -> None:
    root = Path(get_settings().generated_media_dir).expanduser().resolve()
    path = (root / file_name).resolve()
    if path.parent == root:
        path.unlink(missing_ok=True)
