"""Short-lived signed identity tickets for isolated SIRA and SEIL runtimes."""

from __future__ import annotations

import base64
import hmac
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import Protocol

import rfc8785
from pydantic import Field, model_validator

from sira_agents.kernel_models import KernelModel, Party, Principal


class RuntimeTicketError(PermissionError):
    """A runtime identity ticket is invalid, expired, or replayed."""


class RuntimeTicketClaims(KernelModel):
    version: int = Field(default=1, ge=1, le=1)
    ticket_id: str = Field(min_length=16, max_length=128)
    principal: Principal
    party: Party
    organization_id: str = Field(min_length=1, max_length=100)
    actor_id: str = Field(min_length=1, max_length=100)
    purpose: str = Field(min_length=1, max_length=100)
    audience: str = Field(min_length=1, max_length=200)
    allowed_tools: tuple[str, ...] = Field(default=(), max_length=32)
    issued_at: datetime
    expires_at: datetime
    nonce: str = Field(min_length=16, max_length=128)

    @model_validator(mode="after")
    def validate_identity(self) -> RuntimeTicketClaims:
        expected_party = Party.BUYER if self.principal is Principal.SIRA else Party.SELLER
        if self.party is not expected_party:
            raise ValueError("runtime ticket principal and party do not match")
        if self.issued_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("runtime ticket timestamps must be timezone-aware")
        if self.expires_at <= self.issued_at:
            raise ValueError("runtime ticket expiry must follow issue time")
        return self


class ReplayGuard(Protocol):
    async def consume(self, ticket_id: str, nonce: str, expires_at: datetime) -> bool: ...


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except Exception as error:
        raise RuntimeTicketError("RUNTIME_TICKET_MALFORMED") from error


@dataclass(frozen=True, slots=True)
class RuntimeTicketCodec:
    signing_key: bytes = field(repr=False)
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC), repr=False)

    def __post_init__(self) -> None:
        if len(self.signing_key) < 32:
            raise ValueError("runtime ticket signing key must contain at least 32 bytes")

    def issue(
        self,
        *,
        principal: Principal,
        party: Party,
        organization_id: str,
        actor_id: str,
        purpose: str,
        audience: str,
        allowed_tools: tuple[str, ...],
        ttl: timedelta = timedelta(minutes=2),
    ) -> str:
        now = self.clock()
        claims = RuntimeTicketClaims(
            ticket_id=f"rtk_{token_urlsafe(24)}",
            principal=principal,
            party=party,
            organization_id=organization_id,
            actor_id=actor_id,
            purpose=purpose,
            audience=audience,
            allowed_tools=allowed_tools,
            issued_at=now,
            expires_at=now + ttl,
            nonce=token_urlsafe(24),
        )
        payload = rfc8785.dumps(claims.model_dump(mode="json"))
        signature = hmac.digest(self.signing_key, payload, sha256)
        return f"{_encode(payload)}.{_encode(signature)}"

    async def verify(
        self,
        token: str,
        *,
        expected_principal: Principal,
        expected_party: Party,
        expected_organization_id: str,
        expected_purpose: str,
        expected_audience: str,
        replay_guard: ReplayGuard,
    ) -> RuntimeTicketClaims:
        try:
            encoded_payload, encoded_signature = token.split(".", 1)
        except ValueError as error:
            raise RuntimeTicketError("RUNTIME_TICKET_MALFORMED") from error
        payload = _decode(encoded_payload)
        supplied_signature = _decode(encoded_signature)
        expected_signature = hmac.digest(self.signing_key, payload, sha256)
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise RuntimeTicketError("RUNTIME_TICKET_SIGNATURE_INVALID")
        try:
            claims = RuntimeTicketClaims.model_validate(json.loads(payload))
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            raise RuntimeTicketError("RUNTIME_TICKET_CLAIMS_INVALID") from error
        now = self.clock()
        if claims.expires_at <= now or claims.issued_at > now + timedelta(seconds=30):
            raise RuntimeTicketError("RUNTIME_TICKET_EXPIRED")
        if (
            claims.principal is not expected_principal
            or claims.party is not expected_party
            or claims.organization_id != expected_organization_id
            or claims.purpose != expected_purpose
            or claims.audience != expected_audience
        ):
            raise RuntimeTicketError("RUNTIME_TICKET_SCOPE_MISMATCH")
        if not await replay_guard.consume(claims.ticket_id, claims.nonce, claims.expires_at):
            raise RuntimeTicketError("RUNTIME_TICKET_REPLAYED")
        return claims


@dataclass(slots=True)
class InMemoryReplayGuard:
    """Deterministic local/test implementation; hosted mode uses CockroachDB."""

    consumed: set[tuple[str, str]] = field(default_factory=set)

    async def consume(self, ticket_id: str, nonce: str, _expires_at: datetime) -> bool:
        key = (ticket_id, nonce)
        if key in self.consumed:
            return False
        self.consumed.add(key)
        return True
