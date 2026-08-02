"""API process settings. Secrets are read only by integration factories."""

from __future__ import annotations

from functools import lru_cache
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    app_env: str = Field(default="development", validation_alias="APP_ENV")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    development_fixture_mode: bool = Field(
        default=True, validation_alias="DEVELOPMENT_FIXTURE_MODE"
    )
    demo_reset_enabled: bool = Field(default=True, validation_alias="DEMO_RESET_ENABLED")
    public_base_url: str = Field(
        default="http://localhost:8000", validation_alias="PUBLIC_BASE_URL"
    )
    web_base_url: str = Field(default="http://localhost:3000", validation_alias="WEB_BASE_URL")
    database_url: str = Field(
        default="postgresql+asyncpg://localhost:5432/sira",
        validation_alias="DATABASE_URL",
    )
    browser_return_signing_key: SecretStr = Field(
        default=SecretStr(""), validation_alias="BROWSER_RETURN_SIGNING_KEY"
    )
    browser_return_ttl_seconds: int = Field(
        default=600,
        ge=60,
        le=1800,
        validation_alias="BROWSER_RETURN_TTL_SECONDS",
    )

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() in {"development", "test"}

    def assert_safe_runtime(self) -> None:
        if self.is_development:
            return
        if self.development_fixture_mode or self.demo_reset_enabled:
            raise ValueError(
                "production requires DEVELOPMENT_FIXTURE_MODE=false and DEMO_RESET_ENABLED=false"
            )
        try:
            backend = make_url(self.database_url).get_backend_name()
        except Exception:
            backend = "invalid"
        if backend != "postgresql":
            raise ValueError("production requires a PostgreSQL DATABASE_URL")
        self.browser_return_signing_secret()

    def browser_return_signing_secret(self) -> str:
        value = self.browser_return_signing_key.get_secret_value()
        if len(value.encode("utf-8")) >= 32:
            return value
        if self.is_development:
            return "development-only-browser-return-key"  # pragma: allowlist secret
        raise ValueError("production requires a 32-byte BROWSER_RETURN_SIGNING_KEY")

    @model_validator(mode="after")
    def validate_runtime_modes(self) -> Self:
        self.assert_safe_runtime()
        return self


@lru_cache
def get_settings() -> ApiSettings:
    return ApiSettings()
