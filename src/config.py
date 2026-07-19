from functools import lru_cache

from pydantic import Field
from pydantic import model_validator
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

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.app_env.lower() not in {"prod", "production"}:
            return self

        missing = []
        if self.admin_session_secret in {"", "change-me-admin-session-secret", "replace_with_long_random_secret"}:
            missing.append("ADMIN_SESSION_SECRET")
        if not self.arvan_mock_ai and (not self.arvan_api_base_url or not self.arvan_api_key):
            missing.append("ARVAN_API_BASE_URL/ARVAN_API_KEY")

        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Unsafe production configuration. Set secure values for: {joined}")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"prod", "production"}

    @property
    def has_safe_admin_seed_password(self) -> bool:
        return self.admin_password not in {"", "change-me", "replace_with_strong_admin_password"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
