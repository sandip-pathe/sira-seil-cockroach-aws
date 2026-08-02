"""Production identity composition port."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

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
