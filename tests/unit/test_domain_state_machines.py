import pytest

from domain import ApprovalBinding, content_hash
from domain.enums import (
    ApprovalStatus,
    FulfillmentStatus,
    PaymentStatus,
    PurchaseState,
    ReversalStatus,
)
from domain.errors import DomainValidationError, InvalidTransitionError
from domain.state_machines import (
    ApprovalTransitionService,
    FulfillmentTransitionService,
    PaymentTransitionService,
    ReversalTransitionService,
    derive_purchase_state,
)


def test_approval_rejection_is_terminal() -> None:
    assert (
        ApprovalTransitionService.transition(ApprovalStatus.PENDING, ApprovalStatus.REJECTED)
        is ApprovalStatus.REJECTED
    )
    with pytest.raises(InvalidTransitionError):
        ApprovalTransitionService.transition(ApprovalStatus.REJECTED, ApprovalStatus.PENDING)


def test_approval_requires_the_exact_intent_hash() -> None:
    expected = content_hash({"intent": "exact"})
    binding = ApprovalBinding("approval_demo", expected, ApprovalStatus.PENDING)
    approved = ApprovalTransitionService.approve_exact(binding, expected)
    assert approved.status is ApprovalStatus.APPROVED
    with pytest.raises(DomainValidationError, match="does not match"):
        ApprovalTransitionService.approve_exact(
            binding,
            content_hash({"intent": "mutated"}),
        )


def test_pending_or_approved_authority_can_be_revoked_but_not_restored() -> None:
    assert (
        ApprovalTransitionService.transition(ApprovalStatus.PENDING, ApprovalStatus.REVOKED)
        is ApprovalStatus.REVOKED
    )
    assert (
        ApprovalTransitionService.transition(ApprovalStatus.APPROVED, ApprovalStatus.REVOKED)
        is ApprovalStatus.REVOKED
    )
    with pytest.raises(InvalidTransitionError):
        ApprovalTransitionService.transition(ApprovalStatus.REVOKED, ApprovalStatus.APPROVED)


def test_complete_payment_path_and_charged_guard() -> None:
    status = PaymentStatus.NOT_STARTED
    for target in (
        PaymentStatus.SESSION_CREATED,
        PaymentStatus.CARDHOLDER_PENDING,
        PaymentStatus.CHECKOUT_PENDING,
        PaymentStatus.MERCHANT_APPROVED,
        PaymentStatus.REPORTING,
        PaymentStatus.PRAVA_COMPLETED,
    ):
        status = PaymentTransitionService.transition(status, target)
    assert status is PaymentStatus.PRAVA_COMPLETED
    assert PaymentTransitionService.blocks_new_attempt(status)


def test_uncertain_payment_requires_reconciliation_and_never_blind_retries() -> None:
    status = PaymentTransitionService.transition(
        PaymentStatus.CHECKOUT_PENDING, PaymentStatus.UNCERTAIN
    )
    assert PaymentTransitionService.blocks_new_attempt(status)
    with pytest.raises(InvalidTransitionError, match="reconciliation"):
        PaymentTransitionService.transition(status, PaymentStatus.MERCHANT_APPROVED)
    assert (
        PaymentTransitionService.transition(
            status, PaymentStatus.MERCHANT_APPROVED, reconciled=True
        )
        is PaymentStatus.MERCHANT_APPROVED
    )


def test_merchant_approval_cannot_turn_into_decline_or_checkout_retry() -> None:
    with pytest.raises(InvalidTransitionError):
        PaymentTransitionService.transition(
            PaymentStatus.MERCHANT_APPROVED, PaymentStatus.CHECKOUT_PENDING
        )
    with pytest.raises(InvalidTransitionError):
        PaymentTransitionService.transition(PaymentStatus.MERCHANT_APPROVED, PaymentStatus.DECLINED)


def test_fulfillment_can_start_only_after_prava_completion() -> None:
    with pytest.raises(InvalidTransitionError, match="Prava completion"):
        FulfillmentTransitionService.transition(
            FulfillmentStatus.NOT_STARTED,
            FulfillmentStatus.PENDING,
            payment_status=PaymentStatus.MERCHANT_APPROVED,
        )
    assert (
        FulfillmentTransitionService.transition(
            FulfillmentStatus.NOT_STARTED,
            FulfillmentStatus.PENDING,
            payment_status=PaymentStatus.PRAVA_COMPLETED,
        )
        is FulfillmentStatus.PENDING
    )


def test_purchase_state_keeps_payment_and_fulfillment_separate() -> None:
    assert (
        derive_purchase_state(
            ApprovalStatus.APPROVED,
            PaymentStatus.PRAVA_COMPLETED,
            FulfillmentStatus.PARTIAL,
        )
        is PurchaseState.PAID_UNFULFILLED
    )
    assert (
        derive_purchase_state(
            ApprovalStatus.APPROVED,
            PaymentStatus.PRAVA_COMPLETED,
            FulfillmentStatus.VERIFIED,
        )
        is PurchaseState.PURCHASE_FULFILLED
    )
    assert (
        derive_purchase_state(
            ApprovalStatus.APPROVED,
            PaymentStatus.UNCERTAIN,
            FulfillmentStatus.NOT_STARTED,
        )
        is PurchaseState.PAYMENT_UNCERTAIN
    )
    assert (
        derive_purchase_state(
            ApprovalStatus.PENDING,
            PaymentStatus.NOT_STARTED,
            FulfillmentStatus.NOT_STARTED,
        )
        is PurchaseState.AWAITING_APPROVAL
    )
    assert (
        derive_purchase_state(
            ApprovalStatus.APPROVED,
            PaymentStatus.NOT_STARTED,
            FulfillmentStatus.NOT_STARTED,
        )
        is PurchaseState.APPROVED_NOT_STARTED
    )
    assert (
        derive_purchase_state(
            ApprovalStatus.APPROVED,
            PaymentStatus.DECLINED,
            FulfillmentStatus.NOT_STARTED,
        )
        is PurchaseState.PAYMENT_NOT_COMPLETED
    )
    assert (
        derive_purchase_state(
            ApprovalStatus.APPROVED,
            PaymentStatus.PRAVA_COMPLETED,
            FulfillmentStatus.VERIFIED,
            refund_pending=True,
        )
        is PurchaseState.REFUND_PENDING
    )
    assert (
        derive_purchase_state(
            ApprovalStatus.APPROVED,
            PaymentStatus.PRAVA_COMPLETED,
            FulfillmentStatus.REVOKED,
            fully_refunded=True,
        )
        is PurchaseState.REFUNDED
    )


def test_impossible_fulfillment_before_payment_fails_closed() -> None:
    with pytest.raises(DomainValidationError, match="before payment"):
        derive_purchase_state(
            ApprovalStatus.APPROVED,
            PaymentStatus.CHECKOUT_PENDING,
            FulfillmentStatus.PENDING,
        )


def test_reversal_state_machine_supports_direct_confirmation_and_compensation() -> None:
    assert (
        ReversalTransitionService.transition(
            ReversalStatus.REQUESTED, ReversalStatus.REFUNDED
        )
        is ReversalStatus.REFUNDED
    )
    assert (
        ReversalTransitionService.transition(
            ReversalStatus.PROVIDER_PENDING,
            ReversalStatus.COMPENSATION_REQUIRED,
        )
        is ReversalStatus.COMPENSATION_REQUIRED
    )
    with pytest.raises(InvalidTransitionError):
        ReversalTransitionService.transition(
            ReversalStatus.REFUNDED, ReversalStatus.PROVIDER_PENDING
        )
