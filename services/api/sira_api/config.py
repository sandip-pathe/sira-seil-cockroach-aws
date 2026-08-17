"""API process settings. Secrets are read only by integration factories."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal, Self

from pydantic import AliasChoices, Field, SecretStr, model_validator
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
    guest_session_enabled: bool = Field(default=False, validation_alias="GUEST_SESSION_ENABLED")
    guest_session_signing_key: SecretStr = Field(
        default=SecretStr(""), validation_alias="GUEST_SESSION_SIGNING_KEY"
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
    openai_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("SIRA_OPENAI_API_KEY", "OPENAI_API_KEY"),
    )
    seil_openai_api_key: SecretStr = Field(
        default=SecretStr(""), validation_alias="SEIL_OPENAI_API_KEY"
    )
    extra_openai_api_keys: SecretStr = Field(
        default=SecretStr(""), validation_alias="EXTRA_OPENAI_API_KEYS"
    )
    openai_model: str = Field(default="gpt-5-mini", validation_alias="OPENAI_MODEL")
    aws_region: str = Field(
        default="us-east-1",
        validation_alias=AliasChoices("AWS_REGION", "AWS_DEFAULT_REGION"),
    )
    aws_profile: str = Field(default="", validation_alias="AWS_PROFILE")
    agent_runtime_provider: Literal["agentcore", "bedrock", "openai"] = Field(
        default="openai", validation_alias="AGENT_RUNTIME_PROVIDER"
    )
    cognitive_kernel_enabled: bool = Field(
        default=False, validation_alias="COGNITIVE_KERNEL_ENABLED"
    )
    principal_isolation_enabled: bool = Field(
        default=False, validation_alias="PRINCIPAL_ISOLATION_ENABLED"
    )
    sira_agentcore_runtime_arn: str = Field(
        default="", validation_alias="SIRA_AGENTCORE_RUNTIME_ARN"
    )
    seil_agentcore_runtime_arn: str = Field(
        default="", validation_alias="SEIL_AGENTCORE_RUNTIME_ARN"
    )
    runtime_ticket_signing_key: SecretStr = Field(
        default=SecretStr(""), validation_alias="RUNTIME_TICKET_SIGNING_KEY"
    )
    bedrock_chat_model_id: str = Field(
        default="amazon.nova-micro-v1:0",
        validation_alias="BEDROCK_CHAT_MODEL_ID",
    )
    bedrock_embedding_model_id: str = Field(
        default="amazon.titan-embed-text-v2:0",
        validation_alias="BEDROCK_EMBEDDING_MODEL_ID",
    )
    bedrock_guardrail_id: str = Field(default="", validation_alias="BEDROCK_GUARDRAIL_ID")
    bedrock_guardrail_version: str = Field(
        default="DRAFT", validation_alias="BEDROCK_GUARDRAIL_VERSION"
    )
    s3_evidence_bucket: str = Field(default="", validation_alias="SIRA_S3_EVIDENCE_BUCKET")
    s3_evidence_kms_key_id: str = Field(default="", validation_alias="SIRA_S3_EVIDENCE_KMS_KEY_ID")

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
        if self.agent_runtime_provider != "agentcore":
            raise ValueError("production requires AGENT_RUNTIME_PROVIDER=agentcore")
        if self.cognitive_kernel_enabled and not self.principal_isolation_enabled:
            raise ValueError(
                "production COGNITIVE_KERNEL_ENABLED requires PRINCIPAL_ISOLATION_ENABLED=true"
            )
        if self.cognitive_kernel_enabled:
            if not self.sira_agentcore_runtime_arn or not self.seil_agentcore_runtime_arn:
                raise ValueError("production cognitive runtime requires both AgentCore ARNs")
            if len(self.runtime_ticket_signing_key.get_secret_value().encode()) < 32:
                raise ValueError("production cognitive runtime requires a 32-byte ticket key")

    def guest_session_signing_secret(self) -> str:
        value = self.guest_session_signing_key.get_secret_value()
        if len(value.encode("utf-8")) >= 32:
            return value
        if self.is_development:
            return "development-only-guest-session-signing-key"
        raise ValueError("production guest sessions require a 32-byte GUEST_SESSION_SIGNING_KEY")

    @staticmethod
    def _csv_set(value: str) -> frozenset[str]:
        return frozenset(item.strip() for item in value.split(",") if item.strip())

    def identity_roles(self) -> frozenset[str]:
        return self._csv_set(self.identity_allowed_roles)

    def identity_step_up_values(self) -> frozenset[str]:
        return self._csv_set(self.identity_step_up_acr_values)

    def resolved_seil_openai_api_key(self) -> str:
        explicit = self.seil_openai_api_key.get_secret_value().strip()
        if explicit:
            return explicit
        extras = self.extra_openai_api_keys.get_secret_value().strip()
        if not extras:
            return ""
        if extras.startswith("["):
            import json

            try:
                values = json.loads(extras)
            except json.JSONDecodeError:
                return ""
            if isinstance(values, list):
                return next((str(value).strip() for value in values if str(value).strip()), "")
            return ""
        return next((item.strip() for item in extras.split(",") if item.strip()), "")

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
