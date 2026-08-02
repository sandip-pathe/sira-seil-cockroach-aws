"""Credential-free merchant checkout and fulfillment models."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from integrations.common import AdapterDescriptor


def _validate_amount(value: str) -> None:
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("amount must be a decimal string") from exc
    exponent = amount.as_tuple().exponent
    if not amount.is_finite() or amount <= 0 or not isinstance(exponent, int) or exponent < -2:
        raise ValueError("amount must be positive with at most two decimal places")


class MerchantOutcome(StrEnum):
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    UNKNOWN = "UNKNOWN"


class EntitlementVerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_FINAL = "FAILED_FINAL"


class RefundOutcomeStatus(StrEnum):
    PENDING = "PENDING"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    REFUNDED = "REFUNDED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class MerchantCheckoutRequest:
    purchase_intent_id: str
    prava_order_id: str
    idempotency_key: str
    merchant_url: str
    amount: str
    currency: str

    def __post_init__(self) -> None:
        if not self.purchase_intent_id or not self.prava_order_id or not self.idempotency_key:
            raise ValueError("purchase intent, Prava order, and idempotency key are required")
        _validate_amount(self.amount)
        if len(self.currency) != 3 or not self.currency.isalpha() or not self.currency.isupper():
            raise ValueError("currency must be an uppercase ISO 4217 code")


@dataclass(frozen=True, slots=True)
class MerchantCheckoutOutcome:
    """Safe checkout result.  Payment credentials can never be represented here."""

    outcome: MerchantOutcome
    merchant_order_id: str | None
    authorization_code: str | None
    response_code: str | None
    adapter: AdapterDescriptor
    provider_confirmed: bool

    def __post_init__(self) -> None:
        if self.outcome is MerchantOutcome.APPROVED and not self.merchant_order_id:
            raise ValueError("approved checkout requires a merchant order id")
        if self.adapter.mode.value == "development_fixture" and self.provider_confirmed:
            raise ValueError("development fixtures cannot confirm a production checkout")


@dataclass(frozen=True, slots=True)
class EntitlementVerificationRequest:
    merchant_order_id: str
    entitlement_type: str
    minimum_quantity: int
    subject_id: str | None = None
    product_id: str | None = None
    product_version: str | None = None
    region: str | None = None
    scope: str | None = None
    require_access_probe: bool = False

    def __post_init__(self) -> None:
        if not self.merchant_order_id or not self.entitlement_type:
            raise ValueError("merchant order and entitlement type are required")
        if self.minimum_quantity < 1:
            raise ValueError("minimum_quantity must be positive")


@dataclass(frozen=True, slots=True)
class EntitlementVerificationResult:
    status: EntitlementVerificationStatus
    observed_quantity: int
    external_entitlement_ids: tuple[str, ...]
    access_probe_verified: bool
    adapter: AdapterDescriptor
    provider_confirmed: bool

    def __post_init__(self) -> None:
        if self.observed_quantity < 0:
            raise ValueError("observed_quantity must not be negative")
        if self.adapter.mode.value == "development_fixture" and self.provider_confirmed:
            raise ValueError("development fixtures cannot confirm production fulfillment")


@dataclass(frozen=True, slots=True)
class MerchantRefundRequest:
    merchant_order_id: str
    idempotency_key: str
    amount: str
    currency: str
    reason_code: str

    def __post_init__(self) -> None:
        if not self.merchant_order_id or not self.idempotency_key or not self.reason_code:
            raise ValueError("merchant order, idempotency key, and reason code are required")
        _validate_amount(self.amount)
        if len(self.currency) != 3 or not self.currency.isalpha() or not self.currency.isupper():
            raise ValueError("currency must be an uppercase ISO 4217 code")


@dataclass(frozen=True, slots=True)
class MerchantRefundResult:
    status: RefundOutcomeStatus
    provider_refund_id: str | None
    refunded_amount: str
    currency: str
    entitlements_revoked: bool
    adapter: AdapterDescriptor
    provider_confirmed: bool

    def __post_init__(self) -> None:
        try:
            amount = Decimal(self.refunded_amount)
        except InvalidOperation as error:
            raise ValueError("refunded amount must be a non-negative decimal") from error
        if not amount.is_finite() or amount < 0:
            raise ValueError("refunded amount must be a non-negative decimal")
        if len(self.currency) != 3 or not self.currency.isalpha() or not self.currency.isupper():
            raise ValueError("currency must be an uppercase ISO 4217 code")
        if self.status in {
            RefundOutcomeStatus.PARTIALLY_REFUNDED,
            RefundOutcomeStatus.REFUNDED,
        } and (not self.provider_refund_id or amount <= 0):
            raise ValueError("confirmed refunds require a provider reference and positive amount")
        if self.adapter.mode.value == "development_fixture" and self.provider_confirmed:
            raise ValueError("development fixtures cannot confirm a production refund")
