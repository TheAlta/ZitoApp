import unittest

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


if __name__ == "__main__":
    unittest.main()
