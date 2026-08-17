"""Server-owned seller organization bindings for cross-company engagements."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]{3,128}$")


@dataclass(frozen=True, slots=True)
class SellerPrincipalBinding:
    candidate_id: str
    product_id: str
    seller_actor_id: str
    seller_organization_id: str
    merchant_name: str
    merchant_url: str

    def __post_init__(self) -> None:
        if not all(
            _IDENTIFIER.fullmatch(value)
            for value in (
                self.candidate_id,
                self.product_id,
                self.seller_actor_id,
                self.seller_organization_id,
            )
        ):
            raise ValueError("seller binding requires safe identifiers")
        if not self.merchant_name.strip() or not self.merchant_url.startswith("https://"):
            raise ValueError("seller binding requires an HTTPS merchant destination")


class SellerOrganizationDirectory(Protocol):
    """Resolve a published candidate to a verified seller principal and tenant."""

    def resolve(self, candidate_id: str) -> SellerPrincipalBinding | None: ...


class StaticSellerOrganizationDirectory:
    """Explicit mapping used only by the labelled development fixture."""

    def __init__(self, bindings: tuple[SellerPrincipalBinding, ...]) -> None:
        if len({item.candidate_id for item in bindings}) != len(bindings):
            raise ValueError("seller directory candidate IDs must be unique")
        self._bindings = {item.candidate_id: item for item in bindings}

    def resolve(self, candidate_id: str) -> SellerPrincipalBinding | None:
        return self._bindings.get(candidate_id)
