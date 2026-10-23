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
    guest_session_enabled: bool = Field(default=False, validation_alias="GUEST_SESSION_ENABLED")
    guest_session_signing_key: SecretStr = Field(
        default=SecretStr(""), validation_alias="GUEST_SESSION_SIGNING_KEY"
    )
    exchange_route_signing_key: SecretStr = Field(
        default=SecretStr(""), validation_alias="EXCHANGE_ROUTE_SIGNING_KEY"
    )
    guest_session_ttl_seconds: int = Field(
        default=604_800,
        ge=3_600,
        le=2_592_000,
        validation_alias="GUEST_SESSION_TTL_SECONDS",
    )
    public_base_url: str = Field(
        default="http://localhost:8000", validation_alias="PUBLIC_BASE_URL"
    )
    web_base_url: str = Field(default="http://localhost:3000", validation_alias="WEB_BASE_URL")
    database_url: str = Field(
        default="cockroachdb+asyncpg://sira_app@127.0.0.1:26257/sira?ssl=disable",
        validation_alias="DATABASE_URL",
    )
    catalog_database_url: SecretStr = Field(
        default=SecretStr(""), validation_alias="SIRA_CATALOG_DATABASE_URL"
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
    firebase_project_id: str = Field(default="", validation_alias="FIREBASE_PROJECT_ID")
    openai_api_key: SecretStr = Field(default=SecretStr(""), validation_alias="OPENAI_API_KEY")
    openai_chat_model: str = Field(default="gpt-4.1-mini", validation_alias="OPENAI_CHAT_MODEL")
    openai_search_model: str = Field(default="gpt-4.1-mini", validation_alias="OPENAI_SEARCH_MODEL")
    openai_embedding_model: str = Field(
        default="text-embedding-3-small", validation_alias="OPENAI_EMBEDDING_MODEL"
    )
    cognitive_kernel_enabled: bool = Field(
        default=True, validation_alias="COGNITIVE_KERNEL_ENABLED"
    )
    principal_isolation_enabled: bool = Field(
        default=True, validation_alias="PRINCIPAL_ISOLATION_ENABLED"
    )

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() in {"development", "test"}

    def assert_safe_runtime(self) -> None:
        if self.app_env.lower() not in {"development", "test", "production"}:
            raise ValueError("APP_ENV must be explicitly set to development, test, or production")
        if self.is_development:
            return
        try:
            backend = make_url(self.database_url).get_backend_name()
        except Exception:
            backend = "invalid"
        if backend != "cockroachdb":
            raise ValueError("production requires a CockroachDB DATABASE_URL")
        catalog_url = self.catalog_database_url.get_secret_value().strip()
        if catalog_url:
            try:
                catalog_backend = make_url(catalog_url).get_backend_name()
            except Exception:
                catalog_backend = "invalid"
            if catalog_backend != "cockroachdb":
                raise ValueError("production requires a CockroachDB SIRA_CATALOG_DATABASE_URL")
        if self.guest_session_enabled:
            self.guest_session_signing_secret()
        self.exchange_route_signing_secret()
        if not self.openai_api_key.get_secret_value().strip():
            raise ValueError("production requires OPENAI_API_KEY")
        if not self.cognitive_kernel_enabled:
            raise ValueError("production requires COGNITIVE_KERNEL_ENABLED=true")
        if not self.principal_isolation_enabled:
            raise ValueError(
                "production cognitive runtime requires PRINCIPAL_ISOLATION_ENABLED=true"
            )

    def guest_session_signing_secret(self) -> str:
        value = self.guest_session_signing_key.get_secret_value()
        if len(value.encode("utf-8")) >= 32:
            return value
        if self.is_development:
            return "development-only-guest-session-signing-key"
        raise ValueError("production guest sessions require a 32-byte GUEST_SESSION_SIGNING_KEY")

    def exchange_route_signing_secret(self) -> str:
        value = self.exchange_route_signing_key.get_secret_value()
        if len(value.encode("utf-8")) >= 32:
            return value
        if self.is_development:
            return "development-only-exchange-route-signing-key"
        raise ValueError("production requires a 32-byte EXCHANGE_ROUTE_SIGNING_KEY")

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
