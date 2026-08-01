"""Exact money value object."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from .errors import DomainValidationError

_CURRENCY = re.compile(r"^[A-Z]{3}$")


def _coerce_decimal(value: Decimal | str | int) -> Decimal:
    if isinstance(value, float):
        raise DomainValidationError("binary floating point is prohibited for money")
    if isinstance(value, bool):
        raise DomainValidationError("money must be constructed from Decimal, string, or int")
    try:
        result = value if isinstance(value, Decimal) else Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise DomainValidationError("invalid decimal money amount") from exc
    if not result.is_finite():
        raise DomainValidationError("money amount must be finite")
    if result < 0:
        raise DomainValidationError("money amount cannot be negative")
    if result.quantize(Decimal("0.01")) != result:
        raise DomainValidationError("money amount must have at most two decimal places")
    return result.normalize() if result else Decimal(0)


def decimal_text(value: Decimal) -> str:
    return format(value, ".2f")


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str

    def __init__(self, amount: Decimal | str | int, currency: str) -> None:
        amount_value = _coerce_decimal(amount)
        currency_value = currency.upper()
        if not _CURRENCY.fullmatch(currency_value):
            raise DomainValidationError("currency must be a three-letter ISO code")
        object.__setattr__(self, "amount", amount_value)
        object.__setattr__(self, "currency", currency_value)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Money:
        if set(value) != {"amount", "currency"}:
            raise DomainValidationError("money requires exactly amount and currency")
        return cls(value["amount"], value["currency"])

    def to_dict(self) -> dict[str, str]:
        return {"amount": decimal_text(self.amount), "currency": self.currency}

    def to_hash_payload(self) -> dict[str, str]:
        return self.to_dict()

    def _require_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise DomainValidationError("money values use different currencies")

    def __add__(self, other: Money) -> Money:
        self._require_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_currency(other)
        return self.amount < other.amount
