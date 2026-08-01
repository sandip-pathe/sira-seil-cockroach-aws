"""Strict value objects for the first deterministic commerce vertical."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from .enums import ApprovalStatus
from .errors import DomainValidationError
from .hashing import content_hash
from .money import Money

_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def require_id(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise DomainValidationError(f"{field_name} must be a stable non-empty identifier")


def require_hash(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise DomainValidationError(f"{field_name} must be a sha256 content hash")


def require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DomainValidationError(f"{field_name} must be timezone-aware")


def deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): deep_freeze(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(deep_freeze(item) for item in value)
    if isinstance(value, set | frozenset):
        return frozenset(deep_freeze(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class SourceRef:
    provider: str
    content_id: str
    version_id: str
    fragment_hash: str
    retrieved_at: datetime
    fragment_ordinal: int | None = None

    def __post_init__(self) -> None:
        require_id(self.provider, "provider")
        require_id(self.content_id, "content_id")
        require_id(self.version_id, "version_id")
        require_hash(self.fragment_hash, "fragment_hash")
        require_aware(self.retrieved_at, "retrieved_at")
        if self.fragment_ordinal is not None and self.fragment_ordinal < 0:
            raise DomainValidationError("fragment_ordinal cannot be negative")


@dataclass(frozen=True, slots=True)
class Verification:
    status: str
    method: str
    verified_by: str | None
    verified_at: datetime | None
    scope: str = "fact_only"

    def __post_init__(self) -> None:
        allowed = {"unverified", "verified", "human_approved", "disputed", "expired", "revoked"}
        if self.status not in allowed:
            raise DomainValidationError("unsupported verification status")
        if not self.method:
            raise DomainValidationError("verification method is required")
        if self.status in {"verified", "human_approved"}:
            if not self.verified_by or self.verified_at is None:
                raise DomainValidationError("verified facts require verifier and timestamp")
        if self.verified_at is not None:
            require_aware(self.verified_at, "verified_at")


@dataclass(frozen=True, slots=True)
class BuyerFact:
    fact_id: str
    organization_id: str
    subject_type: str
    subject_id: str
    field: str
    operator: str
    value: Any
    kind: str
    stakeholder_role: str
    source: SourceRef
    verification: Verification
    valid_from: datetime
    valid_until: datetime | None
    sensitivity: str
    confidence: str

    def __post_init__(self) -> None:
        require_id(self.fact_id, "fact_id")
        require_id(self.organization_id, "organization_id")
        require_id(self.subject_id, "subject_id")
        if not self.subject_type or not self.field or not self.operator:
            raise DomainValidationError("fact subject, field, and operator are required")
        if self.kind not in {"hard_constraint", "preference", "observation", "authority"}:
            raise DomainValidationError("unsupported buyer fact kind")
        if self.confidence not in {"confirmed", "measured", "inferred", "unknown"}:
            raise DomainValidationError("unsupported confidence")
        require_aware(self.valid_from, "valid_from")
        if self.valid_until is not None:
            require_aware(self.valid_until, "valid_until")
            if self.valid_until <= self.valid_from:
                raise DomainValidationError("valid_until must be after valid_from")
        object.__setattr__(self, "value", deep_freeze(self.value))
        if self.kind == "hard_constraint" and self.verification.status not in {
            "verified",
            "human_approved",
        }:
            raise DomainValidationError("hard constraints require verified or owner-approved facts")

    def is_current(self, at: datetime | None = None) -> bool:
        point = at or datetime.now(UTC)
        require_aware(point, "at")
        return self.valid_from <= point and (self.valid_until is None or point < self.valid_until)


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    evidence_id: str
    claim_id: str
    source: SourceRef
    assertion_source: str
    visibility: str
    verification_method: str
    verification_scope: str
    verification_state: str
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        require_id(self.evidence_id, "evidence_id")
        require_id(self.claim_id, "claim_id")
        if self.verification_state not in {
            "unverified",
            "verified",
            "disputed",
            "expired",
            "revoked",
        }:
            raise DomainValidationError("unsupported evidence verification state")
        if self.expires_at is not None:
            require_aware(self.expires_at, "expires_at")


@dataclass(frozen=True, slots=True)
class MerchantIdentity:
    merchant_id: str
    name: str
    url: str
    country: str

    def __post_init__(self) -> None:
        require_id(self.merchant_id, "merchant_id")
        if not self.name:
            raise DomainValidationError("merchant name is required")
        if not self.url.startswith("https://"):
            raise DomainValidationError("merchant URL must use HTTPS")
        if len(self.country) != 2 or not self.country.isalpha() or not self.country.isupper():
            raise DomainValidationError("merchant country must be ISO alpha-2")


@dataclass(frozen=True, slots=True)
class ExpectedFulfillment:
    fulfillment_item_id: str
    line_item_id: str
    type: str
    subject_type: str
    required: bool
    minimum_quantity: int
    expected_quantity: int
    verification_method: str

    def __post_init__(self) -> None:
        require_id(self.fulfillment_item_id, "fulfillment_item_id")
        require_id(self.line_item_id, "line_item_id")
        if not self.type or not self.subject_type or not self.verification_method:
            raise DomainValidationError("fulfillment type, subject, and verification are required")
        if self.minimum_quantity < 0 or self.expected_quantity < self.minimum_quantity:
            raise DomainValidationError("fulfillment quantities are inconsistent")
        if self.required and self.minimum_quantity < 1:
            raise DomainValidationError("required fulfillment needs a positive minimum")


@dataclass(frozen=True, slots=True)
class PurchaseIntent:
    """An immutable, exact purchase authority payload."""

    schema_version: str
    purchase_intent_id: str
    organization_id: str
    decision_id: str
    decision_hash: str
    solution_plan_id: str
    procurement_plan_id: str
    procurement_gate_result_hash: str
    pack_id: str
    pack_version: int
    offer_id: str
    offer_version: int
    quote_id: str
    quote_expires_at: datetime
    merchant: MerchantIdentity
    approved_merchant_chain_id: str
    amount: Money
    line_items: tuple[Mapping[str, Any], ...]
    expected_fulfillments: tuple[ExpectedFulfillment, ...]
    approval_policy_version: int
    approval_plan_hash: str
    buyer_legal_entity_id: str
    seller_contracting_entity_id: str
    billing_identity_id: str
    cost_center_id: str
    contract_version_id: str
    intent_hash: str = field(default="", compare=True)

    def __post_init__(self) -> None:
        for field_name in (
            "purchase_intent_id",
            "organization_id",
            "decision_id",
            "solution_plan_id",
            "procurement_plan_id",
            "pack_id",
            "offer_id",
            "quote_id",
            "approved_merchant_chain_id",
            "buyer_legal_entity_id",
            "seller_contracting_entity_id",
            "billing_identity_id",
            "cost_center_id",
            "contract_version_id",
        ):
            require_id(getattr(self, field_name), field_name)
        require_hash(self.decision_hash, "decision_hash")
        require_hash(self.procurement_gate_result_hash, "procurement_gate_result_hash")
        require_hash(self.approval_plan_hash, "approval_plan_hash")
        require_aware(self.quote_expires_at, "quote_expires_at")
        if self.pack_version < 1 or self.offer_version < 1 or self.approval_policy_version < 1:
            raise DomainValidationError("artifact versions must be positive")
        if not self.schema_version:
            raise DomainValidationError("schema_version is required")
        object.__setattr__(self, "line_items", tuple(deep_freeze(item) for item in self.line_items))
        object.__setattr__(self, "expected_fulfillments", tuple(self.expected_fulfillments))
        if not self.line_items or not self.expected_fulfillments:
            raise DomainValidationError(
                "a purchase intent needs line items and expected fulfillment"
            )
        computed = content_hash(self.to_hash_payload())
        if self.intent_hash:
            require_hash(self.intent_hash, "intent_hash")
            if self.intent_hash != computed:
                raise DomainValidationError("intent_hash does not match the canonical payload")
        else:
            object.__setattr__(self, "intent_hash", computed)

    def to_hash_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "purchase_intent_id": self.purchase_intent_id,
            "organization_id": self.organization_id,
            "decision_id": self.decision_id,
            "decision_hash": self.decision_hash,
            "solution_plan_id": self.solution_plan_id,
            "procurement_plan_id": self.procurement_plan_id,
            "procurement_gate_result_hash": self.procurement_gate_result_hash,
            "pack_id": self.pack_id,
            "pack_version": self.pack_version,
            "offer_id": self.offer_id,
            "offer_version": self.offer_version,
            "quote_id": self.quote_id,
            "quote_expires_at": self.quote_expires_at,
            "merchant": self.merchant,
            "approved_merchant_chain_id": self.approved_merchant_chain_id,
            "amount": self.amount,
            "line_items": self.line_items,
            "expected_fulfillments": self.expected_fulfillments,
            "approval_policy_version": self.approval_policy_version,
            "approval_plan_hash": self.approval_plan_hash,
            "buyer_legal_entity_id": self.buyer_legal_entity_id,
            "seller_contracting_entity_id": self.seller_contracting_entity_id,
            "billing_identity_id": self.billing_identity_id,
            "cost_center_id": self.cost_center_id,
            "contract_version_id": self.contract_version_id,
        }


@dataclass(frozen=True, slots=True)
class ApprovalBinding:
    approval_request_id: str
    intent_hash: str
    status: ApprovalStatus

    def __post_init__(self) -> None:
        require_id(self.approval_request_id, "approval_request_id")
        require_hash(self.intent_hash, "intent_hash")
