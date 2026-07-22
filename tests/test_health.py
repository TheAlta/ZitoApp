import unittest

from fastapi.testclient import TestClient

from tests._env import setup_test_environment

setup_test_environment()

from src.config import get_settings
from src.db import engine
from src.main import app


class HealthEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        get_settings.cache_clear()

    def test_health_endpoint_returns_database_ok(self) -> None:
        with TestClient(app) as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})
        engine.dispose()
