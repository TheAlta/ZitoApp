from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Zito"
    app_env: str = "local"
    auto_create_tables: bool = True

    database_url: str = Field(..., alias="DATABASE_URL")

    arvan_api_base_url: str = Field("", alias="ARVAN_API_BASE_URL")
    arvan_api_key: str = Field("", alias="ARVAN_API_KEY")
    arvan_model: str = Field("GPT-5.4-Mini", alias="ARVAN_MODEL")
    arvan_timeout_seconds: int = Field(45, alias="ARVAN_TIMEOUT_SECONDS")
    arvan_mock_ai: bool = Field(False, alias="ARVAN_MOCK_AI")

    admin_username: str = Field("zito_admin", alias="ADMIN_USERNAME")
    admin_password: str = Field("change-me", alias="ADMIN_PASSWORD")
    admin_session_secret: str = Field("change-me-admin-session-secret", alias="ADMIN_SESSION_SECRET")
    admin_session_days: int = Field(3650, alias="ADMIN_SESSION_DAYS")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
