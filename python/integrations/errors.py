"""Stable, redacted errors emitted by provider adapters."""

from __future__ import annotations

from enum import StrEnum


class ProviderErrorCode(StrEnum):
    CONFIGURATION_INVALID = "PROVIDER_CONFIGURATION_INVALID"
    URL_NOT_ALLOWED = "PROVIDER_URL_NOT_ALLOWED"
    AUTHENTICATION_FAILED = "PROVIDER_AUTHENTICATION_FAILED"
    ACCESS_DENIED = "PROVIDER_ACCESS_DENIED"
    INSUFFICIENT_CREDITS = "PROVIDER_INSUFFICIENT_CREDITS"
    NOT_FOUND = "PROVIDER_NOT_FOUND"
    RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    INVALID_REQUEST = "PROVIDER_INVALID_REQUEST"
    INVALID_STATE = "PROVIDER_INVALID_STATE"
    INVALID_RESPONSE = "PROVIDER_INVALID_RESPONSE"
    PENDING = "PROVIDER_PENDING"
    TIMEOUT = "PROVIDER_TIMEOUT"
    UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    MERCHANT_DECLINED = "MERCHANT_DECLINED"
    CHECKOUT_UNCERTAIN = "MERCHANT_CHECKOUT_UNCERTAIN"
    FIXTURE_ONLY = "DEVELOPMENT_FIXTURE_ONLY"


class ProviderError(RuntimeError):
    """A safe provider failure with no upstream body, headers, URL query, or secret.

    Only fixed metadata is accepted by the constructor.  Original httpx exceptions are
    deliberately not retained as causes because their request objects may contain
    authorization headers or payment data.
    """

    __slots__ = ("code", "operation", "provider", "retryable", "status_code")

    def __init__(
        self,
        *,
        provider: str,
        operation: str,
        code: ProviderErrorCode,
        retryable: bool,
        status_code: int | None = None,
    ) -> None:
        self.provider = provider
        self.operation = operation
        self.code = code
        self.retryable = retryable
        self.status_code = status_code
        super().__init__(f"{provider}.{operation} failed [{code.value}]")

    def __repr__(self) -> str:
        return (
            "ProviderError("
            f"provider={self.provider!r}, operation={self.operation!r}, "
            f"code={self.code.value!r}, retryable={self.retryable!r}, "
            f"status_code={self.status_code!r})"
        )


def raise_for_status(
    status_code: int,
    *,
    provider: str,
    operation: str,
) -> None:
    """Map an HTTP status to a provider-independent code without reading its body."""

    if 200 <= status_code < 300:
        return
    mapping: dict[int, tuple[ProviderErrorCode, bool]] = {
        400: (ProviderErrorCode.INVALID_REQUEST, False),
        401: (ProviderErrorCode.AUTHENTICATION_FAILED, False),
        403: (ProviderErrorCode.ACCESS_DENIED, False),
        402: (ProviderErrorCode.INSUFFICIENT_CREDITS, False),
        404: (ProviderErrorCode.NOT_FOUND, False),
        409: (ProviderErrorCode.INVALID_STATE, False),
        422: (ProviderErrorCode.INVALID_REQUEST, False),
        429: (ProviderErrorCode.RATE_LIMITED, True),
    }
    code, retryable = mapping.get(
        status_code,
        (ProviderErrorCode.UNAVAILABLE, status_code >= 500),
    )
    raise ProviderError(
        provider=provider,
        operation=operation,
        code=code,
        retryable=retryable,
        status_code=status_code,
    ) from None
