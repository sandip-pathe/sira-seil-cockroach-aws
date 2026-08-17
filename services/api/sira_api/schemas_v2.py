"""Action-neutral public contracts for the Decision Room and seller evidence flow."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from domain.enums import (
    ActorRole,
    ApprovalStatus,
    DecisionOutcome,
    DecisionStage,
    DecisionVersionState,
    ExecutionStepStatus,
    ExecutionStepType,
    OperationStatus,
    OptionFeedbackAction,
    PackAuthority,
    PlanSelectionState,
    RankStability,
    RequestVisibility,
    ResultArtifactType,
    SellerEvidenceState,
    SellerExportFormat,
    SellerReviewDecision,
    SolutionActionType,
    SolutionOptionStatus,
    SolutionPlanLifecycle,
    StackRisk,
    StageStatus,
    TruthValue,
    UIActionCapability,
)

from .schemas import Currency, HashValue, Identifier, MoneyAmount, StrictModel

ExecutableActionType = Literal[
    "REUSE_EXISTING",
    "CONFIGURE_EXISTING",
    "NO_ACTION",
    "BUY",
    "RENEW",
    "RESIZE",
    "REPLACE",
    "CANCEL",
]


class ComponentStatus(StrEnum):
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
    ADVISORY_ONLY = "ADVISORY_ONLY"


class ActionDescriptor(StrictModel):
    id: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")
    label: str = Field(min_length=1, max_length=100)
    method: Literal["GET", "POST", "PATCH", "DELETE"]
    href: str = Field(pattern=r"^/", max_length=500)
    requires_confirmation: bool
    expires_at: datetime | None = None


class BlockingTask(StrictModel):
    id: Identifier
    title: str = Field(min_length=1, max_length=200)
    owner_role: ActorRole
    due_at: datetime | None
    expires_at: datetime | None
    status: Literal["OPEN", "WAITING", "BLOCKED", "COMPLETED", "EXPIRED"]
    href: str = Field(pattern=r"^/", max_length=500)


class ActiveOperation(StrictModel):
    id: Identifier
    kind: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")
    status: OperationStatus
    current_checkpoint_id: Identifier | None
    last_successful_checkpoint_id: Identifier | None
    owner_role: ActorRole
    started_at: datetime
    updated_at: datetime
    retryable: bool
    safe_to_leave: bool
    recovery_action: ActionDescriptor | None = None


class StageHistoryEntry(StrictModel):
    stage: DecisionStage
    status: StageStatus
    checkpoint_id: Identifier | None
    completed_at: datetime | None = None
    href: str = Field(min_length=1, max_length=500)


class VersionLinks(StrictModel):
    current: str = Field(pattern=r"^/", max_length=500)
    previous: str | None = Field(default=None, pattern=r"^/", max_length=500)
    superseded_by: str | None = Field(default=None, pattern=r"^/", max_length=500)


class WorkflowActor(StrictModel):
    role: ActorRole
    capabilities: list[UIActionCapability]


class WorkflowProjection(StrictModel):
    current_stage: DecisionStage
    actor: WorkflowActor
    available_actions: list[ActionDescriptor]
    blocking_tasks: list[BlockingTask]
    active_operation: ActiveOperation | None = None
    stage_history: list[StageHistoryEntry]
    version_links: VersionLinks


class DecisionRequestHeader(StrictModel):
    id: Identifier
    intent: str = Field(min_length=1, max_length=500)
    status: Literal[
        "DRAFT",
        "DISCOVERING",
        "DECISION_READY",
        "ACTION_IN_PROGRESS",
        "RESULT_READY",
        "COMPLETED",
    ]
    decision_version: int = Field(ge=1)
    decision_state: DecisionVersionState
    superseded_by: Identifier | None = None
    evaluation_mode: Literal["DEVELOPMENT_FIXTURE_NON_PRODUCTION"]
    scenario_id: Identifier
    fixture_label: Literal["DEVELOPMENT_FIXTURE_NON_PRODUCTION"]


class EvaluationSummary(StrictModel):
    id: Identifier
    payload_hash: HashValue
    decision_hash: HashValue
    pipeline_version: Identifier
    engine_version: Identifier


class CompanyFactProjection(StrictModel):
    fact_id: Identifier
    display_name: str = Field(min_length=1, max_length=100)
    display_value: str = Field(min_length=1, max_length=200)
    provenance_label: str = Field(min_length=1, max_length=200)
    sensitivity: Literal["internal", "confidential", "restricted"]


class CompanyContextProjection(StrictModel):
    facts_used: list[CompanyFactProjection]
    hidden_fact_count: int = Field(ge=0)
    company_profile_version: int = Field(ge=1)
    company_stack_snapshot: int = Field(ge=1)


class DisclosurePreview(StrictModel):
    source_id: Identifier
    source_version: int = Field(ge=1)
    source_hash: HashValue
    recipient: Literal["SELLER"]
    purpose: str = Field(min_length=1, max_length=240)
    exact_fields: list[str] = Field(min_length=1, max_length=32)
    transformations: list[str] = Field(max_length=16)
    omitted_categories: list[str] = Field(min_length=1, max_length=16)
    expires_at: datetime
    status: Literal["ACTIVE", "EXPIRED"]


class CoverageProjection(StrictModel):
    raw_record_count: int = Field(ge=0)
    product_evidence_option_count: int = Field(ge=0)
    canonical_product_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    generated_solution_plan_count: int = Field(ge=0)
    evaluated_solution_plan_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    statement: str = Field(min_length=1, max_length=500)


class ExactRatioView(StrictModel):
    numerator: int = Field(ge=0)
    denominator: int = Field(gt=0)


class ExactScoreView(ExactRatioView):
    display: MoneyAmount


class PreferenceScoreBounds(StrictModel):
    conservative: ExactScoreView
    optimistic: ExactScoreView


class BoundUnavailableView(StrictModel):
    status: Literal["BOUND_UNAVAILABLE"] = "BOUND_UNAVAILABLE"
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")


class StackRiskBounds(StrictModel):
    base: StackRisk | BoundUnavailableView
    lower: StackRisk | BoundUnavailableView
    upper: StackRisk | BoundUnavailableView


class MoneyViewV2(StrictModel):
    amount: MoneyAmount
    currency: Literal["USD"]


class TotalCostBounds(StrictModel):
    low: MoneyViewV2 | BoundUnavailableView
    base: MoneyViewV2 | BoundUnavailableView
    high: MoneyViewV2 | BoundUnavailableView


class CoverageBounds(StrictModel):
    conservative: ExactRatioView | BoundUnavailableView
    optimistic: ExactRatioView | BoundUnavailableView


class EvidenceCoverageView(StrictModel):
    hard: ExactRatioView
    decision_material: CoverageBounds


class EvidenceAgeBounds(StrictModel):
    lower: ExactRatioView | BoundUnavailableView
    upper: ExactRatioView | BoundUnavailableView


class DefaultComparisonCost(MoneyViewV2):
    horizon_days: int = Field(ge=1)


class DefaultComparison(StrictModel):
    cost: DefaultComparisonCost
    stack_change: str = Field(min_length=1, max_length=500)
    next_action: str = Field(min_length=1, max_length=120)


class ProductEvidenceComponent(StrictModel):
    product_evidence_id: Identifier | None
    current_instance_id: Identifier | None
    action: Literal["ADD", "REMOVE", "RETAIN", "CONFIGURE", "RENEW", "RESIZE", "CANCEL", "REUSE"]
    publisher_authority: PackAuthority | None
    verification_summary: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def one_component_source(self) -> ProductEvidenceComponent:
        if (self.product_evidence_id is None) == (self.current_instance_id is None):
            raise ValueError("exactly one component source is required")
        return self


class MerchantProjection(StrictModel):
    id: Identifier
    offer_id: Identifier
    candidate_id: Identifier


class EvidenceSummary(StrictModel):
    id: Identifier
    label: str = Field(min_length=1, max_length=200)
    publisher_authority: PackAuthority
    verification_state: Literal[
        "VERIFIED",
        "SELLER_ASSERTED",
        "STALE",
        "INSUFFICIENT",
        "CONFLICTING",
        "REVOKED",
    ]
    href: str = Field(pattern=r"^/", max_length=500)


class SolutionOption(StrictModel):
    id: Identifier
    action_type: SolutionActionType
    label: str = Field(min_length=1, max_length=200)
    status: SolutionOptionStatus
    reason_code: str | None = Field(default=None, max_length=80)
    reason: str = Field(min_length=1, max_length=500)
    default_comparison: DefaultComparison
    preference_score: PreferenceScoreBounds
    ordering_frontier_member: bool
    resolution_frontier_member: bool
    quote_required: bool
    quote_policy_reason: str = Field(min_length=1, max_length=120)
    permitted_resolution: str | None = Field(default=None, max_length=300)
    stack_risk: StackRiskBounds
    total_cost: TotalCostBounds
    evidence_coverage: EvidenceCoverageView
    maximum_evidence_age_ratio: EvidenceAgeBounds
    evidence_frontier: list[EvidenceFrontierItem]
    components: list[ProductEvidenceComponent]
    merchant: MerchantProjection | None = None
    evidence: list[EvidenceSummary]
    seller_positioning: str | None = Field(default=None, max_length=500)


class EvidenceFrontierItem(StrictModel):
    criterion_id: Identifier
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")
    option_ids: list[Identifier] = Field(min_length=1)
    permitted_resolution: str | None = Field(default=None, max_length=300)


class RankStabilityProjection(StrictModel):
    status: RankStability
    summary: str = Field(min_length=1, max_length=500)
    evidence_frontier: list[EvidenceFrontierItem]


class ExecutionStep(StrictModel):
    id: Identifier
    type: ExecutionStepType
    status: ExecutionStepStatus
    owner_role: ActorRole
    started_at: datetime | None = None
    completed_at: datetime | None = None
    checkpoint_id: Identifier | None = None
    artifact_id: Identifier | None = None
    blocker: str | None = Field(default=None, max_length=300)
    available_action: ActionDescriptor | None = None


class SelectedActionPlan(StrictModel):
    id: Identifier
    action_type: ExecutableActionType
    state: PlanSelectionState
    selected_at: datetime
    selected_by_role: ActorRole
    selection_id: Identifier
    decision_version: int = Field(ge=1)
    decision_hash: HashValue
    execution_steps: list[ExecutionStep]
    href: str = Field(min_length=1, max_length=500)


class StackChangeProjection(StrictModel):
    id: Identifier
    status: Literal["PROPOSED", "STAGED", "APPLIED", "REJECTED", "SUPERSEDED"]
    summary: str = Field(min_length=1, max_length=500)
    added: list[Identifier]
    removed: list[Identifier]
    staged_for_removal: list[Identifier]
    retained: list[Identifier]
    dependency_changed: list[Identifier]
    href: str = Field(min_length=1, max_length=500)


class ApprovalProjection(StrictModel):
    required: bool
    status: ApprovalStatus
    requirement_set_id: Identifier | None = None
    owner_roles: list[ActorRole]
    completed_count: int = Field(ge=0)
    required_count: int = Field(ge=0)
    rejected_by_role: ActorRole | None = None
    expires_at: datetime | None = None
    href: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def not_required_is_empty(self) -> ApprovalProjection:
        if not self.required and (
            self.status != ApprovalStatus.NOT_REQUIRED or self.required_count
        ):
            raise ValueError("non-required approval must use NOT_REQUIRED with no requirements")
        return self


class PaymentHandoffProjection(StrictModel):
    id: Identifier
    purchase_intent_id: Identifier
    approval_request_id: Identifier
    intent_hash: HashValue
    handoff_hash: HashValue
    destination_url: str = Field(pattern=r"^https://", max_length=2000)
    recipient: str = Field(min_length=1, max_length=200)
    amount: MoneyAmount
    currency: Currency
    reference: str = Field(min_length=1, max_length=160)
    status: Literal["READY", "OPENED", "EXPIRED", "CANCELLED"]
    expires_at: datetime
    opened_at: datetime | None = None
    href: str = Field(min_length=1, max_length=500)


class ResultArtifact(StrictModel):
    id: Identifier
    type: ResultArtifactType
    verification_state: Literal["PENDING", "VERIFIED", "FAILED", "REVOKED"]
    actor_ref: Identifier | None
    owner_role: ActorRole
    occurred_at: datetime
    verified_at: datetime | None = None
    safe_label: str = Field(min_length=1, max_length=200)
    href: str = Field(pattern=r"^/", max_length=500)
    stack_patch_id: Identifier | None


class DecisionView(StrictModel):
    request: DecisionRequestHeader
    workflow: WorkflowProjection
    evaluation: EvaluationSummary
    company_context: CompanyContextProjection
    disclosure_preview: DisclosurePreview
    coverage: CoverageProjection
    decision_outcome: DecisionOutcome
    rank_stability: RankStabilityProjection
    solution_options: list[SolutionOption]
    selected_action_plan: SelectedActionPlan | None = None
    stack_change: StackChangeProjection | None = None
    approval: ApprovalProjection | None = None
    payment_handoff: PaymentHandoffProjection | None = None
    result_artifacts: list[ResultArtifact]


class FrozenVersions(StrictModel):
    request: Identifier
    company_profile: Identifier
    stackfile: Identifier
    registry: Identifier
    pack_set: Identifier
    offer_set: Identifier
    taxonomy: Identifier
    normalization: Identifier
    policy: Identifier
    fx: Identifier
    pipeline: Identifier
    engine: Identifier


class EvaluationRecord(StrictModel):
    evaluation_id: Identifier
    evaluated_at: datetime
    evaluation_payload_hash: HashValue
    frozen_versions: FrozenVersions
    ranked_solution_plan_ids: list[Identifier]
    ordering_frontier_plan_ids: list[Identifier]
    bound_unavailable_plan_ids: list[Identifier]


class IdentityMergeView(StrictModel):
    canonical_id: Identifier
    merged_record_id: Identifier
    reasons: list[str] = Field(min_length=1)


class EvaluatedUniverseView(StrictModel):
    raw_record_count: int = Field(ge=0)
    product_evidence_option_count: int = Field(ge=0)
    canonical_product_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    generated_solution_plan_count: int = Field(ge=0)
    evaluated_solution_plan_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    included_record_ids: list[Identifier]
    excluded_record_ids: list[Identifier]
    identity_merges: list[IdentityMergeView]
    coverage_statement: str = Field(min_length=1, max_length=500)


class GateReasonView(StrictModel):
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")
    status: ComponentStatus
    detail: str = Field(min_length=1, max_length=500)


class GateResultView(StrictModel):
    gate_id: Identifier
    truth: TruthValue
    reasons: list[GateReasonView]
    evaluated_predicates: list[str]
    permitted_resolution: str | None = Field(max_length=300)


class EvidenceAssessmentView(StrictModel):
    evidence_id: Identifier
    record_id: Identifier
    field: str = Field(pattern=r"^[a-z][a-z0-9_.]{2,127}$")
    source_class: str = Field(min_length=1, max_length=100)
    verification_method: str = Field(min_length=1, max_length=100)
    scope_match: bool
    reconstructable: bool
    freshness_current: bool | None
    disputed: bool
    revoked: bool
    state: Literal["ACCEPTABLE", "UNKNOWN", "STALE", "CONFLICT"]
    reasons: list[str]
    age_bounds: EvidenceAgeBounds | None


class DecisionComponentResult(StrictModel):
    component_id: Identifier
    name: str = Field(min_length=1, max_length=200)
    pack_id: Identifier | None
    pack_version: int | None = Field(ge=1)
    current_instance_id: Identifier | None
    publisher_authority: PackAuthority | None
    status: ComponentStatus
    primary_reason: GateReasonView | None
    gate_results: list[GateResultView]
    evidence_assessments: list[EvidenceAssessmentView]

    @model_validator(mode="after")
    def one_component_source(self) -> DecisionComponentResult:
        if (self.pack_id is None) == (self.current_instance_id is None):
            raise ValueError("exactly one Decision component source is required")
        if (self.pack_id is None) != (self.pack_version is None):
            raise ValueError("Pack ID and version must be present together")
        return self


class PlanComponentView(StrictModel):
    component_id: Identifier
    source_type: Literal["PRODUCT_EVIDENCE", "CURRENT_INSTANCE", "CONTRACT", "DEPENDENCY"]
    source_id: Identifier
    action_type: SolutionActionType


class ScoreComponentView(StrictModel):
    criterion_id: Identifier
    weight: int = Field(ge=1, le=5)
    coverage_weight: int = Field(ge=1, le=5)
    conservative_satisfaction: ExactRatioView
    optimistic_satisfaction: ExactRatioView
    conservative_contribution: ExactRatioView
    optimistic_contribution: ExactRatioView
    evidence_ids: list[Identifier]
    evidence_state: Literal["ACCEPTABLE", "UNKNOWN", "STALE", "CONFLICT"]
    prior_label: str | None = Field(max_length=200)


class CostLineItemBoundsView(StrictModel):
    type: Literal[
        "MERCHANT_SUBTOTAL",
        "SIRA_TRANSACTION_FEE",
        "TAX",
        "CONTRACT_COST",
        "MIGRATION_COST",
        "IMPLEMENTATION_COST",
    ]
    low: MoneyViewV2 | BoundUnavailableView
    base: MoneyViewV2 | BoundUnavailableView
    high: MoneyViewV2 | BoundUnavailableView
    schedule_version: str | None = Field(max_length=100)


class PlanDimensionsView(StrictModel):
    preference: PreferenceScoreBounds
    stack_risk: StackRiskBounds
    total_cost: TotalCostBounds
    cost_line_items: list[CostLineItemBoundsView]
    payment_required: bool
    hard_coverage: ExactRatioView
    decision_material_coverage: CoverageBounds
    maximum_evidence_age_ratio: EvidenceAgeBounds
    universe_coverage: ExactRatioView
    unresolved_count: int = Field(ge=0)
    conflicting_count: int = Field(ge=0)
    bound_unavailable_reasons: list[str]


class SolutionPlanRecord(StrictModel):
    solution_plan_id: Identifier
    action_type: SolutionActionType
    components: list[PlanComponentView]
    component_hash: HashValue
    construction_lifecycle: Literal["CANDIDATE"]
    lifecycle: SolutionPlanLifecycle
    status: ComponentStatus
    primary_reason: GateReasonView | None
    gate_results: list[GateResultView]
    score_components: list[ScoreComponentView]
    dimensions: PlanDimensionsView
    stable_action_ids: list[Identifier] = Field(min_length=1)
    rank: int | None = Field(ge=1)
    ordering_frontier_member: bool
    resolution_frontier_member: bool
    quote_required: bool
    quote_policy_reason: str = Field(min_length=1, max_length=100)
    permitted_resolution: str | None = Field(max_length=300)
    autonomous_execution_allowed: bool
    stack_patch_id: Identifier | None


class CounterfactualRecordView(StrictModel):
    outcome: Literal["WINNER_CHANGED", "NO_SMALL_COUNTERFACTUAL_FOUND"]
    removed_fact_ids: list[Identifier] = Field(max_length=3)
    alternative_fact_id_sets: list[list[Identifier]]
    tested_limit: Literal[3]
    before_evaluation_payload_hash: HashValue
    after_evaluation_payload_hash: HashValue | None
    generic_evaluation_payload_hash: HashValue
    before_selected_plan_id: Identifier | None
    after_selected_plan_id: Identifier | None
    generic_selected_plan_id: Identifier | None
    changed_gate_ids: list[Identifier]
    record_hash: HashValue


class DecisionLedgerV2(StrictModel):
    schema_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    decision_id: Identifier
    decision_version: int = Field(ge=1)
    decision_state: DecisionVersionState
    supersedes_decision_id: Identifier | None
    request_id: Identifier
    purchase_brief_id: Identifier
    purchase_brief_version: int = Field(ge=1)
    requirement_brief_id: Identifier
    requirement_brief_version: int = Field(ge=1)
    company_profile_version: int = Field(ge=1)
    stack_snapshot: int = Field(ge=1)
    policy_version: int = Field(ge=1)
    evaluation: EvaluationRecord
    evaluated_universe: EvaluatedUniverseView
    component_results: list[DecisionComponentResult]
    solution_plans: list[SolutionPlanRecord] = Field(min_length=1)
    decision_outcome: DecisionOutcome
    selected_solution_plan_id: Identifier | None
    rank_stability: RankStabilityProjection
    counterfactuals: list[CounterfactualRecordView] = Field(min_length=1)
    decision_hash: HashValue
    created_at: datetime


class DecisionRequestCreate(StrictModel):
    intent: str = Field(min_length=10, max_length=2000)
    scenario_id: Identifier | None = None
    desired_outcome: str | None = Field(default=None, max_length=1000)
    deadline: date | None = None
    visibility: RequestVisibility = RequestVisibility.SELECTIVE
    incumbent_instance_id: Identifier | None = None
    mission_id: Identifier | None = None


class DecisionRequestView(StrictModel):
    id: Identifier
    intent: str
    status: str
    visibility: RequestVisibility
    owner_role: ActorRole
    deadline: date | None = None
    current_stage: DecisionStage
    blocker: str | None = None
    last_checkpoint: str
    current_decision_version: int | None = Field(default=None, ge=1)
    evaluation_mode: Literal[
        "SCENARIO_SELECTION_REQUIRED",
        "DEVELOPMENT_FIXTURE_NON_PRODUCTION",
        "PROVIDER_CONFIGURATION_REQUIRED",
    ]
    scenario_id: Identifier | None = None
    fixture_label: Literal["DEVELOPMENT_FIXTURE_NON_PRODUCTION"] | None = None
    href: str


class DecisionIndexView(StrictModel):
    active: list[DecisionRequestView]
    history: list[DecisionRequestView]
    available_actions: list[ActionDescriptor]


class DecisionRuleItem(StrictModel):
    id: Identifier
    kind: Literal["HARD_GATE", "PREFERENCE", "STACK_POLICY", "APPROVAL"]
    label: str
    weight: int | None = Field(default=None, ge=0)
    required: bool
    version: int = Field(ge=1)


class DecisionRulesView(StrictModel):
    id: Identifier
    request_id: Identifier
    version: int = Field(ge=1)
    content_hash: HashValue
    rules: list[DecisionRuleItem]


class OptionFeedbackCreate(StrictModel):
    action: OptionFeedbackAction
    reason: str = Field(min_length=3, max_length=1000)
    proposed_criterion_change: dict[Identifier, int] | None = None


class OptionFeedbackView(StrictModel):
    id: Identifier
    request_id: Identifier
    solution_plan_id: Identifier
    action: OptionFeedbackAction
    reason: str
    engagement_id: Identifier | None = None
    proposal_id: Identifier | None = None
    contact_details_revealed: Literal[False] = False
    ranking_effect: Literal[False] = False


class PlanSelectionCreate(StrictModel):
    solution_plan_id: Identifier
    decision_version: int = Field(ge=1)
    decision_hash: HashValue


class PlanSelectionView(StrictModel):
    selection_id: Identifier
    source_decision_id: Identifier
    selected_decision_id: Identifier
    solution_plan_id: Identifier
    decision_version: int = Field(ge=1)
    decision_hash: HashValue
    state: PlanSelectionState
    action_run_href: str | None = None


class ActionRunCreate(StrictModel):
    solution_plan_id: Identifier
    decision_version: int = Field(ge=1)
    decision_hash: HashValue


class ActionRunView(StrictModel):
    schema_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    action_run_id: Identifier
    workflow_id: Identifier
    decision_id: Identifier
    decision_version: int = Field(ge=1)
    decision_hash: HashValue
    selection_id: Identifier
    solution_plan_id: Identifier
    action_type: ExecutableActionType
    status: OperationStatus
    current_step_id: Identifier | None
    last_successful_checkpoint_id: Identifier | None
    owner_role: ActorRole
    blocking_task: BlockingTask | None = None
    recovery_action: ActionDescriptor | None = None
    execution_steps: list[ExecutionStep] = Field(min_length=1)
    payment_handoff: PaymentHandoffProjection | None
    result_artifacts: list[ResultArtifact]
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    @model_validator(mode="after")
    def completed_run_has_proof(self) -> ActionRunView:
        if self.status == OperationStatus.COMPLETED and (
            self.completed_at is None or not self.result_artifacts
        ):
            raise ValueError("completed action runs require verified Result proof")
        return self


ScalarEvidenceValue = str | int | bool | list[str] | None


class SellerCapability(StrEnum):
    CLAIM_PRODUCT = "CLAIM_PRODUCT"
    VIEW_OWN_DRAFT = "VIEW_OWN_DRAFT"
    EDIT_CLAIMS = "EDIT_CLAIMS"
    ADD_EVIDENCE = "ADD_EVIDENCE"
    SUBMIT_REVIEW = "SUBMIT_REVIEW"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    APPROVE_REVIEW = "APPROVE_REVIEW"
    REJECT_REVIEW = "REJECT_REVIEW"
    PUBLISH = "PUBLISH"
    SUSPEND = "SUSPEND"
    EXPORT = "EXPORT"
    VIEW_ACTIVITY_METRICS = "VIEW_ACTIVITY_METRICS"
    RETRY_PUBLICATION = "RETRY_PUBLICATION"


class SellerProductSearchItem(StrictModel):
    id: Identifier
    name: str
    category: str
    publisher_authority: PackAuthority
    state: SellerEvidenceState
    public_summary: str
    href: str


class SellerProductSearchView(StrictModel):
    results: list[SellerProductSearchItem]


class SellerClaimCreate(StrictModel):
    authority_proof_reference: str = Field(min_length=3, max_length=500)
    requested_role: ActorRole = ActorRole.SELLER_EDITOR


class SellerClaimView(StrictModel):
    claim_id: Identifier
    product_id: Identifier
    state: SellerEvidenceState
    submitted_at: datetime
    safe_reason: str | None = None


class SellerPackHealth(StrictModel):
    status: Literal["HEALTHY", "NEEDS_ATTENTION", "BLOCKED"]
    required_claim_count: int = Field(ge=0)
    complete_claim_count: int = Field(ge=0)
    stale_claim_count: int = Field(ge=0)
    conflict_count: int = Field(ge=0)


class SellerValidationGap(StrictModel):
    id: Identifier
    field: str = Field(pattern=r"^[a-z][a-z0-9_.]{2,127}$")
    safe_message: str = Field(min_length=1, max_length=300)
    href: str = Field(pattern=r"^/", max_length=500)


class SellerValidation(StrictModel):
    status: Literal["NOT_RUN", "VALID", "HAS_GAPS", "CONFLICT"]
    gaps: list[SellerValidationGap]


class SellerReviewSummary(StrictModel):
    review_id: Identifier
    revision_hash: HashValue
    status: Literal["PENDING", "COMPLETED"]
    decision: SellerReviewDecision | None
    reviewer_role: Literal[ActorRole.SELLER_REVIEWER, ActorRole.PLATFORM_OPERATOR]
    reason: str | None = Field(max_length=500)
    recorded_at: datetime | None


class SellerReusableAnswers(StrictModel):
    published_version: int | None = Field(ge=1)
    published_answer_count: int = Field(ge=0)
    formats: list[SellerExportFormat]
    href: str | None = Field(pattern=r"^/", max_length=500)


class SellerActivityMetrics(StrictModel):
    window_start: datetime
    window_end: datetime
    answer_rendered_count: int = Field(ge=0)
    seller_handoff_requested_count: int = Field(ge=0)
    observed_self_service_count: int = Field(ge=0)
    measurement_label: Literal["OBSERVATIONAL_NOT_CAUSAL"] = "OBSERVATIONAL_NOT_CAUSAL"
    href: str = Field(pattern=r"^/", max_length=500)


class SellerEvidenceProduct(StrictModel):
    id: Identifier
    name: str = Field(min_length=1, max_length=200)
    seller_state: SellerEvidenceState
    current_version: int = Field(ge=1)
    href: str = Field(pattern=r"^/", max_length=500)


class SellerActor(StrictModel):
    role: Literal[ActorRole.SELLER_EDITOR, ActorRole.SELLER_REVIEWER, ActorRole.PLATFORM_OPERATOR]
    capabilities: list[SellerCapability]


class PublisherAuthorityProjection(StrictModel):
    value: PackAuthority
    label: str = Field(min_length=1, max_length=100)
    supporting_copy: str = Field(min_length=1, max_length=500)


class SellerVersionLinks(StrictModel):
    current: str = Field(pattern=r"^/", max_length=500)
    previous: str | None = Field(default=None, pattern=r"^/", max_length=500)


class SellerActionDescriptor(StrictModel):
    id: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")
    label: str = Field(min_length=1, max_length=100)
    method: Literal["GET", "POST", "PATCH"]
    href: str = Field(pattern=r"^/", max_length=500)
    requires_confirmation: bool


class SellerEvidenceView(StrictModel):
    product: SellerEvidenceProduct
    actor: SellerActor
    publisher_authority: PublisherAuthorityProjection
    pack_health: SellerPackHealth
    validation: SellerValidation
    review: SellerReviewSummary | None = None
    reusable_answers: SellerReusableAnswers
    activity_metrics: SellerActivityMetrics
    available_actions: list[SellerActionDescriptor]
    version_links: SellerVersionLinks


class SellerEvidenceClaim(StrictModel):
    field: str = Field(min_length=1, max_length=120)
    value: ScalarEvidenceValue
    evidence_ids: list[Identifier]


class SellerPackDraftView(StrictModel):
    id: Identifier
    product_id: Identifier
    revision: int = Field(ge=1)
    revision_hash: HashValue
    state: SellerEvidenceState
    publisher_authority: PackAuthority
    claims: list[SellerEvidenceClaim]
    fit_rules: list[SellerEvidenceClaim]
    anti_fit_rules: list[SellerEvidenceClaim]
    validation: SellerValidation
    updated_at: datetime


class SellerPackDraftPatch(StrictModel):
    base_revision: int = Field(ge=1)
    claims: list[SellerEvidenceClaim] = Field(default_factory=list)
    fit_rules: list[SellerEvidenceClaim] = Field(default_factory=list)
    anti_fit_rules: list[SellerEvidenceClaim] = Field(default_factory=list)


class SellerEvidenceAttachCreate(StrictModel):
    source_reference: str = Field(min_length=3, max_length=500)
    source_class: str = Field(min_length=2, max_length=80)
    claim_fields: list[str] = Field(min_length=1)
    observed_at: datetime | None = None


class SellerEvidenceAttachmentView(StrictModel):
    id: Identifier
    draft_id: Identifier
    verification_state: Literal["UNVERIFIED", "PENDING", "VERIFIED", "REJECTED"]
    source_reference_hash: HashValue


class SellerReviewDecisionCreate(StrictModel):
    decision: SellerReviewDecision
    revision_hash: HashValue
    reason: str = Field(min_length=3, max_length=1000)


class SellerSubmitReviewCreate(StrictModel):
    revision_hash: HashValue


class SellerReviewDecisionView(StrictModel):
    id: Identifier
    draft_id: Identifier
    decision: SellerReviewDecision
    revision_hash: HashValue
    actor_role: ActorRole
    reason: str
    occurred_at: datetime


class SellerPublishCreate(StrictModel):
    revision_hash: HashValue


class SellerPackVersionView(StrictModel):
    id: Identifier
    product_id: Identifier
    version: int = Field(ge=1)
    content_hash: HashValue
    publisher_authority: PackAuthority
    state: SellerEvidenceState
    published_at: datetime | None = None


class SellerSuspendCreate(StrictModel):
    reason: str = Field(min_length=3, max_length=1000)
    effective_at: datetime


class SellerPackExport(StrictModel):
    format: SellerExportFormat
    pack_id: Identifier
    pack_version: int = Field(ge=1)
    publisher_authority: PackAuthority
    verification_summary: str
    generated_at: datetime
    content_hash: HashValue
    href: str


class SellerPackExportsView(StrictModel):
    exports: list[SellerPackExport]
