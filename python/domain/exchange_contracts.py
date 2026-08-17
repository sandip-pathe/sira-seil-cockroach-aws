"""Immutable disclosure and offer contracts for the bilateral exchange."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .bilateral_exchange import ExchangeParty
from .hashing import content_hash

Hash = str
Participant = Literal[ExchangeParty.BUYER, ExchangeParty.SELLER]


class ContractViolation(ValueError):
    """A disclosure, offer, or approval violates the exchange contract."""


class ReleaseStatus(StrEnum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class OfferApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVOKED = "REVOKED"
    SUPERSEDED = "SUPERSEDED"


class ExchangeHandoffStatus(StrEnum):
    READY = "READY"
    OPENED = "OPENED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")


def _participant(value: ExchangeParty, name: str) -> None:
    if value is ExchangeParty.SYSTEM:
        raise ValueError(f"{name} must be BUYER or SELLER")


def _private_key(key: str) -> bool:
    normalized = key.casefold().replace("-", "_")
    return any(
        marker in normalized
        for marker in (
            "hidden_budget",
            "reservation_value",
            "seller_floor",
            "private_note",
            "private_source",
            "buyer_private",
            "seller_private",
        )
    )


def _assert_public_tree(value: object) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if _private_key(str(key)):
                raise ContractViolation("private-plane data cannot enter an exchange contract")
            _assert_public_tree(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _assert_public_tree(child)


class ReleaseManifest(ContractModel):
    """Exact authorization for one directional, purpose-bound disclosure."""

    schema_version: Literal["release-manifest.v1"] = "release-manifest.v1"
    manifest_id: str = Field(min_length=1, max_length=64)
    case_id: str = Field(min_length=1, max_length=64)
    owner: ExchangeParty
    recipient: ExchangeParty
    purpose: str = Field(min_length=1, max_length=240)
    fields: tuple[str, ...] = Field(min_length=1)
    transformations: dict[str, Literal["IDENTITY", "LOWERCASE", "REDACT"]]
    source_versions: dict[str, int] = Field(min_length=1)
    expires_at: datetime
    approval_id: str = Field(min_length=1, max_length=64)
    approved_payload_hash: Hash = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    status: ReleaseStatus = ReleaseStatus.ACTIVE
    manifest_hash: Hash = ""

    @model_validator(mode="after")
    def validate_contract(self) -> ReleaseManifest:
        _participant(self.owner, "owner")
        _participant(self.recipient, "recipient")
        if self.owner is self.recipient:
            raise ValueError("release recipient must be the other exchange party")
        _require_aware(self.expires_at, "expires_at")
        if len(set(self.fields)) != len(self.fields):
            raise ValueError("release fields must be unique")
        if any(not field or "." in field or _private_key(field) for field in self.fields):
            raise ValueError("release fields must be safe top-level field names")
        if set(self.transformations) - set(self.fields):
            raise ValueError("transformations may reference only released fields")
        if any(version < 1 for version in self.source_versions.values()):
            raise ValueError("source versions must be positive")
        expected_approval_hash = content_hash(self.approval_payload())
        if self.approved_payload_hash != expected_approval_hash:
            raise ValueError("release approval does not bind the exact disclosure payload")
        expected_manifest_hash = content_hash(self.hash_payload())
        if self.manifest_hash and self.manifest_hash != expected_manifest_hash:
            raise ValueError("manifest_hash does not match the canonical manifest")
        object.__setattr__(self, "manifest_hash", expected_manifest_hash)
        return self

    def approval_payload(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "owner": self.owner,
            "recipient": self.recipient,
            "purpose": self.purpose,
            "fields": self.fields,
            "transformations": self.transformations,
            "source_versions": self.source_versions,
            "expires_at": self.expires_at,
        }

    def hash_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "manifest_id": self.manifest_id,
            **self.approval_payload(),
            "approval_id": self.approval_id,
            "approved_payload_hash": self.approved_payload_hash,
            "status": self.status,
        }

    def release(self, source: dict[str, Any], *, now: datetime) -> dict[str, Any]:
        _require_aware(now, "now")
        if self.status is not ReleaseStatus.ACTIVE:
            raise ContractViolation("release authorization has been revoked")
        if now >= self.expires_at:
            raise ContractViolation("release authorization has expired")
        missing = set(self.fields) - set(source)
        if missing:
            raise ContractViolation(f"release source is missing approved fields: {sorted(missing)}")
        selected: dict[str, Any] = {}
        for field in self.fields:
            value = source[field]
            transform = self.transformations.get(field, "IDENTITY")
            if transform == "LOWERCASE":
                if not isinstance(value, str):
                    raise ContractViolation("LOWERCASE transformation requires text")
                value = value.lower()
            elif transform == "REDACT":
                value = "[redacted]"
            selected[field] = value
        _assert_public_tree(selected)
        return selected

    def revoke(self) -> ReleaseManifest:
        if self.status is ReleaseStatus.REVOKED:
            return self
        return ReleaseManifest.model_validate(
            {**self.model_dump(), "status": ReleaseStatus.REVOKED, "manifest_hash": ""}
        )


class ExchangeEnvelope(ContractModel):
    schema_version: Literal["exchange-envelope.v1"] = "exchange-envelope.v1"
    envelope_id: str = Field(min_length=1, max_length=64)
    case_id: str = Field(min_length=1, max_length=64)
    sender: ExchangeParty
    recipient: ExchangeParty
    sequence: int = Field(ge=1)
    causation_id: str = Field(min_length=1, max_length=64)
    manifest_hash: Hash = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    payload: dict[str, Any]
    expires_at: datetime
    payload_hash: Hash = ""

    @model_validator(mode="after")
    def validate_envelope(self) -> ExchangeEnvelope:
        _participant(self.sender, "sender")
        _participant(self.recipient, "recipient")
        if self.sender is self.recipient:
            raise ValueError("exchange envelope must cross parties")
        _require_aware(self.expires_at, "expires_at")
        _assert_public_tree(self.payload)
        expected = content_hash(self.hash_payload())
        if self.payload_hash and self.payload_hash != expected:
            raise ValueError("payload_hash does not match the exchange envelope")
        object.__setattr__(self, "payload_hash", expected)
        return self

    def hash_payload(self) -> dict[str, Any]:
        return self.model_dump(exclude={"payload_hash"})


class ExchangeReceipt(ContractModel):
    receipt_id: str = Field(min_length=1, max_length=64)
    envelope_id: str = Field(min_length=1, max_length=64)
    case_id: str = Field(min_length=1, max_length=64)
    recipient: ExchangeParty
    envelope_hash: Hash = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    received_at: datetime

    @model_validator(mode="after")
    def validate_receipt(self) -> ExchangeReceipt:
        _participant(self.recipient, "recipient")
        _require_aware(self.received_at, "received_at")
        return self


class OfferLine(ContractModel):
    item_id: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=240)
    quantity: int = Field(ge=1)
    unit_price: Decimal = Field(ge=Decimal("0"), max_digits=20, decimal_places=2)

    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * self.quantity


class OfferVersion(ContractModel):
    """One immutable commercial proposal; accepted offers are never edited."""

    schema_version: Literal["offer.v1"] = "offer.v1"
    offer_id: str = Field(min_length=1, max_length=64)
    case_id: str = Field(min_length=1, max_length=64)
    version: int = Field(ge=1)
    proposer: ExchangeParty
    recipient: ExchangeParty
    predecessor_hash: Hash | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    changed_terms: tuple[str, ...]
    rationale: str = Field(min_length=1, max_length=1000)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    lines: tuple[OfferLine, ...] = Field(min_length=1)
    total: Decimal = Field(ge=Decimal("0"), max_digits=20, decimal_places=2)
    expires_at: datetime
    requirement_hash: Hash = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    evidence_hash: Hash = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    approval_status: OfferApprovalStatus = OfferApprovalStatus.PENDING
    offer_hash: Hash = ""

    @model_validator(mode="after")
    def validate_offer(self) -> OfferVersion:
        _participant(self.proposer, "proposer")
        _participant(self.recipient, "recipient")
        if self.proposer is self.recipient:
            raise ValueError("offer recipient must be the other exchange party")
        _require_aware(self.expires_at, "expires_at")
        if self.version == 1 and self.predecessor_hash is not None:
            raise ValueError("initial offer cannot have a predecessor")
        if self.version > 1 and self.predecessor_hash is None:
            raise ValueError("counteroffer must bind its predecessor")
        if self.version > 1 and not self.changed_terms:
            raise ValueError("counteroffer must name changed terms")
        if len(set(self.changed_terms)) != len(self.changed_terms):
            raise ValueError("changed terms must be unique")
        if len({line.item_id for line in self.lines}) != len(self.lines):
            raise ValueError("offer line item ids must be unique")
        if sum((line.subtotal for line in self.lines), Decimal("0")) != self.total:
            raise ValueError("offer total does not equal line-item arithmetic")
        expected = content_hash(self.hash_payload())
        if self.offer_hash and self.offer_hash != expected:
            raise ValueError("offer_hash does not match the canonical offer")
        object.__setattr__(self, "offer_hash", expected)
        return self

    def hash_payload(self) -> dict[str, Any]:
        # Approval lifecycle is a separate event stream. It must not change the
        # identity of the exact commercial terms being approved.
        return self.model_dump(exclude={"offer_hash", "approval_status"})

    def assert_actionable(self, *, actor: ExchangeParty, now: datetime) -> None:
        _require_aware(now, "now")
        if actor is not self.recipient:
            raise ContractViolation("only the current recipient may accept this offer")
        if now >= self.expires_at:
            raise ContractViolation("offer has expired")
        if self.approval_status is not OfferApprovalStatus.PENDING:
            raise ContractViolation("offer is not pending")


class OfferApproval(ContractModel):
    approval_id: str = Field(min_length=1, max_length=64)
    case_id: str = Field(min_length=1, max_length=64)
    offer_hash: Hash = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    approver_id: str = Field(min_length=1, max_length=100)
    approved_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def validate_approval(self) -> OfferApproval:
        _require_aware(self.approved_at, "approved_at")
        _require_aware(self.expires_at, "expires_at")
        if self.expires_at <= self.approved_at:
            raise ValueError("offer approval must expire after approval")
        return self

    def authorize(self, offer: OfferVersion, *, now: datetime) -> OfferVersion:
        _require_aware(now, "now")
        if self.case_id != offer.case_id or self.offer_hash != offer.offer_hash:
            raise ContractViolation("approval does not bind the current exact offer")
        if now >= self.expires_at or now >= offer.expires_at:
            raise ContractViolation("offer or approval has expired")
        if offer.approval_status is not OfferApprovalStatus.PENDING:
            raise ContractViolation("offer is not pending approval")
        return OfferVersion.model_validate(
            {
                **offer.model_dump(),
                "approval_status": OfferApprovalStatus.APPROVED,
                "offer_hash": "",
            }
        )


class ExchangePaymentHandoff(ContractModel):
    """Provider-neutral external payment context bound to an approved offer."""

    schema_version: Literal["exchange-handoff.v1"] = "exchange-handoff.v1"
    handoff_id: str = Field(min_length=1, max_length=64)
    case_id: str = Field(min_length=1, max_length=64)
    offer_hash: Hash = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    approval_hash: Hash = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    destination_url: str = Field(min_length=1, max_length=2000)
    recipient: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(ge=Decimal("0"), max_digits=20, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    reference: str = Field(min_length=1, max_length=160)
    created_at: datetime
    expires_at: datetime
    status: ExchangeHandoffStatus = ExchangeHandoffStatus.READY
    opened_at: datetime | None = None
    handoff_hash: Hash = ""

    @model_validator(mode="after")
    def validate_handoff(self) -> ExchangePaymentHandoff:
        destination = urlsplit(self.destination_url)
        if (
            destination.scheme != "https"
            or not destination.hostname
            or destination.username is not None
            or destination.password is not None
            or destination.fragment
        ):
            raise ValueError(
                "exchange handoff destination must be HTTPS without credentials or fragment"
            )
        _require_aware(self.created_at, "created_at")
        _require_aware(self.expires_at, "expires_at")
        if self.expires_at <= self.created_at:
            raise ValueError("exchange handoff must expire after creation")
        if self.opened_at is not None:
            _require_aware(self.opened_at, "opened_at")
        if self.status is ExchangeHandoffStatus.OPENED and self.opened_at is None:
            raise ValueError("opened exchange handoff requires opened_at")
        if self.status is not ExchangeHandoffStatus.OPENED and self.opened_at is not None:
            raise ValueError("only an opened exchange handoff may have opened_at")
        expected = content_hash(self.hash_payload())
        if self.handoff_hash and self.handoff_hash != expected:
            raise ValueError("handoff_hash does not match the canonical exchange handoff")
        object.__setattr__(self, "handoff_hash", expected)
        return self

    def hash_payload(self) -> dict[str, Any]:
        return self.model_dump(exclude={"status", "opened_at", "handoff_hash"})

    def open(self, *, now: datetime) -> ExchangePaymentHandoff:
        _require_aware(now, "now")
        if self.status is ExchangeHandoffStatus.OPENED:
            return self
        if self.status is not ExchangeHandoffStatus.READY or now >= self.expires_at:
            raise ContractViolation("exchange handoff is not openable")
        return ExchangePaymentHandoff.model_validate(
            {
                **self.model_dump(),
                "status": ExchangeHandoffStatus.OPENED,
                "opened_at": now,
                "handoff_hash": "",
            }
        )


def validate_counteroffer(previous: OfferVersion, current: OfferVersion) -> None:
    if current.case_id != previous.case_id or current.offer_id != previous.offer_id:
        raise ContractViolation("counteroffer targets another negotiation")
    if current.version != previous.version + 1:
        raise ContractViolation("counteroffer version is not sequential")
    if current.predecessor_hash != previous.offer_hash:
        raise ContractViolation("counteroffer does not bind the current offer")
    if current.proposer is not previous.recipient or current.recipient is not previous.proposer:
        raise ContractViolation("counteroffer parties do not alternate")
    actual_changes: set[str] = set()
    for name in ("currency", "lines", "total", "requirement_hash", "evidence_hash"):
        if getattr(previous, name) != getattr(current, name):
            actual_changes.add(name)
    if set(current.changed_terms) != actual_changes:
        raise ContractViolation("changed_terms does not exactly describe the counteroffer")


def utc_now() -> datetime:
    """Injectable default for callers that do not already own a clock."""

    return datetime.now(UTC)
