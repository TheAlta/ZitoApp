import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from tests._env import setup_test_environment

setup_test_environment()

from src.config import get_settings
from src.lib.arvan_embeddings import cosine_similarity, embed_texts


class ArvanEmbeddingMockTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        get_settings.cache_clear()

    async def test_mock_embeddings_are_stable_and_semantically_comparable(self) -> None:
        first, related, unrelated = await embed_texts(
            [
                "هدف یادگیری را به یک اقدام کوچک تبدیل کن",
                "برای هدف یادگیری یک قدم کوچک برنامه‌ریزی کن",
                "قرارداد اجاره و بندهای حقوقی",
            ]
        )

        self.assertEqual(len(first), len(related))
        self.assertEqual(len(first), 3072)
        self.assertGreater(cosine_similarity(first, related), cosine_similarity(first, unrelated))


class ArvanEmbeddingRetryTests(unittest.TestCase):
    def test_transient_timeout_is_retried_once_and_vectors_are_returned(self) -> None:
        response = httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.25, 0.75]}]},
            request=httpx.Request("POST", "https://example.invalid/v1/embeddings"),
        )
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = False
        client.post = AsyncMock(side_effect=[httpx.ReadTimeout("temporary"), response])
        settings = SimpleNamespace(
            arvan_mock_ai=False,
            has_embedding_configuration=True,
            effective_embedding_api_base_url="https://example.invalid/v1",
            effective_embedding_api_key="test",
            arvan_embedding_model="test-embedding",
            arvan_embedding_dimensions=2,
            arvan_embedding_timeout_seconds=30,
        )

        with (
            patch("src.lib.arvan_embeddings.get_settings", return_value=settings),
            patch("src.lib.arvan_embeddings.httpx.AsyncClient", return_value=client),
            patch("src.lib.arvan_embeddings.asyncio.sleep", new=AsyncMock()),
        ):
            vectors = asyncio.run(embed_texts(["course content"]))

        self.assertEqual(vectors, [[0.25, 0.75]])
        self.assertEqual(client.post.await_count, 2)


if __name__ == "__main__":
    unittest.main()
