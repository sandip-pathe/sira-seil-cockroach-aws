"""Pure approval and external-handoff transition services."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import ClassVar

from .enums import ApprovalStatus, PaymentHandoffStatus
from .errors import DomainValidationError, InvalidTransitionError
from .models import ApprovalBinding, PaymentHandoff, require_aware, require_hash


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


class PaymentHandoffTransitionService:
    """Transitions the handoff only; external payment state is out of scope."""

    _allowed: ClassVar[dict[PaymentHandoffStatus, frozenset[PaymentHandoffStatus]]] = {
        PaymentHandoffStatus.READY: frozenset(
            {
                PaymentHandoffStatus.OPENED,
                PaymentHandoffStatus.EXPIRED,
                PaymentHandoffStatus.CANCELLED,
            }
        ),
        PaymentHandoffStatus.OPENED: frozenset(),
        PaymentHandoffStatus.EXPIRED: frozenset(),
        PaymentHandoffStatus.CANCELLED: frozenset(),
    }

    @classmethod
    def transition(
        cls,
        handoff: PaymentHandoff,
        target: PaymentHandoffStatus,
        *,
        at: datetime,
    ) -> PaymentHandoff:
        require_aware(at, "at")
        if target not in cls._allowed[handoff.status]:
            raise InvalidTransitionError(
                f"payment handoff cannot transition {handoff.status} -> {target}"
            )
        if target is PaymentHandoffStatus.OPENED:
            if at >= handoff.expires_at:
                raise InvalidTransitionError("expired payment handoff cannot be opened")
            return replace(handoff, status=target, opened_at=at)
        return replace(handoff, status=target)
