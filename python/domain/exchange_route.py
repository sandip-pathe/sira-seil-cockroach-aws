"""Opaque, expiring route capabilities for the two-party coordinator."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime

from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, ConfigDict, Field


class ExchangeRouteError(ValueError):
    """The route token is invalid, expired, or scoped to another participant."""


class ExchangeRoute(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1, max_length=64)
    candidate_id: str = Field(min_length=1, max_length=128)
    product_id: str = Field(min_length=1, max_length=128)
    merchant_name: str = Field(min_length=1, max_length=200)
    merchant_url: str = Field(pattern=r"^https://", max_length=2000)
    buyer_organization_id: str = Field(min_length=1, max_length=64)
    seller_organization_id: str = Field(min_length=1, max_length=64)
    development_guest_organization_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )
    expires_at: datetime


class ExchangeRouteCodec:
    def __init__(self, secret: str) -> None:
        if len(secret.encode("utf-8")) < 32:
            raise ValueError("exchange routing requires at least 32 bytes of secret material")
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
        self._fernet = Fernet(key)

    def encode(self, route: ExchangeRoute) -> str:
        payload = route.model_dump(mode="json")
        return self._fernet.encrypt(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")

    def decode(
        self,
        token: str,
        *,
        organization_id: str,
        now: datetime | None = None,
    ) -> ExchangeRoute:
        try:
            payload = json.loads(self._fernet.decrypt(token.encode("ascii")))
            route = ExchangeRoute.model_validate(payload)
        except (InvalidToken, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as error:
            raise ExchangeRouteError("exchange route is invalid") from error
        current = now or datetime.now(UTC)
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("now must include a timezone")
        if current >= route.expires_at:
            raise ExchangeRouteError("exchange route has expired")
        permitted_organizations = {
            route.buyer_organization_id,
            route.seller_organization_id,
        }
        if route.development_guest_organization_id is not None:
            permitted_organizations.add(route.development_guest_organization_id)
        if organization_id not in permitted_organizations:
            raise ExchangeRouteError("exchange route belongs to another organization")
        return route
