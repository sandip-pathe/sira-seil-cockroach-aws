"""Production identity composition port."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol, cast
from urllib.parse import urlparse

import httpx

IdentityKind = Literal["HUMAN", "SERVICE"]


@dataclass(frozen=True, slots=True)
class VerifiedPrincipal:
    organization_id: str
    actor_id: str
    roles: frozenset[str]
    step_up_verified: bool
    identity_kind: IdentityKind
    party: Literal["BUYER", "SELLER"] | None = None


class IdentityAdapter(Protocol):
    """Verify a bearer token server-side and return tenant-bound authority."""

    async def authenticate(self, bearer_token: str) -> VerifiedPrincipal | None: ...


class IdentityProviderUnavailable(RuntimeError):
    """Safe identity-provider outage signal with no token or secret context."""


_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]{3,128}$")


class IntrospectionIdentityAdapter:
    """Verify opaque/OIDC access tokens with an RFC 7662-compatible endpoint."""

    def __init__(
        self,
        *,
        introspection_url: str,
        client_id: str,
        client_secret: str,
        expected_issuer: str,
        expected_audience: str,
        allowed_roles: frozenset[str],
        step_up_acr_values: frozenset[str] = frozenset(),
        step_up_max_age_seconds: int = 600,
        client: httpx.AsyncClient | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        parsed = urlparse(introspection_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("identity introspection requires an HTTPS endpoint")
        if not client_id or not client_secret or not expected_issuer or not expected_audience:
            raise ValueError("identity introspection configuration is incomplete")
        if not allowed_roles:
            raise ValueError("identity introspection requires an explicit role allowlist")
        if not 60 <= step_up_max_age_seconds <= 3600:
            raise ValueError("identity step-up maximum age must be between 60 and 3600 seconds")
        self._url = introspection_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._issuer = expected_issuer
        self._audience = expected_audience
        self._allowed_roles = allowed_roles
        self._step_up_acr_values = step_up_acr_values
        self._step_up_max_age_seconds = step_up_max_age_seconds
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(5.0))
        self._owns_client = client is None
        self._now = now or (lambda: datetime.now(UTC))

    async def authenticate(self, bearer_token: str) -> VerifiedPrincipal | None:
        if not bearer_token or len(bearer_token) > 8192:
            return None
        response: httpx.Response | None = None
        try:
            response = await self._client.post(
                self._url,
                data={"token": bearer_token, "token_type_hint": "access_token"},
                auth=(self._client_id, self._client_secret),
                headers={"Accept": "application/json"},
            )
        except httpx.HTTPError:
            pass
        if response is None:
            raise IdentityProviderUnavailable("identity provider unavailable") from None
        if response.status_code >= 500:
            raise IdentityProviderUnavailable("identity provider unavailable") from None
        if response.status_code != 200:
            return None
        payload: object = None
        try:
            payload = response.json()
        except ValueError:
            pass
        if payload is None:
            raise IdentityProviderUnavailable(
                "identity provider returned an invalid response"
            ) from None
        if not isinstance(payload, Mapping):
            raise IdentityProviderUnavailable("identity provider returned an invalid response")
        return self._principal(payload)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _principal(self, payload: Mapping[str, object]) -> VerifiedPrincipal | None:
        now = self._now()
        if now.tzinfo is None:
            raise ValueError("identity adapter clock must be timezone-aware")
        if payload.get("active") is not True or payload.get("iss") != self._issuer:
            return None
        if not self._audience_matches(payload.get("aud")):
            return None
        expires_at = self._numeric_date(payload.get("exp"))
        if expires_at is None or expires_at <= now.timestamp():
            return None
        actor_id = payload.get("sub")
        organization_id = payload.get("organization_id")
        identity_kind = payload.get("identity_kind")
        party = payload.get("party")
        if (
            not isinstance(actor_id, str)
            or not _IDENTIFIER.fullmatch(actor_id)
            or not isinstance(organization_id, str)
            or not _IDENTIFIER.fullmatch(organization_id)
            or identity_kind not in {"HUMAN", "SERVICE"}
            or party not in {"BUYER", "SELLER", None}
        ):
            return None
        roles_value = payload.get("roles")
        if not isinstance(roles_value, list) or not all(
            isinstance(role, str) for role in roles_value
        ):
            return None
        claimed_roles = frozenset(roles_value)
        if not claimed_roles.issubset(self._allowed_roles):
            return None
        return VerifiedPrincipal(
            organization_id=organization_id,
            actor_id=actor_id,
            roles=claimed_roles,
            step_up_verified=self._step_up_verified(payload, now),
            identity_kind=cast(IdentityKind, identity_kind),
            party=cast(Literal["BUYER", "SELLER"] | None, party),
        )

    def _audience_matches(self, value: object) -> bool:
        if isinstance(value, str):
            return value == self._audience
        return isinstance(value, list) and all(isinstance(item, str) for item in value) and (
            self._audience in value
        )

    @staticmethod
    def _numeric_date(value: object) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value)

    def _step_up_verified(self, payload: Mapping[str, object], now: datetime) -> bool:
        if not self._step_up_acr_values or payload.get("acr") not in self._step_up_acr_values:
            return False
        authenticated_at = self._numeric_date(payload.get("auth_time"))
        if authenticated_at is None:
            return False
        age = now.timestamp() - authenticated_at
        return 0 <= age <= self._step_up_max_age_seconds
