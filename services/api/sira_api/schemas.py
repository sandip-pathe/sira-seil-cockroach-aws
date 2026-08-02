"""Strict public request and response models that freeze the first API contract."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, StringConstraints, UrlConstraints

from domain.enums import PaymentStatus

Identifier = Annotated[
    str,
    StringConstraints(min_length=3, max_length=128, pattern=r"^[a-z][a-z0-9_:-]{2,127}$"),
]
HashValue = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
MoneyAmount = Annotated[str, StringConstraints(pattern=r"^(0|[1-9][0-9]*)\.[0-9]{2}$")]
MetricValue = Annotated[str, StringConstraints(pattern=r"^-?(0|[1-9][0-9]*)(\.[0-9]{1,6})?$")]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
HttpsUrl = Annotated[AnyUrl, UrlConstraints(allowed_schemes=["https"], host_required=True)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CandidateStatus(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    ELIGIBLE_WITH_EXCEPTION = "ELIGIBLE_WITH_EXCEPTION"
    CONDITIONAL = "CONDITIONAL"
    SIRA_INELIGIBLE = "SIRA_INELIGIBLE"
    SEIL_PASS = "SEIL_PASS"
    UNAVAILABLE = "UNAVAILABLE"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    AUTHORITY_REQUIRED = "AUTHORITY_REQUIRED"
    ADVISORY_ONLY = "ADVISORY_ONLY"


class ApprovalStatus(StrEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    NOT_REQUESTED = "NOT_REQUESTED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class FulfillmentStatus(StrEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    NOT_STARTED = "NOT_STARTED"
    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    VERIFIED = "VERIFIED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_FINAL = "FAILED_FINAL"
    REVOKED = "REVOKED"


class RequestVisibility(StrEnum):
    PRIVATE = "PRIVATE"
    SELECTIVE = "SELECTIVE"
    OPEN_RFP = "OPEN_RFP"


class CandidateAction(StrEnum):
    SHORTLIST = "SHORTLIST"
    PASS = "PASS"
    REQUEST_OFFER = "REQUEST_OFFER"
    SAVE_FOR_LATER = "SAVE_FOR_LATER"
    NOT_ENOUGH_EVIDENCE = "NOT_ENOUGH_EVIDENCE"


class EngagementStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    SELLER_REVIEWING = "SELLER_REVIEWING"
    SELLER_PASSED = "SELLER_PASSED"
    OFFER_AVAILABLE = "OFFER_AVAILABLE"
    BUYER_CONSENT_PENDING = "BUYER_CONSENT_PENDING"
    SELLER_CONSENT_PENDING = "SELLER_CONSENT_PENDING"
    INTRODUCTION_READY = "INTRODUCTION_READY"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"


class HealthResponse(StrictModel):
    status: Literal["ok", "degraded"]
    service: Literal["sira-api"] = "sira-api"
    version: str
    database: Literal["configured", "unavailable", "not_checked"]
    fixture_mode: bool


class ErrorBody(StrictModel):
    code: str
    message: str
    request_id: str
    retryable: bool
    next_action: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(StrictModel):
    error: ErrorBody


class DesiredOutcomeInput(StrictModel):
    metric: str
    target: int | float
    operator: Literal["gte", "lte"] = "gte"
    checkpoint_days: int = Field(ge=1, le=365)


class StakeholdersInput(StrictModel):
    user_group_ids: list[Identifier] = Field(default_factory=list)
    decision_maker_id: Identifier
    payer_id: Identifier


class PurchaseRequestCreate(StrictModel):
    intent: str = Field(min_length=10, max_length=2000)
    scenario_id: Identifier | None = None
    jtbd_id: Identifier | None = None
    stakeholders: StakeholdersInput | None = None
    desired_outcome: DesiredOutcomeInput | None = None
    deadline: date | None = None
    visibility: RequestVisibility = RequestVisibility.SELECTIVE


class PurchaseRequestView(StrictModel):
    id: Identifier
    organization_id: Identifier
    intent: str
    status: str
    visibility: RequestVisibility
    version: int
    evaluation_mode: Literal[
        "SCENARIO_SELECTION_REQUIRED",
        "DEVELOPMENT_FIXTURE_NON_PRODUCTION",
        "PROVIDER_CONFIGURATION_REQUIRED",
    ]
    scenario_id: Identifier | None = None
    fixture_label: Literal["DEVELOPMENT_FIXTURE_NON_PRODUCTION"] | None = None
    workflow_id: Identifier | None = None
    decision_id: Identifier | None = None


class WorkflowAccepted(StrictModel):
    workflow_id: Identifier
    status_url: str
    events_url: str


class WorkflowView(StrictModel):
    workflow_id: Identifier
    aggregate_id: Identifier
    operation: str
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED"]
    result_reference: str | None = None
    safe_error_code: str | None = None


class CompanyFactView(StrictModel):
    fact_id: Identifier
    display_name: str
    display_value: str
    provenance_label: str
    sensitivity: str


class CompanyContextView(StrictModel):
    facts_used: list[CompanyFactView]
    hidden_fact_count: int = Field(ge=0)
    passport_version: int = Field(ge=1)
    stack_snapshot: int = Field(ge=1)


class CoverageView(StrictModel):
    evaluated_count: int = Field(ge=0)
    statement: str


class MoneyView(StrictModel):
    amount: MoneyAmount
    currency: Currency


class EvidenceView(StrictModel):
    claim_id: Identifier
    title: str
    verification_method: str
    verification_scope: str
    verified_at: datetime
    fragment_hash: HashValue


class CandidateView(StrictModel):
    id: Identifier
    name: str
    status: CandidateStatus
    reason_code: str | None = None
    reason: str
    preference_score: int | None = Field(default=None, ge=0, le=100)
    stack_risk: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] | None = None
    total_cost: MoneyView
    evidence: list[Identifier] = Field(default_factory=list)
    seller_positioning: str | None = None


class RequestDecisionHeader(StrictModel):
    id: Identifier
    intent: str
    status: str


class SolutionPlanView(StrictModel):
    solution_plan_id: Identifier
    action: Literal[
        "REUSE_EXISTING", "CONFIGURE_EXISTING", "NO_ACTION", "BUY", "REPLACE", "CONSOLIDATE"
    ]
    component_candidate_ids: list[Identifier]
    status: CandidateStatus
    preference_score: int = Field(ge=0, le=100)
    stack_risk: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    total_cost: MoneyView
    required_evidence_coverage_percent: int = Field(ge=0, le=100)
    maximum_evidence_age_days: int = Field(ge=0)
    stable_action_ids: list[Identifier]
    rank: int = Field(ge=1)
    stack_patch_id: Identifier


class StackPatchView(StrictModel):
    schema_version: str
    patch_id: Identifier
    organization_id: Identifier
    base_snapshot: int = Field(ge=1)
    decision_id: Identifier
    solution_plan_id: Identifier
    status: Literal[
        "PROPOSED",
        "STAGED",
        "APPROVED",
        "APPLYING",
        "APPLIED",
        "REJECTED",
        "CONFLICT",
        "FAILED",
    ]
    operations: list[dict[str, Any]]
    prerequisites: list[str]
    rollback_plan: list[str]
    cost_impact: dict[str, Any]
    risk: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    expected_outcome: str
    created_at: datetime
    content_hash: HashValue


class ApprovalView(StrictModel):
    status: ApprovalStatus
    approval_request_id: Identifier | None = None
    intent_hash: HashValue | None = None


class PaymentView(StrictModel):
    status: PaymentStatus
    provider_session_reference: str | None = None


class FulfillmentView(StrictModel):
    status: FulfillmentStatus
    verified_entitlement_ids: list[Identifier] = Field(default_factory=list)


class LegacyDecisionView(StrictModel):
    request: RequestDecisionHeader
    company_context: CompanyContextView
    coverage: CoverageView
    candidates: list[CandidateView]
    selected_solution_plan: SolutionPlanView
    stack_patch: StackPatchView
    approval: ApprovalView
    payment: PaymentView
    fulfillment: FulfillmentView
    receipt: dict[str, Any] | None = None
    counterfactual: dict[str, Any]


# Transitional import alias for code that still validates the hidden legacy route.
DecisionView = LegacyDecisionView


class PurchaseBriefView(StrictModel):
    schema_version: str
    purchase_brief_id: Identifier
    request_id: Identifier
    organization_id: Identifier
    version: int
    supersedes_version: int | None = None
    status: str
    visibility: RequestVisibility
    intent: str
    category_id: Identifier
    desired_outcome: dict[str, Any]
    stakeholder_roles: list[str]
    hard_gates: list[dict[str, Any]]
    preferences: list[dict[str, Any]]
    known_alternatives: list[str]
    stackfile_impact_policy: dict[str, Any]
    disclosure_choices: dict[str, Any]
    approval_requirements: list[dict[str, Any]]
    calibration_examples: list[dict[str, Any]]
    created_at: datetime
    content_hash: HashValue


class RequirementBriefView(StrictModel):
    schema_version: str
    requirement_brief_id: Identifier
    purchase_brief_id: Identifier
    purchase_brief_version: int
    version: int
    visibility: RequestVisibility
    category_id: Identifier
    intent: str
    desired_outcome: str
    team: dict[str, Any]
    data_profile: dict[str, Any]
    hard_requirements: list[dict[str, Any]]
    preferences: list[dict[str, Any]]
    allowed_stack_context: dict[str, Any]
    seller_questions: list[str]
    expires_at: datetime
    content_hash: HashValue


class CalibrationRunCreate(StrictModel):
    known_failure_candidate_id: Identifier = "fixture_low_price_policy_fail"
    current_approach_id: Identifier = "current_manual_recap"
    expected_qualifier_candidate_id: Identifier = "fixture_selected_fit"
    proposed_changes: list[dict[str, Any]] = Field(default_factory=list)


class CalibrationRunView(StrictModel):
    id: Identifier
    purchase_request_id: Identifier
    purchase_brief_version: int
    results: list[dict[str, Any]]
    proposal: dict[str, Any] | None = None
    proposal_effective: Literal[False] = False


class CandidateActionCreate(StrictModel):
    action: CandidateAction
    reason: str = Field(min_length=3, max_length=1000)
    proposed_criterion_change: dict[str, Any] | None = None


class CandidateActionView(StrictModel):
    id: Identifier
    request_id: Identifier
    candidate_id: Identifier
    action: CandidateAction
    reason: str
    engagement_id: Identifier | None = None
    proposal_id: Identifier | None = None
    contact_details_revealed: Literal[False] = False
    proposal_effective: Literal[False] = False


class ConsentCreate(StrictModel):
    consent: bool
    scope: Literal["CONTACT_EXCHANGE"] = "CONTACT_EXCHANGE"


class EngagementView(StrictModel):
    id: Identifier
    status: EngagementStatus
    buyer_consented: bool
    seller_consented: bool
    contact_details: dict[str, str] | None = None


class DecisionLedgerView(StrictModel):
    schema_version: str
    decision_id: Identifier
    request_id: Identifier
    purchase_brief_id: Identifier
    purchase_brief_version: int
    requirement_brief_id: Identifier
    requirement_brief_version: int
    buyer_passport_version: int
    stack_snapshot: int
    policy_version: int
    evaluated_universe: dict[str, Any]
    candidate_results: list[dict[str, Any]]
    solution_plans: list[dict[str, Any]]
    selected_solution_plan_id: Identifier
    counterfactual: dict[str, Any]
    decision_hash: HashValue
    created_at: datetime


class CounterfactualView(StrictModel):
    decision_id: Identifier
    generic_selected_candidate_id: Identifier
    company_aware_selected_candidate_id: Identifier
    decisive_private_fact_ids: list[Identifier]
    generic_result_hash: HashValue
    company_aware_result_hash: HashValue
    changed: bool
    explanation: str
    remaining_uncertainties: list[str] = Field(default_factory=list)


class DecisionSimulationCreate(StrictModel):
    context_mode: Literal["COMPANY_AWARE", "GENERIC_REQUEST_ONLY"] = "COMPANY_AWARE"
    preference_weight_overrides: dict[Identifier, int] = Field(default_factory=dict)
    reason: str = Field(min_length=3, max_length=1000)


class DecisionSimulationView(StrictModel):
    simulation_id: Identifier
    decision_id: Identifier
    context_mode: Literal["COMPANY_AWARE", "GENERIC_REQUEST_ONLY"]
    baseline_solution_plan_id: Identifier
    simulated_solution_plan_id: Identifier
    simulated_order: list[Identifier]
    input_hash: HashValue
    result_hash: HashValue
    authoritative: Literal[False] = False
    ranking_effect: Literal[False] = False


class EvaluationReplayView(StrictModel):
    evaluation_run_id: Identifier
    decision_id: Identifier
    stored_decision_hash: HashValue
    replayed_decision_hash: HashValue
    ordering_matches: bool
    statuses_match: bool
    counterfactual_matches: bool
    byte_stable: bool


class ProposalDecisionCreate(StrictModel):
    reason: str = Field(min_length=3, max_length=1000)


class ProposalDecisionView(StrictModel):
    proposal_id: Identifier
    base_purchase_brief_id: Identifier
    status: Literal["ACCEPTED", "REJECTED"]
    resulting_purchase_brief_id: Identifier | None = None
    resulting_version: int | None = None
    resulting_decision_id: Identifier | None = None
    resulting_decision_hash: HashValue | None = None
    resulting_decision_version: int | None = None
    ranking_effect: bool


class PurchaseIntentCreate(StrictModel):
    solution_plan_id: Identifier | None = None


class PurchaseIntentView(StrictModel):
    schema_version: str
    purchase_intent_id: Identifier
    organization_id: Identifier
    decision_id: Identifier
    decision_version: int
    decision_hash: HashValue
    selection_id: Identifier
    solution_plan_id: Identifier
    stack_patch_id: Identifier
    purchase_intent_group_id: Identifier | None = None
    procurement_plan_id: Identifier
    procurement_gate_result_hash: HashValue
    pack_id: Identifier
    pack_version: int
    offer_id: Identifier
    offer_version: int
    quote_id: Identifier
    quote_version: int
    quote_expires_at: datetime
    merchant: dict[str, str]
    approved_merchant_chain_id: Identifier
    amount: MoneyAmount
    currency: Currency
    line_items: list[dict[str, Any]]
    expected_fulfillments: list[dict[str, Any]]
    fulfillment_completion_policy: str
    buyer_legal_entity_id: Identifier
    seller_contracting_entity_id: Identifier
    billing_identity_id: Identifier
    cost_center_id: Identifier
    purchase_order_ref: str | None = None
    merchant_subtotal: MoneyAmount
    tax_amount: MoneyAmount
    fee_amount: MoneyAmount
    fee_schedule_version: Identifier
    contract_version_id: Identifier
    landed_total: MoneyAmount
    approval_policy_version: int
    approval_requirement_set_id: Identifier
    approval_plan_hash: HashValue
    approval_status: ApprovalStatus
    payment_status: PaymentStatus
    fulfillment_status: FulfillmentStatus
    intent_hash: HashValue
    locked_at: datetime


class ApprovalRequestCreate(StrictModel):
    """The server resolves approval policy from the locked Purchase Brief."""


class ApprovalRequestView(StrictModel):
    id: Identifier
    purchase_intent_id: Identifier
    intent_hash: HashValue
    status: ApprovalStatus
    required_roles: list[str]
    approved_roles: list[str]
    expires_at: datetime


class ApprovalCreate(StrictModel):
    intent_hash: HashValue
    actor_role: str


class ApprovalRejectCreate(StrictModel):
    intent_hash: HashValue
    actor_role: str
    reason: str = Field(min_length=3, max_length=1000)


class ApprovalRevokeCreate(StrictModel):
    intent_hash: HashValue
    actor_role: str
    reason: str = Field(min_length=3, max_length=1000)


class PravaSessionCreate(StrictModel):
    return_url: HttpsUrl


class PravaSessionView(StrictModel):
    id: Identifier
    purchase_intent_id: Identifier
    status: PaymentStatus
    hosted_url: str | None = None
    expires_at: datetime | None = None
    production_provider: Literal["PRAVA"] = "PRAVA"
    production_verified: Literal[False] = False
    setup_blocked: bool
    missing_configuration: list[str] = Field(default_factory=list)


class PravaBrowserReturnCreate(StrictModel):
    state: Annotated[
        str,
        StringConstraints(
            min_length=16,
            max_length=256,
            pattern=r"^[A-Za-z0-9._~-]+$",
        ),
    ]
    return_url: HttpsUrl


class PurchaseStatusView(StrictModel):
    purchase_intent_id: Identifier
    approval_status: ApprovalStatus
    payment_status: PaymentStatus
    fulfillment_status: FulfillmentStatus
    purchase_state: Literal[
        "AWAITING_APPROVAL",
        "APPROVED_NOT_STARTED",
        "PAYMENT_IN_PROGRESS",
        "PAYMENT_NOT_COMPLETED",
        "PAYMENT_UNCERTAIN",
        "PAID_UNFULFILLED",
        "PURCHASE_FULFILLED",
        "REFUND_PENDING",
        "REFUNDED",
    ]
    deployment_state: Literal["NOT_STARTED", "STAGED", "ACTIVE"]
    outcome_state: Literal["NOT_MEASURED", "MEASURING", "ACHIEVED", "NOT_ACHIEVED", "INCONCLUSIVE"]


class ReversalCreate(StrictModel):
    kind: Literal["CANCELLATION", "REFUND"]
    requested_amount: MoneyAmount | None = None
    reason_code: Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]{2,79}$")]
    reason: str = Field(min_length=3, max_length=1000)


class ReversalView(StrictModel):
    id: Identifier
    purchase_intent_id: Identifier
    intent_hash: HashValue
    kind: Literal["CANCELLATION", "REFUND"]
    status: Literal[
        "REQUESTED",
        "PROVIDER_PENDING",
        "PARTIALLY_REFUNDED",
        "REFUNDED",
        "REJECTED",
        "FAILED_RETRYABLE",
        "COMPENSATION_REQUIRED",
        "COMPENSATED",
        "CANCELLED",
    ]
    requested_amount: MoneyAmount
    refunded_amount: MoneyAmount
    currency: Currency
    provider_confirmed: bool
    provider_action_required: bool
    safe_error_code: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class OutcomeCheckpointCreate(StrictModel):
    metric: str = Field(min_length=1, max_length=200)
    observed_value: MetricValue
    observed_at: datetime
    source_class: Literal["SYSTEM_OBSERVATION", "HUMAN_ATTESTATION", "PROVIDER_REPORT"]
    source_reference: str = Field(min_length=3, max_length=500)


class OutcomeCheckpointView(StrictModel):
    id: Identifier
    purchase_intent_id: Identifier
    decision_id: Identifier
    decision_hash: HashValue
    solution_plan_id: Identifier
    metric: str
    target_value: MetricValue
    target_operator: Literal["gte", "lte"]
    observed_value: MetricValue
    checkpoint_days: int = Field(ge=1, le=365)
    measurement_started_at: datetime
    checkpoint_due_at: datetime
    observed_at: datetime
    state: Literal["MEASURING", "ACHIEVED", "NOT_ACHIEVED", "INCONCLUSIVE"]
    source_class: Literal["SYSTEM_OBSERVATION", "HUMAN_ATTESTATION", "PROVIDER_REPORT"]
    source_reference_hash: HashValue
    checkpoint_hash: HashValue
    preference_proposal: dict[str, Any] | None = None


class ReceiptView(StrictModel):
    schema_version: str
    receipt_id: Identifier
    purchase_id: Identifier
    purchase_intent_id: Identifier
    request_id: Identifier
    decision_id: Identifier
    decision_hash: HashValue
    pack_id: Identifier
    pack_version: int = Field(ge=1)
    offer_id: Identifier
    offer_version: int = Field(ge=1)
    quote_id: Identifier
    quote_version: int = Field(ge=1)
    approval_request_id: Identifier
    approval_intent_hash: HashValue
    prava_session_reference: Identifier
    prava_order_reference: Identifier
    merchant_order_id: Identifier
    merchant: dict[str, str]
    amount: MoneyAmount
    currency: Currency
    payment_status: Literal["PRAVA_COMPLETED"]
    fulfillment_status: Literal["VERIFIED"]
    entitlement_ids: list[Identifier] = Field(min_length=1)
    stack_patch_id: Identifier
    stack_patch_status: Literal["STAGED"]
    issued_at: datetime
    environment: Literal["fixture", "sandbox", "production"]
    adapter_label: str = Field(min_length=1, max_length=100)
    production_success: bool


class StackfileView(StrictModel):
    organization_id: Identifier
    current: dict[str, Any]
    proposed_patch: StackPatchView | None = None
