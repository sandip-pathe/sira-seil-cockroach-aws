import pytest

from domain import ApprovalBinding, content_hash
from domain.enums import ApprovalStatus
from domain.errors import DomainValidationError, InvalidTransitionError
from domain.state_machines import ApprovalTransitionService


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
