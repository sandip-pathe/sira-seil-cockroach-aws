"""Pure SIRA + SEIL domain contracts.

This package intentionally depends only on the Python standard library.  HTTP,
persistence, provider, workflow, and agent-runtime concerns belong behind
adapters in their respective packages.
"""

from .enums import (
    ApprovalStatus,
    CandidateAction,
    CandidateStatus,
    EngagementStatus,
    FulfillmentStatus,
    PaymentStatus,
    ProductInstanceState,
    PurchaseState,
    RequestVisibility,
    RuleOperator,
    SolutionAction,
    StackPatchStatus,
    StackRisk,
    TruthValue,
)
from .errors import DomainValidationError, InvalidTransitionError
from .hashing import canonical_json, content_hash
from .models import (
    ApprovalBinding,
    BuyerFact,
    EvidenceRef,
    ExpectedFulfillment,
    MerchantIdentity,
    PurchaseIntent,
    SourceRef,
    Verification,
)
from .money import Money
from .publication import (
    DEFAULT_PACK_PUBLICATION_ALLOWLIST,
    DEFAULT_REQUIREMENT_BRIEF_ALLOWLIST,
    assert_public_payload,
    publish_seil_pack,
    sanitize_requirement_brief,
)
from .rules import RuleCondition, RuleEvaluation, RuleExpression, resolve_field
from .state_machines import (
    ApprovalTransitionService,
    FulfillmentTransitionService,
    PaymentTransitionService,
    derive_purchase_state,
)

__all__ = [
    "DEFAULT_PACK_PUBLICATION_ALLOWLIST",
    "DEFAULT_REQUIREMENT_BRIEF_ALLOWLIST",
    "ApprovalBinding",
    "ApprovalStatus",
    "ApprovalTransitionService",
    "BuyerFact",
    "CandidateAction",
    "CandidateStatus",
    "DomainValidationError",
    "EngagementStatus",
    "EvidenceRef",
    "ExpectedFulfillment",
    "FulfillmentStatus",
    "FulfillmentTransitionService",
    "InvalidTransitionError",
    "MerchantIdentity",
    "Money",
    "PaymentStatus",
    "PaymentTransitionService",
    "ProductInstanceState",
    "PurchaseIntent",
    "PurchaseState",
    "RequestVisibility",
    "RuleCondition",
    "RuleEvaluation",
    "RuleExpression",
    "RuleOperator",
    "SolutionAction",
    "SourceRef",
    "StackPatchStatus",
    "StackRisk",
    "TruthValue",
    "Verification",
    "assert_public_payload",
    "canonical_json",
    "content_hash",
    "derive_purchase_state",
    "publish_seil_pack",
    "resolve_field",
    "sanitize_requirement_brief",
]
