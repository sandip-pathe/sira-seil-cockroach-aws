"""API process settings. Secrets are read only by integration factories."""

from __future__ import annotations

from functools import lru_cache
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    app_env: str = Field(default="unset", validation_alias="APP_ENV")
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
    identity_introspection_url: str = Field(
        default="", validation_alias="IDENTITY_INTROSPECTION_URL"
    )
    identity_client_id: str = Field(default="", validation_alias="IDENTITY_CLIENT_ID")
    identity_client_secret: SecretStr = Field(
        default=SecretStr(""), validation_alias="IDENTITY_CLIENT_SECRET"
    )
    identity_expected_issuer: str = Field(default="", validation_alias="IDENTITY_EXPECTED_ISSUER")
    identity_expected_audience: str = Field(
        default="", validation_alias="IDENTITY_EXPECTED_AUDIENCE"
    )
    identity_allowed_roles: str = Field(default="", validation_alias="IDENTITY_ALLOWED_ROLES")
    identity_step_up_acr_values: str = Field(
        default="", validation_alias="IDENTITY_STEP_UP_ACR_VALUES"
    )
    identity_step_up_max_age_seconds: int = Field(
        default=600,
        ge=60,
        le=3600,
        validation_alias="IDENTITY_STEP_UP_MAX_AGE_SECONDS",
    )
    openai_api_key: SecretStr = Field(default=SecretStr(""), validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5-mini", validation_alias="OPENAI_MODEL")

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() in {"development", "test"}

    def assert_safe_runtime(self) -> None:
        if self.app_env.lower() not in {"development", "test", "production"}:
            raise ValueError("APP_ENV must be explicitly set to development, test, or production")
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

    @staticmethod
    def _csv_set(value: str) -> frozenset[str]:
        return frozenset(item.strip() for item in value.split(",") if item.strip())

    def identity_roles(self) -> frozenset[str]:
        return self._csv_set(self.identity_allowed_roles)

    def identity_step_up_values(self) -> frozenset[str]:
        return self._csv_set(self.identity_step_up_acr_values)

    def assert_identity_configuration(self) -> None:
        required = {
            "IDENTITY_INTROSPECTION_URL": self.identity_introspection_url,
            "IDENTITY_CLIENT_ID": self.identity_client_id,
            "IDENTITY_CLIENT_SECRET": self.identity_client_secret.get_secret_value(),
            "IDENTITY_EXPECTED_ISSUER": self.identity_expected_issuer,
            "IDENTITY_EXPECTED_AUDIENCE": self.identity_expected_audience,
            "IDENTITY_ALLOWED_ROLES": self.identity_allowed_roles,
        }
        missing = sorted(name for name, value in required.items() if not value.strip())
        if missing:
            raise ValueError(
                "production identity configuration is incomplete: " + ", ".join(missing)
            )

    @model_validator(mode="after")
    def validate_runtime_modes(self) -> Self:
        self.assert_safe_runtime()
        return self


@lru_cache
def get_settings() -> ApiSettings:
    return ApiSettings()
