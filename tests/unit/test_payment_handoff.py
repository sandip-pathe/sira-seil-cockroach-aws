from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from domain import (
    DomainValidationError,
    InvalidTransitionError,
    Money,
    PaymentHandoff,
    PaymentHandoffStatus,
    PaymentHandoffTransitionService,
    content_hash,
)

NOW = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)
INTENT_HASH = content_hash({"intent": "exact-approved-purchase"})


def make_handoff(**changes: object) -> PaymentHandoff:
    values = {
        "schema_version": "1.0",
        "handoff_id": "handoff-001",
        "organization_id": "org-001",
        "purchase_intent_id": "intent-001",
        "approval_request_id": "approval-001",
        "intent_hash": INTENT_HASH,
        "destination_url": "https://payments.example.test/invoice/123",
        "recipient": "Example Software Ltd",
        "amount": Money("1499.00", "USD"),
        "reference": "SIRA-PO-123",
        "created_at": NOW,
        "expires_at": NOW + timedelta(minutes=15),
    }
    values.update(changes)
    return PaymentHandoff(**values)  # type: ignore[arg-type]


def test_handoff_hash_binds_exact_approved_context() -> None:
    handoff = make_handoff()

    assert handoff.status is PaymentHandoffStatus.READY
    assert handoff.opened_at is None
    assert handoff.handoff_hash.startswith("sha256:")
    with pytest.raises(DomainValidationError, match="canonical payload"):
        replace(handoff, amount=Money("1500.00", "USD"))


@pytest.mark.parametrize(
    "destination",
    [
        "http://payments.example.test/invoice/123",
        "https://user:secret@payments.example.test/invoice/123",
        "https://payments.example.test/invoice/123#card-number",
    ],
)
def test_handoff_rejects_unsafe_destinations(destination: str) -> None:
    with pytest.raises(DomainValidationError, match="HTTPS URL"):
        make_handoff(destination_url=destination)


def test_handoff_can_be_opened_once_before_expiry() -> None:
    handoff = make_handoff()
    opened_at = NOW + timedelta(minutes=1)

    opened = PaymentHandoffTransitionService.transition(
        handoff,
        PaymentHandoffStatus.OPENED,
        at=opened_at,
    )

    assert opened.status is PaymentHandoffStatus.OPENED
    assert opened.opened_at == opened_at
    assert opened.handoff_hash == handoff.handoff_hash
    with pytest.raises(InvalidTransitionError):
        PaymentHandoffTransitionService.transition(
            opened,
            PaymentHandoffStatus.OPENED,
            at=opened_at,
        )


def test_expired_handoff_cannot_be_opened() -> None:
    handoff = make_handoff()

    with pytest.raises(InvalidTransitionError, match="expired"):
        PaymentHandoffTransitionService.transition(
            handoff,
            PaymentHandoffStatus.OPENED,
            at=handoff.expires_at,
        )
