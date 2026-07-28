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
    user_session_days: int = Field(3650, alias="USER_SESSION_DAYS")

    otp_mock: bool = Field(True, alias="OTP_MOCK")
    otp_code_digits: int = Field(6, alias="OTP_CODE_DIGITS")
    otp_expire_minutes: int = Field(2, alias="OTP_EXPIRE_MINUTES")
    otp_max_attempts: int = Field(5, alias="OTP_MAX_ATTEMPTS")
    otp_resend_seconds: int = Field(60, alias="OTP_RESEND_SECONDS")

    smsir_api_url: str = Field("https://api.sms.ir/v1", alias="SMSIR_API_URL")
    smsir_api_key: str = Field("", alias="SMSIR_API_KEY")
    smsir_template_id: str = Field("", alias="SMSIR_TEMPLATE_ID")
    smsir_code_parameter: str = Field("Code", alias="SMSIR_CODE_PARAMETER")
    smsir_timeout_seconds: int = Field(10, alias="SMSIR_TIMEOUT_SECONDS")

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
        if not self.otp_mock and (not self.smsir_api_key or not self.smsir_template_id):
            missing.append("SMSIR_API_KEY/SMSIR_TEMPLATE_ID")

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
