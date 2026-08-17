"""Closed API contracts for the bilateral exchange surface."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field

from .schemas import Identifier, StrictModel


class ExchangeCaseCreate(StrictModel):
    purchase_request_id: Identifier
    candidate_id: Identifier


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


class ExchangeEvidencePublish(StrictModel):
    expected_version: int = Field(ge=1)
    summary: str = Field(min_length=1, max_length=500)
    published_span_ids: list[Identifier] = Field(default_factory=list, max_length=64)


class ExchangeOfferLineInput(StrictModel):
    item_id: Identifier
    description: str = Field(min_length=1, max_length=240)
    quantity: int = Field(ge=1, le=1_000_000)
    unit_price: Decimal = Field(ge=0, max_digits=20, decimal_places=2)


class ExchangeOfferCreate(StrictModel):
    expected_version: int = Field(ge=1)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    lines: list[ExchangeOfferLineInput] = Field(min_length=1, max_length=100)
    total: Decimal = Field(ge=0, max_digits=20, decimal_places=2)
    rationale: str = Field(min_length=1, max_length=1000)
    changed_terms: list[str] = Field(default_factory=list, max_length=16)
    expires_at: datetime


class ExchangeOfferAccept(StrictModel):
    expected_version: int = Field(ge=1)
    offer_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ExchangeOfferApprove(StrictModel):
    expected_version: int = Field(ge=1)
    offer_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    approval_expires_at: datetime
