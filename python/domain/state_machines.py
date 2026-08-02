"""Pure, explicit approval/payment/fulfillment transition services."""

from __future__ import annotations

from typing import ClassVar

from .enums import (
    ApprovalStatus,
    FulfillmentStatus,
    PaymentStatus,
    PurchaseState,
    ReversalStatus,
)
from .errors import DomainValidationError, InvalidTransitionError
from .models import ApprovalBinding, require_hash


class ApprovalTransitionService:
    _allowed: ClassVar[dict[ApprovalStatus, frozenset[ApprovalStatus]]] = {
        ApprovalStatus.NOT_REQUESTED: frozenset({ApprovalStatus.PENDING}),
        ApprovalStatus.PENDING: frozenset(
            {
                ApprovalStatus.APPROVED,
                ApprovalStatus.REJECTED,
                ApprovalStatus.REVOKED,
                ApprovalStatus.EXPIRED,
                ApprovalStatus.SUPERSEDED,
            }
        ),
        ApprovalStatus.APPROVED: frozenset({ApprovalStatus.REVOKED, ApprovalStatus.SUPERSEDED}),
        ApprovalStatus.REJECTED: frozenset(),
        ApprovalStatus.REVOKED: frozenset(),
        ApprovalStatus.EXPIRED: frozenset(),
        ApprovalStatus.SUPERSEDED: frozenset(),
    }

    @classmethod
    def transition(cls, current: ApprovalStatus, target: ApprovalStatus) -> ApprovalStatus:
        if target not in cls._allowed[current]:
            raise InvalidTransitionError(f"approval cannot transition {current} -> {target}")
        return target

    @classmethod
    def approve_exact(
        cls,
        binding: ApprovalBinding,
        presented_intent_hash: str,
    ) -> ApprovalBinding:
        """Approve only the exact canonical intent bound to the request."""

        require_hash(presented_intent_hash, "presented_intent_hash")
        if presented_intent_hash != binding.intent_hash:
            raise DomainValidationError("approval payload hash does not match Purchase Intent")
        return ApprovalBinding(
            approval_request_id=binding.approval_request_id,
            intent_hash=binding.intent_hash,
            status=cls.transition(binding.status, ApprovalStatus.APPROVED),
        )

    @staticmethod
    def reconcile_payload(binding: ApprovalBinding, current_intent_hash: str) -> ApprovalBinding:
        """Supersede any nonterminal approval when its exact payload changes."""

        require_hash(current_intent_hash, "current_intent_hash")
        if binding.intent_hash == current_intent_hash:
            return binding
        if binding.status in {ApprovalStatus.PENDING, ApprovalStatus.APPROVED}:
            return ApprovalBinding(
                approval_request_id=binding.approval_request_id,
                intent_hash=binding.intent_hash,
                status=ApprovalStatus.SUPERSEDED,
            )
        return binding


class PaymentTransitionService:
    _allowed: ClassVar[dict[PaymentStatus, frozenset[PaymentStatus]]] = {
        PaymentStatus.NOT_STARTED: frozenset({PaymentStatus.SESSION_CREATED}),
        PaymentStatus.SESSION_CREATED: frozenset(
            {
                PaymentStatus.CARDHOLDER_PENDING,
                PaymentStatus.EXPIRED,
                PaymentStatus.FAILED,
                PaymentStatus.UNCERTAIN,
            }
        ),
        PaymentStatus.CARDHOLDER_PENDING: frozenset(
            {
                PaymentStatus.CHECKOUT_PENDING,
                PaymentStatus.EXPIRED,
                PaymentStatus.FAILED,
                PaymentStatus.UNCERTAIN,
            }
        ),
        PaymentStatus.CHECKOUT_PENDING: frozenset(
            {
                PaymentStatus.MERCHANT_APPROVED,
                PaymentStatus.DECLINED,
                PaymentStatus.UNCERTAIN,
            }
        ),
        PaymentStatus.MERCHANT_APPROVED: frozenset(
            {PaymentStatus.REPORTING, PaymentStatus.UNCERTAIN}
        ),
        PaymentStatus.REPORTING: frozenset(
            {PaymentStatus.PRAVA_COMPLETED, PaymentStatus.UNCERTAIN}
        ),
        PaymentStatus.PRAVA_COMPLETED: frozenset(),
        PaymentStatus.DECLINED: frozenset(),
        PaymentStatus.EXPIRED: frozenset(),
        PaymentStatus.UNCERTAIN: frozenset(
            {
                PaymentStatus.MERCHANT_APPROVED,
                PaymentStatus.REPORTING,
                PaymentStatus.PRAVA_COMPLETED,
                PaymentStatus.DECLINED,
                PaymentStatus.FAILED,
            }
        ),
        PaymentStatus.FAILED: frozenset(),
    }

    @classmethod
    def transition(
        cls,
        current: PaymentStatus,
        target: PaymentStatus,
        *,
        reconciled: bool = False,
    ) -> PaymentStatus:
        if target not in cls._allowed[current]:
            raise InvalidTransitionError(f"payment cannot transition {current} -> {target}")
        if current is PaymentStatus.UNCERTAIN and not reconciled:
            raise InvalidTransitionError("uncertain payment can change only after reconciliation")
        return target

    @staticmethod
    def blocks_new_attempt(status: PaymentStatus) -> bool:
        return status in {
            PaymentStatus.CHECKOUT_PENDING,
            PaymentStatus.MERCHANT_APPROVED,
            PaymentStatus.REPORTING,
            PaymentStatus.PRAVA_COMPLETED,
            PaymentStatus.UNCERTAIN,
        }


