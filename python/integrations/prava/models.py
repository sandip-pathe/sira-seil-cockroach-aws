"""Credential-free Prava hosted-checkout models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from integrations.common import AdapterDescriptor
from integrations.merchants.models import MerchantCheckoutOutcome


def _validate_amount(value: str) -> None:
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("amount must be a decimal string") from exc
    exponent = amount.as_tuple().exponent
    if not amount.is_finite() or amount <= 0 or not isinstance(exponent, int) or exponent < -2:
        raise ValueError("amount must be positive with at most two decimal places")


class PravaPaymentStatus(StrEnum):
    PENDING = "pending"
    AWAITING_RESULT = "awaiting_result"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class PravaMerchantDetails:
    name: str
    url: str
    country_code_iso2: str

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.url:
            raise ValueError("merchant name and URL are required")
        if (
            len(self.country_code_iso2) != 2
            or not self.country_code_iso2.isalpha()
            or not self.country_code_iso2.isupper()
        ):
            raise ValueError("country_code_iso2 must be two uppercase letters")


@dataclass(frozen=True, slots=True)
class PravaProductDetails:
    description: str
    unit_price: str
    quantity: int = 1
    product_id: str | None = None

    def __post_init__(self) -> None:
        if not self.description.strip() or self.quantity < 1:
            raise ValueError("product description and positive quantity are required")
        _validate_amount(self.unit_price)


@dataclass(frozen=True, slots=True)
class PravaSessionRequest:
    user_id: str
    user_email: str
    total_amount: str
    currency: str
    merchant: PravaMerchantDetails
    products: tuple[PravaProductDetails, ...]
    callback_url: str

    def __post_init__(self) -> None:
        if not self.user_id or "@" not in self.user_email:
            raise ValueError("user id and email are required")
        _validate_amount(self.total_amount)
        if len(self.currency) != 3 or not self.currency.isalpha() or not self.currency.isupper():
            raise ValueError("currency must be an uppercase ISO 4217 code")
        if not self.products:
            raise ValueError("at least one product is required")


@dataclass(frozen=True, slots=True)
class PravaHostedSession:
    """Safe browser handoff; the provider session token is deliberately omitted."""

    session_id: str
    hosted_url: str
    order_id: str
    expires_at: datetime
    adapter: AdapterDescriptor


@dataclass(frozen=True, slots=True)
class PravaReportResult:
    session_id: str
    transaction_reference: str
    provider_confirmed: bool
    adapter: AdapterDescriptor

    def __post_init__(self) -> None:
        if self.adapter.mode.value == "development_fixture" and self.provider_confirmed:
            raise ValueError("a development fixture cannot confirm a production report")


@dataclass(frozen=True, slots=True)
class PravaCheckoutResult:
    """Only redacted checkout facts may cross the isolated operation boundary."""

    session_id: str
    prava_order_id: str
    transaction_reference: str
    merchant: MerchantCheckoutOutcome
    provider_reported: bool
    final_status: PravaPaymentStatus
    reconciliation_required: bool
    adapter: AdapterDescriptor

    def __post_init__(self) -> None:
        if self.adapter.mode.value == "development_fixture" and self.provider_reported:
            raise ValueError("a development fixture cannot confirm a production report")
