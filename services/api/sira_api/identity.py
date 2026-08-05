"""Production identity composition port."""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol, cast
from urllib.parse import urlparse

import httpx
import jwt
from cryptography import x509
from jwt import InvalidTokenError

IdentityKind = Literal["HUMAN", "SERVICE"]


@dataclass(frozen=True, slots=True)
class VerifiedPrincipal:
    organization_id: str
    actor_id: str
    roles: frozenset[str]
    step_up_verified: bool
    identity_kind: IdentityKind
    party: Literal["BUYER", "SELLER"] | None = None
    firebase_identity: bool = False
    anonymous: bool = False
    verified_identity: bool = True


class IdentityAdapter(Protocol):
    """Verify a bearer token server-side and return tenant-bound authority."""

    async def authenticate(self, bearer_token: str) -> VerifiedPrincipal | None: ...


class IdentityProviderUnavailable(RuntimeError):
    """Safe identity-provider outage signal with no token or secret context."""


_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]{3,128}$")


class FirebaseIdentityAdapter:
    """Verify Firebase ID tokens against Google's rotating public certificates."""

    _CERTIFICATES_URL = (
        "https://www.googleapis.com/robot/v1/metadata/x509/"
        "securetoken@system.gserviceaccount.com"
    )

    def __init__(
        self,
        *,
        project_id: str,
        step_up_max_age_seconds: int = 600,
        client: httpx.AsyncClient | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if not _IDENTIFIER.fullmatch(project_id):
            raise ValueError("Firebase project ID is invalid")
        self._project_id = project_id
        self._issuer = f"https://securetoken.google.com/{project_id}"
        self._step_up_max_age_seconds = step_up_max_age_seconds
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(5.0))
        self._owns_client = client is None
        self._now = now or (lambda: datetime.now(UTC))
        self._certificates: dict[str, str] = {}
        self._certificates_expire_at = 0.0
        self._certificate_lock = asyncio.Lock()

    async def authenticate(self, bearer_token: str) -> VerifiedPrincipal | None:
        if not bearer_token or len(bearer_token) > 8192:
            return None
        try:
            header = jwt.get_unverified_header(bearer_token)
        except InvalidTokenError:
            return None
        key_id = header.get("kid")
        if header.get("alg") != "RS256" or not isinstance(key_id, str) or len(key_id) > 256:
            return None
        certificate = await self._certificate(key_id)
        if certificate is None:
            return None
        try:
            public_key = x509.load_pem_x509_certificate(certificate.encode()).public_key()
            payload = jwt.decode(
                bearer_token,
                key=public_key,
                algorithms=["RS256"],
                audience=self._project_id,
                issuer=self._issuer,
                leeway=30,
                options={"require": ["aud", "auth_time", "exp", "iat", "iss", "sub"]},
            )
        except (InvalidTokenError, ValueError):
            return None
        return self._principal(payload)

    async def _certificate(self, key_id: str) -> str | None:
        now = time.time()
        if now < self._certificates_expire_at and key_id in self._certificates:
            return self._certificates[key_id]
        async with self._certificate_lock:
            now = time.time()
            if now < self._certificates_expire_at and key_id in self._certificates:
                return self._certificates[key_id]
            try:
                response = await self._client.get(
                    self._CERTIFICATES_URL, headers={"Accept": "application/json"}
                )
            except httpx.HTTPError:
                raise IdentityProviderUnavailable("Firebase certificates unavailable") from None
            if response.status_code != 200:
                raise IdentityProviderUnavailable("Firebase certificates unavailable")
            try:
                payload = response.json()
            except ValueError:
                raise IdentityProviderUnavailable("Firebase certificates invalid") from None
            if not isinstance(payload, dict) or not all(
                isinstance(item, str) and isinstance(value, str)
                for item, value in payload.items()
            ):
                raise IdentityProviderUnavailable("Firebase certificates invalid")
            cache_control = response.headers.get("cache-control", "")
            match = re.search(r"(?:^|,)\s*max-age=(\d+)", cache_control)
            max_age = int(match.group(1)) if match else 300
            self._certificates = payload
            self._certificates_expire_at = now + max(60, min(max_age, 86_400))
            return self._certificates.get(key_id)

    def _principal(self, payload: Mapping[str, object]) -> VerifiedPrincipal | None:
        uid = payload.get("sub")
        firebase = payload.get("firebase")
        authenticated_at = payload.get("auth_time")
        if (
            not isinstance(uid, str)
            or not uid
            or len(uid) > 128
            or not isinstance(firebase, Mapping)
            or isinstance(authenticated_at, bool)
            or not isinstance(authenticated_at, (int, float))
        ):
            return None
        provider = firebase.get("sign_in_provider")
        if not isinstance(provider, str):
            return None
        anonymous = provider == "anonymous"
        email_verified = payload.get("email_verified") is True
        verified_identity = not anonymous and (provider != "password" or email_verified)
        digest = hashlib.sha256(f"{self._project_id}:{uid}".encode()).hexdigest()
        now = self._now()
        auth_age = now.timestamp() - float(authenticated_at)
        return VerifiedPrincipal(
            organization_id=(
                f"org_guest_{digest[:24]}" if anonymous else f"org_user_{digest[:24]}"
            ),
            actor_id=f"usr_{digest[:24]}",
            roles=frozenset(),
            step_up_verified=(
                verified_identity and 0 <= auth_age <= self._step_up_max_age_seconds
            ),
            identity_kind="HUMAN",
            party=None,
            firebase_identity=True,
            anonymous=anonymous,
            verified_identity=verified_identity,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


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
        return (
            isinstance(value, list)
            and all(isinstance(item, str) for item in value)
            and (self._audience in value)
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
