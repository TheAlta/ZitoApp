import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import AsyncMock, patch

from tests._env import setup_test_environment

setup_test_environment()

from src.cli.seed_course_content import main
from src.db import Base, engine


class SeedCourseContentCliTests(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    def test_seed_indexes_initial_kb_jobs_by_default(self) -> None:
        with patch(
            "src.cli.seed_course_content.run_index_worker_once",
            new=AsyncMock(return_value=[]),
        ) as index_worker, patch.object(sys, "argv", ["seed-course-content"]), redirect_stdout(io.StringIO()) as output:
            result = main()

        self.assertEqual(result, 0)
        index_worker.assert_awaited_once()
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["course_slug"], "personal-development-ai")
        self.assertFalse(payload["indexing"]["skipped"])

    def test_seed_can_leave_jobs_for_the_supervised_worker(self) -> None:
        with patch(
            "src.cli.seed_course_content.run_index_worker_once",
            new=AsyncMock(),
        ) as index_worker, patch.object(
            sys,
            "argv",
            ["seed-course-content", "--skip-index"],
        ), redirect_stdout(io.StringIO()) as output:
            result = main()

        self.assertEqual(result, 0)
        index_worker.assert_not_awaited()
        payload = json.loads(output.getvalue())
        self.assertTrue(payload["indexing"]["skipped"])


if __name__ == "__main__":
    unittest.main()
