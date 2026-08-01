"""Network egress validation shared by all HTTP provider adapters."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit, urlunsplit

from integrations.errors import ProviderError, ProviderErrorCode


def _normalized_host(host: str) -> str:
    try:
        normalized = host.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError:
        normalized = ""
    if not normalized:
        raise ValueError("invalid host")
    try:
        ipaddress.ip_address(normalized)
    except ValueError:
        pass
    else:
        raise ValueError("IP literal hosts are not allowed")
    if normalized == "localhost" or normalized.endswith(".localhost"):
        raise ValueError("local hosts are not allowed")
    return normalized


@dataclass(frozen=True, slots=True)
class HttpsUrlPolicy:
    """Validate HTTPS URLs against an exact, normalized host allowlist."""

    provider: str
    allowed_hosts: frozenset[str]

    def __post_init__(self) -> None:
        try:
            normalized = frozenset(_normalized_host(host) for host in self.allowed_hosts)
        except ValueError:
            raise ProviderError(
                provider=self.provider,
                operation="configure",
                code=ProviderErrorCode.URL_NOT_ALLOWED,
                retryable=False,
            ) from None
        if not normalized:
            raise ProviderError(
                provider=self.provider,
                operation="configure",
                code=ProviderErrorCode.URL_NOT_ALLOWED,
                retryable=False,
            ) from None
        object.__setattr__(self, "allowed_hosts", normalized)

    def validate(
        self,
        url: str,
        *,
        operation: str,
        allow_query: bool = True,
        allow_fragment: bool = False,
    ) -> str:
        """Return a normalized URL or raise a stable error with no URL echo."""

        try:
            parsed = urlsplit(url)
            if parsed.scheme.lower() != "https":
                raise ValueError("HTTPS is required")
            if parsed.username is not None or parsed.password is not None:
                raise ValueError("userinfo is prohibited")
            if parsed.hostname is None:
                raise ValueError("host is required")
            host = _normalized_host(parsed.hostname)
            if host not in self.allowed_hosts:
                raise ValueError("host is not allowlisted")
            if parsed.port not in (None, 443):
                raise ValueError("only port 443 is allowed")
            if parsed.query and not allow_query:
                raise ValueError("query is not allowed")
            if parsed.fragment and not allow_fragment:
                raise ValueError("fragment is not allowed")
            netloc = host
            normalized = SplitResult(
                scheme="https",
                netloc=netloc,
                path=parsed.path or "",
                query=parsed.query,
                fragment=parsed.fragment,
            )
            return urlunsplit(normalized)
        except (TypeError, ValueError):
            raise ProviderError(
                provider=self.provider,
                operation=operation,
                code=ProviderErrorCode.URL_NOT_ALLOWED,
                retryable=False,
            ) from None


def validate_identifier(value: str, *, provider: str, operation: str) -> str:
    """Allow provider identifiers in URL paths without permitting path injection."""

    if not value or len(value) > 255 or not all(ch.isalnum() or ch in "_-" for ch in value):
        raise ProviderError(
            provider=provider,
            operation=operation,
            code=ProviderErrorCode.INVALID_REQUEST,
            retryable=False,
        ) from None
    return value