class FulfillmentTransitionService:
    _allowed: ClassVar[dict[FulfillmentStatus, frozenset[FulfillmentStatus]]] = {
        FulfillmentStatus.NOT_STARTED: frozenset({FulfillmentStatus.PENDING}),
        FulfillmentStatus.PENDING: frozenset(
            {
                FulfillmentStatus.PARTIAL,
                FulfillmentStatus.VERIFIED,
                FulfillmentStatus.FAILED_RETRYABLE,
                FulfillmentStatus.FAILED_FINAL,
            }
        ),
        FulfillmentStatus.PARTIAL: frozenset(
            {
                FulfillmentStatus.VERIFIED,
                FulfillmentStatus.FAILED_RETRYABLE,
                FulfillmentStatus.FAILED_FINAL,
            }
        ),
        FulfillmentStatus.FAILED_RETRYABLE: frozenset(
            {FulfillmentStatus.PENDING, FulfillmentStatus.VERIFIED}
        ),
        FulfillmentStatus.VERIFIED: frozenset({FulfillmentStatus.REVOKED}),
        FulfillmentStatus.FAILED_FINAL: frozenset(),
        FulfillmentStatus.REVOKED: frozenset(),
    }

    @classmethod
    def transition(
        cls,
        current: FulfillmentStatus,
        target: FulfillmentStatus,
        *,
        payment_status: PaymentStatus,
    ) -> FulfillmentStatus:
        if target not in cls._allowed[current]:
            raise InvalidTransitionError(f"fulfillment cannot transition {current} -> {target}")
        if (
            current is FulfillmentStatus.NOT_STARTED
            and payment_status is not PaymentStatus.PRAVA_COMPLETED
        ):
            raise InvalidTransitionError("fulfillment cannot start before Prava completion")
        return target


class ReversalTransitionService:
    _allowed: ClassVar[dict[ReversalStatus, frozenset[ReversalStatus]]] = {
        ReversalStatus.REQUESTED: frozenset(
            {
                ReversalStatus.PROVIDER_PENDING,
                ReversalStatus.PARTIALLY_REFUNDED,
                ReversalStatus.REFUNDED,
                ReversalStatus.REJECTED,
                ReversalStatus.COMPENSATION_REQUIRED,
                ReversalStatus.CANCELLED,
            }
        ),
        ReversalStatus.PROVIDER_PENDING: frozenset(
            {
                ReversalStatus.PARTIALLY_REFUNDED,
                ReversalStatus.REFUNDED,
                ReversalStatus.REJECTED,
                ReversalStatus.FAILED_RETRYABLE,
                ReversalStatus.COMPENSATION_REQUIRED,
            }
        ),
        ReversalStatus.FAILED_RETRYABLE: frozenset(
            {
                ReversalStatus.PROVIDER_PENDING,
                ReversalStatus.COMPENSATION_REQUIRED,
                ReversalStatus.CANCELLED,
            }
        ),
        ReversalStatus.PARTIALLY_REFUNDED: frozenset(
            {
                ReversalStatus.PROVIDER_PENDING,
                ReversalStatus.REFUNDED,
                ReversalStatus.COMPENSATION_REQUIRED,
            }
        ),
        ReversalStatus.COMPENSATION_REQUIRED: frozenset({ReversalStatus.COMPENSATED}),
        ReversalStatus.REFUNDED: frozenset(),
        ReversalStatus.REJECTED: frozenset(),
        ReversalStatus.COMPENSATED: frozenset(),
        ReversalStatus.CANCELLED: frozenset(),
    }

    @classmethod
    def transition(cls, current: ReversalStatus, target: ReversalStatus) -> ReversalStatus:
        if target not in cls._allowed[current]:
            raise InvalidTransitionError(f"reversal cannot transition {current} -> {target}")
        return target


def derive_purchase_state(
    approval_status: ApprovalStatus,
    payment_status: PaymentStatus,
    fulfillment_status: FulfillmentStatus,
    *,
    refund_pending: bool = False,
    fully_refunded: bool = False,
) -> PurchaseState:
    """Derive the UI purchase state without collapsing canonical machines."""

    if refund_pending and fully_refunded:
        raise DomainValidationError("refund cannot be pending and complete")
    if fully_refunded:
        return PurchaseState.REFUNDED
    if refund_pending:
        return PurchaseState.REFUND_PENDING
    if approval_status is not ApprovalStatus.APPROVED:
        return PurchaseState.AWAITING_APPROVAL
    if payment_status is PaymentStatus.NOT_STARTED:
        if fulfillment_status is not FulfillmentStatus.NOT_STARTED:
            raise DomainValidationError("fulfillment exists before payment")
        return PurchaseState.APPROVED_NOT_STARTED
    if payment_status is PaymentStatus.UNCERTAIN:
        return PurchaseState.PAYMENT_UNCERTAIN
    if payment_status in {PaymentStatus.DECLINED, PaymentStatus.EXPIRED, PaymentStatus.FAILED}:
        return PurchaseState.PAYMENT_NOT_COMPLETED
    if payment_status is not PaymentStatus.PRAVA_COMPLETED:
        if fulfillment_status is not FulfillmentStatus.NOT_STARTED:
            raise DomainValidationError("fulfillment exists before payment completion")
        return PurchaseState.PAYMENT_IN_PROGRESS
    if fulfillment_status is FulfillmentStatus.VERIFIED:
        return PurchaseState.PURCHASE_FULFILLED
    return PurchaseState.PAID_UNFULFILLED
