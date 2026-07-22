import os
from pathlib import Path


def setup_test_environment() -> None:
    db_path = Path("test_ci.db").resolve()
    os.environ["APP_NAME"] = "ZitoTest"
    os.environ["APP_ENV"] = "test"
    os.environ["AUTO_CREATE_TABLES"] = "true"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["ARVAN_API_BASE_URL"] = "https://example.invalid/v1"
    os.environ["ARVAN_API_KEY"] = "test-key"
    os.environ["ARVAN_MODEL"] = "GPT-5.4-Mini"
    os.environ["ARVAN_TIMEOUT_SECONDS"] = "5"
    os.environ["ARVAN_MOCK_AI"] = "true"
    os.environ["ADMIN_USERNAME"] = "zito_admin"
    os.environ["ADMIN_PASSWORD"] = "local-test-admin-password"
    os.environ["ADMIN_SESSION_SECRET"] = "local-test-session-secret-that-is-long-enough"
    os.environ["ADMIN_SESSION_DAYS"] = "7"
