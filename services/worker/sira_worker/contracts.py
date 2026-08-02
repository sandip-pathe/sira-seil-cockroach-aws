"""Credential-free Temporal workflow and activity contracts."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import StrEnum
from typing import Any

FORBIDDEN_CREDENTIAL_FIELD_PARTS = frozenset(
    {
        "card",
        "credential",
        "cvv",
        "expiry_month",
        "expiry_year",
        "pan",
        "payment_token",
        "secret",
    }
)


class SafeMerchantOutcome(StrEnum):
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    UNKNOWN = "UNKNOWN"


class SafeFulfillmentStatus(StrEnum):
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_FINAL = "FAILED_FINAL"


class SafeReversalStatus(StrEnum):
    PROVIDER_PENDING = "PROVIDER_PENDING"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    REFUNDED = "REFUNDED"
    REJECTED = "REJECTED"
    COMPENSATION_REQUIRED = "COMPENSATION_REQUIRED"


@dataclass(frozen=True, slots=True)
class IsolatedCheckoutActivityInput:
    """Only durable identifiers needed to load canonical state inside the activity."""

    organization_id: str
    purchase_intent_id: str
    intent_hash: str
    prava_session_id: str
    merchant_adapter_id: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class CheckoutActivityResult:
    purchase_intent_id: str
    prava_session_id: str
    prava_order_id: str
    transaction_reference: str
    merchant_outcome: SafeMerchantOutcome
    merchant_order_id: str | None
    provider_reported: bool
    reconciliation_required: bool


@dataclass(frozen=True, slots=True)
class ReconcileActivityInput:
    organization_id: str
    purchase_intent_id: str
    intent_hash: str
    prava_session_id: str
    merchant_adapter_id: str
    idempotency_key: str
    transaction_reference: str


@dataclass(frozen=True, slots=True)
class VerifyFulfillmentActivityInput:
    organization_id: str
    purchase_intent_id: str
    merchant_order_id: str


@dataclass(frozen=True, slots=True)
class FulfillmentActivityResult:
    purchase_intent_id: str
    status: SafeFulfillmentStatus


@dataclass(frozen=True, slots=True)
class WorkflowFailureActivityInput:
    organization_id: str
    purchase_intent_id: str
    safe_code: str


@dataclass(frozen=True, slots=True)
class RefundActivityInput:
    organization_id: str
    reversal_id: str
    purchase_intent_id: str
    intent_hash: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class RefundActivityResult:
    reversal_id: str
    status: SafeReversalStatus
    refunded_amount: str
    currency: str
    provider_reference: str | None
    entitlements_revoked: bool
    reconciliation_required: bool


@dataclass(frozen=True, slots=True)
class PurchaseReversalWorkflowInput:
    organization_id: str
    reversal_id: str
    purchase_intent_id: str
    intent_hash: str
    idempotency_key: str

    def activity_input(self) -> RefundActivityInput:
        return RefundActivityInput(
            organization_id=self.organization_id,
            reversal_id=self.reversal_id,
            purchase_intent_id=self.purchase_intent_id,
            intent_hash=self.intent_hash,
            idempotency_key=self.idempotency_key,
        )


@dataclass(frozen=True, slots=True)
class PurchaseReversalWorkflowResult:
    reversal_id: str
    status: SafeReversalStatus
    refunded_amount: str
    currency: str
    provider_reference: str | None
    entitlements_revoked: bool
    reconciliation_required: bool


@dataclass(frozen=True, slots=True)
class PurchaseCheckoutWorkflowInput:
    organization_id: str
    purchase_intent_id: str
    intent_hash: str
    prava_session_id: str
    merchant_adapter_id: str
    idempotency_key: str

    def activity_input(self) -> IsolatedCheckoutActivityInput:
        return IsolatedCheckoutActivityInput(
            organization_id=self.organization_id,
            purchase_intent_id=self.purchase_intent_id,
            intent_hash=self.intent_hash,
            prava_session_id=self.prava_session_id,
            merchant_adapter_id=self.merchant_adapter_id,
            idempotency_key=self.idempotency_key,
        )


@dataclass(frozen=True, slots=True)
class PurchaseCheckoutWorkflowResult:
    purchase_intent_id: str
    merchant_outcome: SafeMerchantOutcome
    merchant_order_id: str | None
    provider_reported: bool
    reconciliation_required: bool


def assert_credential_free_contract(value: object) -> None:
    """Fail closed if a Temporal contract ever gains a credential-like field.

    This check is run by both worker registration and the workflow before dispatch.
    It inspects schema names, not values, and therefore cannot print a secret.
    """

    seen: set[int] = set()

    def walk(item: object) -> None:
        item_id = id(item)
        if item_id in seen:
            return
        seen.add(item_id)
        if is_dataclass(item) and not isinstance(item, type):
            for field in fields(item):
                normalized = field.name.lower()
                if any(part in normalized for part in FORBIDDEN_CREDENTIAL_FIELD_PARTS):
                    raise ValueError("Temporal contract contains a prohibited field")
                walk(getattr(item, field.name))
        elif isinstance(item, dict):
            for key, nested in item.items():
                normalized = str(key).lower()
                if any(part in normalized for part in FORBIDDEN_CREDENTIAL_FIELD_PARTS):
                    raise ValueError("Temporal contract contains a prohibited field")
                walk(nested)
        elif isinstance(item, (tuple, list, set, frozenset)):
            for nested in item:
                walk(nested)

    walk(value)


def assert_all_contract_schemas_are_credential_free() -> None:
    """Inspect the dataclass schemas without constructing secret-bearing values."""

    contract_types: tuple[type[Any], ...] = (
        IsolatedCheckoutActivityInput,
        CheckoutActivityResult,
        ReconcileActivityInput,
        VerifyFulfillmentActivityInput,
        FulfillmentActivityResult,
        WorkflowFailureActivityInput,
        PurchaseCheckoutWorkflowInput,
        PurchaseCheckoutWorkflowResult,
        RefundActivityInput,
        RefundActivityResult,
        PurchaseReversalWorkflowInput,
        PurchaseReversalWorkflowResult,
    )
    for contract_type in contract_types:
        for field in fields(contract_type):
            normalized = field.name.lower()
            if any(part in normalized for part in FORBIDDEN_CREDENTIAL_FIELD_PARTS):
                raise RuntimeError("Temporal contract schema contains a prohibited field")
