"""Closed API contracts for the bilateral exchange surface."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from .schemas import Identifier, StrictModel


class ExchangeCaseCreate(StrictModel):
    purchase_request_id: Identifier
    seller_organization_id: Identifier


class ExchangeProjectionView(StrictModel):
    case_id: Identifier
    party: Literal["BUYER", "SELLER"]
    state: Literal[
        "CREATED",
        "REQUIREMENT_RELEASED",
        "EVIDENCE_RELEASED",
        "OFFERED",
        "COUNTERED",
        "AGREED_PENDING_APPROVAL",
        "APPROVED_FOR_HANDOFF",
        "REJECTED",
        "EXPIRED",
    ]
    version: int = Field(ge=1)
    released: dict[str, Any]
    projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ExchangeCaseCreated(StrictModel):
    case_id: Identifier
    route_capability: str = Field(min_length=64, max_length=4096)
    expires_at: datetime
    projection: ExchangeProjectionView
