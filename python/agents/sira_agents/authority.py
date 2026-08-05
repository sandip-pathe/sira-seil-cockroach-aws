"""Deterministic authority microkernel for protected agent effects."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


class AuthorityDenied(PermissionError):
    """A protected effect has no exact, live capability grant."""


@dataclass(frozen=True, slots=True)
class Capability:
    id: str
    capability: str
    scope: Mapping[str, Any]
    status: str
    expires_at: datetime
    max_uses: int
    uses: int


def authorize_effect(
    *,
    effect_type: str,
    request_payload: Mapping[str, Any],
    grant: Capability | None,
    now: datetime | None = None,
) -> None:
    """Fail closed unless the grant exactly covers this effect and payload scope."""

    if grant is None:
        raise AuthorityDenied("CAPABILITY_GRANT_REQUIRED")
    current_time = now or datetime.now(UTC)
    if grant.status != "ACTIVE" or grant.expires_at <= current_time:
        raise AuthorityDenied("CAPABILITY_GRANT_INACTIVE")
    if grant.uses >= grant.max_uses:
        raise AuthorityDenied("CAPABILITY_GRANT_CONSUMED")
    if grant.capability != effect_type:
        raise AuthorityDenied("CAPABILITY_TYPE_MISMATCH")
    for key, expected in grant.scope.items():
        if request_payload.get(key) != expected:
            raise AuthorityDenied(f"CAPABILITY_SCOPE_MISMATCH:{key}")
