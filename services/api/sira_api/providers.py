"""Server-only provider composition; secrets never enter schemas or persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from integrations.prava.rest import (
    DEFAULT_PRAVA_CHECKOUT_HOSTS,
    PravaHostedRestAdapter,
)

from .errors import ApiProblem, SetupBlocked


class _ProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    prava_base_url: str = Field(default="", validation_alias="PRAVA_BASE_URL")
    prava_secret_key: SecretStr = Field(default=SecretStr(""), validation_alias="PRAVA_SECRET_KEY")
    prava_merchant_url: str = Field(default="", validation_alias="PRAVA_MERCHANT_URL")
    prava_callback_url: str = Field(default="", validation_alias="PRAVA_CALLBACK_URL")
    prava_user_email: str = Field(default="", validation_alias="PRAVA_USER_EMAIL")
    prava_merchant_country: str = Field(default="US", validation_alias="PRAVA_MERCHANT_COUNTRY")
    prava_hosted_checkout_hosts: str = Field(
        default="", validation_alias="PRAVA_HOSTED_CHECKOUT_HOSTS"
    )
    controlled_merchant_base_url: str = Field(
        default="", validation_alias="CONTROLLED_MERCHANT_BASE_URL"
    )
    controlled_merchant_api_key: SecretStr = Field(
        default=SecretStr(""), validation_alias="CONTROLLED_MERCHANT_API_KEY"
    )
    controlled_merchant_id: str = Field(default="", validation_alias="CONTROLLED_MERCHANT_ID")
    web_base_url: str = Field(default="http://localhost:3000", validation_alias="WEB_BASE_URL")


def _https_host(value: str, *, setting: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise SetupBlocked("prava_controlled_merchant", [f"{setting}_VALID_HTTPS_URL"])
    return parsed.hostname.lower()


def _origin(value: str, *, setting: str, require_https: bool) -> tuple[str, int | None]:
    parsed = urlsplit(value)
    allowed_schemes = {"https"} if require_https else {"http", "https"}
    if (
        parsed.scheme.lower() not in allowed_schemes
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ApiProblem(
            code="RETURN_URL_NOT_ALLOWED",
            message=f"{setting} does not contain an allowed web origin.",
            status_code=422,
        )
    return parsed.hostname.lower(), parsed.port


@dataclass(frozen=True, slots=True)
class PravaRuntimeConfiguration:
    base_url: str
    secret_key: str = field(repr=False)
    callback_url: str
    merchant_url: str
    merchant_country: str
    user_email: str
    web_base_url: str
    hosted_checkout_hosts: frozenset[str]

    @classmethod
    def load(cls) -> PravaRuntimeConfiguration:
        settings = _ProviderSettings()
        values = {
            "PRAVA_BASE_URL": settings.prava_base_url.strip(),
            "PRAVA_SECRET_KEY": settings.prava_secret_key.get_secret_value().strip(),
            "PRAVA_MERCHANT_URL": settings.prava_merchant_url.strip(),
            "PRAVA_CALLBACK_URL": settings.prava_callback_url.strip(),
            "PRAVA_USER_EMAIL": settings.prava_user_email.strip(),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise SetupBlocked("prava_controlled_merchant", missing)

        country = settings.prava_merchant_country.strip().upper()
        if len(country) != 2 or not country.isalpha():
            raise SetupBlocked("prava_controlled_merchant", ["PRAVA_MERCHANT_COUNTRY_ISO2"])
        user_email = values["PRAVA_USER_EMAIL"]
        if "@" not in user_email:
            raise SetupBlocked("prava_controlled_merchant", ["PRAVA_USER_EMAIL_VALID"])

        configured_hosts = {
            item.strip().lower()
            for item in settings.prava_hosted_checkout_hosts.split(",")
            if item.strip()
        }
        return cls(
            base_url=values["PRAVA_BASE_URL"],
            secret_key=values["PRAVA_SECRET_KEY"],
            callback_url=values["PRAVA_CALLBACK_URL"],
            merchant_url=values["PRAVA_MERCHANT_URL"],
            merchant_country=country,
            user_email=user_email,
            web_base_url=settings.web_base_url.strip(),
            hosted_checkout_hosts=frozenset(configured_hosts.union(DEFAULT_PRAVA_CHECKOUT_HOSTS)),
        )

    def validate_return_url(self, return_url: str) -> None:
        expected = _origin(self.web_base_url, setting="WEB_BASE_URL", require_https=False)
        local_web_app = expected[0] in {"localhost", "127.0.0.1", "::1"}
        supplied = _origin(return_url, setting="return_url", require_https=not local_web_app)
        if supplied != expected:
            raise ApiProblem(
                code="RETURN_URL_NOT_ALLOWED",
                message="The return URL must use the configured web application origin.",
                status_code=422,
            )

    def validate_merchant_url(self, canonical_merchant_url: str) -> str:
        configured_url = self.merchant_url.rstrip("/")
        canonical_url = canonical_merchant_url.rstrip("/")
        if configured_url != canonical_url:
            raise ApiProblem(
                code="MERCHANT_CHAIN_MISMATCH",
                message="The locked merchant does not match the configured controlled merchant.",
                status_code=409,
            )
        return _https_host(canonical_url, setting="PRAVA_MERCHANT_URL")

    def callback_url_with_state(self, state: str) -> str:
        parsed = urlsplit(self.callback_url)
        query = parse_qsl(parsed.query, keep_blank_values=True)
        if any(key == "state" for key, _value in query):
            raise SetupBlocked(
                "prava_controlled_merchant", ["PRAVA_CALLBACK_URL_WITHOUT_STATE_QUERY"]
            )
        return urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                urlencode([*query, ("state", state)]),
                "",
            )
        )

    def build_adapter(self, *, canonical_merchant_url: str) -> PravaHostedRestAdapter:
        api_host = _https_host(self.base_url, setting="PRAVA_BASE_URL")
        merchant_host = self.validate_merchant_url(canonical_merchant_url)
        callback_host = _https_host(self.callback_url, setting="PRAVA_CALLBACK_URL")
        return PravaHostedRestAdapter(
            secret_key=self.secret_key,
            base_url=self.base_url,
            api_hosts=frozenset({api_host}),
            merchant_hosts=frozenset({merchant_host}),
            callback_hosts=frozenset({callback_host}),
            hosted_checkout_hosts=self.hosted_checkout_hosts,
        )
