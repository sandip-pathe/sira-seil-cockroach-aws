"""Shared, stable enum values for the first vertical workflow."""

from enum import StrEnum

StringEnum = StrEnum


class CandidateStatus(StringEnum):
    ELIGIBLE = "ELIGIBLE"
    ELIGIBLE_WITH_EXCEPTION = "ELIGIBLE_WITH_EXCEPTION"
    CONDITIONAL = "CONDITIONAL"
    SIRA_INELIGIBLE = "SIRA_INELIGIBLE"
    SEIL_PASS = "SEIL_PASS"  # noqa: S105 - product status, not a password
    UNAVAILABLE = "UNAVAILABLE"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    AUTHORITY_REQUIRED = "AUTHORITY_REQUIRED"


class ApprovalStatus(StringEnum):
    NOT_REQUESTED = "NOT_REQUESTED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class PaymentStatus(StringEnum):
    """Persisted first-build payment states.

    A one-time Prava credential deliberately has no persisted state: it exists
    only in the isolated checkout operation between CARDHOLDER_PENDING and
    CHECKOUT_PENDING.
    """

    NOT_STARTED = "NOT_STARTED"
    SESSION_CREATED = "SESSION_CREATED"
    CARDHOLDER_PENDING = "CARDHOLDER_PENDING"
    CHECKOUT_PENDING = "CHECKOUT_PENDING"
    MERCHANT_APPROVED = "MERCHANT_APPROVED"
    REPORTING = "REPORTING"
    PRAVA_COMPLETED = "PRAVA_COMPLETED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"
    UNCERTAIN = "UNCERTAIN"
    FAILED = "FAILED"


class FulfillmentStatus(StringEnum):
    NOT_STARTED = "NOT_STARTED"
    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    VERIFIED = "VERIFIED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_FINAL = "FAILED_FINAL"
    REVOKED = "REVOKED"


class PurchaseState(StringEnum):
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED_NOT_STARTED = "APPROVED_NOT_STARTED"
    PAYMENT_IN_PROGRESS = "PAYMENT_IN_PROGRESS"
    PAYMENT_NOT_COMPLETED = "PAYMENT_NOT_COMPLETED"
    PAYMENT_UNCERTAIN = "PAYMENT_UNCERTAIN"
    PAID_UNFULFILLED = "PAID_UNFULFILLED"
    PURCHASE_FULFILLED = "PURCHASE_FULFILLED"
    REFUND_PENDING = "REFUND_PENDING"
    REFUNDED = "REFUNDED"


class RequestVisibility(StringEnum):
    PRIVATE = "PRIVATE"
    SELECTIVE = "SELECTIVE"
    OPEN_RFP = "OPEN_RFP"


class CandidateAction(StringEnum):
    SHORTLIST = "SHORTLIST"
    PASS = "PASS"  # noqa: S105 - buyer feedback action, not a password
    REQUEST_OFFER = "REQUEST_OFFER"
    SAVE_FOR_LATER = "SAVE_FOR_LATER"
    NOT_ENOUGH_EVIDENCE = "NOT_ENOUGH_EVIDENCE"


class EngagementStatus(StringEnum):
    NOT_STARTED = "NOT_STARTED"
    SELLER_REVIEWING = "SELLER_REVIEWING"
    SELLER_PASSED = "SELLER_PASSED"
    OFFER_AVAILABLE = "OFFER_AVAILABLE"
    BUYER_CONSENT_PENDING = "BUYER_CONSENT_PENDING"
    SELLER_CONSENT_PENDING = "SELLER_CONSENT_PENDING"
    INTRODUCTION_READY = "INTRODUCTION_READY"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"


class SolutionAction(StringEnum):
    REUSE_EXISTING = "REUSE_EXISTING"
    CONFIGURE_EXISTING = "CONFIGURE_EXISTING"
    NO_ACTION = "NO_ACTION"
    BUY = "BUY"
    REPLACE = "REPLACE"
    CONSOLIDATE = "CONSOLIDATE"


class StackRisk(StringEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        return {
            StackRisk.LOW: 0,
            StackRisk.MEDIUM: 1,
            StackRisk.HIGH: 2,
            StackRisk.CRITICAL: 3,
        }[self]


class TruthValue(StringEnum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNRESOLVED = "UNRESOLVED"


class RuleOperator(StringEnum):
    EQ = "eq"
    NEQ = "neq"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    CONTAINS_ALL = "contains_all"
    GTE = "gte"
    LTE = "lte"
    GT = "gt"
    LT = "lt"
    EXISTS = "exists"
    DATE_BEFORE = "date_before"
    DATE_ON_OR_BEFORE = "date_on_or_before"
    DATE_AFTER = "date_after"
    DATE_ON_OR_AFTER = "date_on_or_after"


class ProductInstanceState(StringEnum):
    PROPOSED = "proposed"
    CONTRACTED = "contracted"
    PROVISIONED = "provisioned"
    DEPLOYING = "deploying"
    ACTIVE = "active"
    DEGRADED = "degraded"
    RETIRING = "retiring"
    CANCELLED = "cancelled"


class StackPatchStatus(StringEnum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    APPLYING = "APPLYING"
    APPLIED = "APPLIED"
    CONFLICT = "CONFLICT"
    FAILED = "FAILED"
    COMPENSATING_PATCH = "COMPENSATING_PATCH"
