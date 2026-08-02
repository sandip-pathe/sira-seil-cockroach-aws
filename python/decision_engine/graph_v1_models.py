"""Pure value objects for the deterministic SIRA Decision Graph v1.

These types describe frozen facts and policy.  They deliberately contain no
provider, persistence, API, or model-runtime concepts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from domain.enums import CandidateStatus, PackAuthority, SolutionAction, StackRisk, TruthValue
from domain.errors import DomainValidationError
from domain.models import require_id
from domain.money import Money

from .bounds import (
    CoverageBounds,
    EvidenceAgeBounds,
    ExactRatio,
    OrderingBounds,
    PreferenceScoreBounds,
    RiskBounds,
)

type Scalar = str | int | bool | None
type FactValue = Scalar | tuple[str, ...]

_COST_LINE_TYPES = frozenset(
    {
        "MERCHANT_SUBTOTAL",
        "SIRA_TRANSACTION_FEE",
        "TAX",
        "CONTRACT_COST",
        "MIGRATION_COST",
        "IMPLEMENTATION_COST",
    }
)


class EvidenceState(StrEnum):
    ACCEPTABLE = "ACCEPTABLE"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"
    CONFLICT = "CONFLICT"


class GateMode(StrEnum):
    REQUIRE_MATCH = "REQUIRE_MATCH"
    BLOCK_ON_MATCH = "BLOCK_ON_MATCH"


class PlanLifecycle(StrEnum):
    CANDIDATE = "CANDIDATE"
    RESOLUTION_PENDING = "RESOLUTION_PENDING"
    EXECUTABLE = "EXECUTABLE"
    BLOCKED = "BLOCKED"


class NormalizationKind(StrEnum):
    BOOLEAN_EQUALS = "BOOLEAN_EQUALS"
    SET_CONTAINS_ALL = "SET_CONTAINS_ALL"
    LOWER_IS_BETTER = "LOWER_IS_BETTER"
    OUTCOME_RATE = "OUTCOME_RATE"


class CounterfactualOutcome(StrEnum):
    WINNER_CHANGED = "WINNER_CHANGED"
    NO_SMALL_COUNTERFACTUAL_FOUND = "NO_SMALL_COUNTERFACTUAL_FOUND"


@dataclass(frozen=True, slots=True)
class FrozenVersions:
    request_version: str
    company_profile_version: str
    stackfile_version: str
    registry_version: str
    pack_set_version: str
    offer_set_version: str
    taxonomy_version: str
    normalization_version: str
    policy_version: str
    fx_version: str
    pipeline_version: str
    engine_version: str

    def __post_init__(self) -> None:
        for value in (
            self.request_version,
            self.company_profile_version,
            self.stackfile_version,
            self.registry_version,
            self.pack_set_version,
            self.offer_set_version,
            self.taxonomy_version,
            self.normalization_version,
            self.policy_version,
            self.fx_version,
            self.pipeline_version,
            self.engine_version,
        ):
            if not value:
                raise DomainValidationError("every Decision Graph input version must be frozen")


@dataclass(frozen=True, slots=True)
class FrozenFact:
    fact_id: str
    field: str
    value: FactValue
    private: bool
    version: str
    asserted_by_role: str = "unknown"
    authority_level: str = "UNKNOWN"
    authority_rank: int = 0

    def __post_init__(self) -> None:
        require_id(self.fact_id, "fact_id")
        if not self.field or not self.version or not self.asserted_by_role:
            raise DomainValidationError("a frozen fact requires field and version")
        if self.authority_rank < 0 or not self.authority_level:
            raise DomainValidationError("a frozen fact requires non-negative actor authority")

    def to_hash_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "fact_id": self.fact_id,
            "field": self.field,
            "value": self.value,
            "private": self.private,
            "version": self.version,
        }
        # Preserve the frozen v1 demo hashes until actor authority actually affects
        # an input. New compiled inputs bind the authority metadata explicitly.
        if (
            self.asserted_by_role != "unknown"
            or self.authority_level != "UNKNOWN"
            or self.authority_rank != 0
        ):
            payload.update(
                {
                    "asserted_by_role": self.asserted_by_role,
                    "authority_level": self.authority_level,
                    "authority_rank": self.authority_rank,
                }
            )
        return payload


@dataclass(frozen=True, slots=True)
class ActorConflictResolution:
    field: str
    fact_ids: tuple[str, ...]
    selected_fact_id: str
    selected_role: str
    decided_by_role: str
    strategy: str
    reason: str

    def __post_init__(self) -> None:
        if (
            not self.field
            or not self.selected_role
            or not self.decided_by_role
            or not self.reason
        ):
            raise DomainValidationError("actor conflict resolution fields are required")
        if self.strategy not in {"AUTHORITY_PRECEDENCE", "EXPLICIT_OWNER_DECISION"}:
            raise DomainValidationError("unsupported actor conflict resolution strategy")
        normalized = tuple(sorted(set(self.fact_ids)))
        if len(normalized) < 2 or self.selected_fact_id not in normalized:
            raise DomainValidationError("actor conflict resolution must select a conflicting fact")
        object.__setattr__(self, "fact_ids", normalized)
        for fact_id in normalized:
            require_id(fact_id, "conflicting_fact_id")


@dataclass(frozen=True, slots=True)
class ProductFact:
    field: str
    value: FactValue
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.field:
            raise DomainValidationError("a product fact requires a field")
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(self.evidence_ids))))
        for evidence_id in self.evidence_ids:
            require_id(evidence_id, "evidence_id")


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence_id: str
    record_id: str
    source_class: str
    verification_method: str
    verification_scope: str
    reconstructable: bool
    observed_at_lower: datetime | None
    observed_at_upper: datetime | None
    disputed: bool = False
    revoked: bool = False

    def __post_init__(self) -> None:
        require_id(self.evidence_id, "evidence_id")
        require_id(self.record_id, "record_id")
        if not self.source_class or not self.verification_method or not self.verification_scope:
            raise DomainValidationError("evidence provenance is required")
        if (self.observed_at_lower is None) != (self.observed_at_upper is None):
            raise DomainValidationError("both evidence observed-time bounds are required together")
        if (
            self.observed_at_lower is not None
            and self.observed_at_upper is not None
            and self.observed_at_lower > self.observed_at_upper
        ):
            raise DomainValidationError("evidence time bounds are reversed")


@dataclass(frozen=True, slots=True)
class RawCandidateRecord:
    record_id: str
    pack_id: str
    pack_version: int
    seller_id: str
    product_id: str
    edition: str
    region: str
    offer_id: str
    authority: PackAuthority
    available: bool
    facts: tuple[ProductFact, ...]
    seller_gate_ids: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value, name in (
            (self.record_id, "record_id"),
            (self.pack_id, "pack_id"),
            (self.seller_id, "seller_id"),
            (self.product_id, "product_id"),
            (self.offer_id, "offer_id"),
        ):
            require_id(value, name)
        if self.pack_version < 1 or not self.edition or not self.region:
            raise DomainValidationError("candidate identity and positive Pack version are required")
        object.__setattr__(self, "facts", tuple(self.facts))
        object.__setattr__(self, "seller_gate_ids", tuple(sorted(set(self.seller_gate_ids))))
        object.__setattr__(self, "aliases", tuple(sorted(set(self.aliases))))


@dataclass(frozen=True, slots=True)
class CostLineItem:
    line_item_type: str
    low: Money
    base: Money
    high: Money
    schedule_version: str | None = None

    def __post_init__(self) -> None:
        if self.line_item_type not in _COST_LINE_TYPES:
            raise DomainValidationError("unsupported Decision Ledger cost line-item type")


@dataclass(frozen=True, slots=True)
class OfferCost:
    offer_id: str
    low: Money | None
    base: Money | None
    high: Money | None
    horizon_days: int
    line_items: tuple[CostLineItem, ...] = ()
    payment_required: bool = False

    def __post_init__(self) -> None:
        require_id(self.offer_id, "offer_id")
        if isinstance(self.horizon_days, bool) or self.horizon_days < 1:
            raise DomainValidationError("an offer cost requires a positive comparison horizon")
        object.__setattr__(self, "line_items", tuple(self.line_items))
        if not self.payment_required and any(
            item.line_item_type == "SIRA_TRANSACTION_FEE" for item in self.line_items
        ):
            raise DomainValidationError("a non-payment action cannot contain a transaction fee")


@dataclass(frozen=True, slots=True)
class IdentityNormalization:
    version: str
    aliases: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not self.version:
            raise DomainValidationError("identity normalization requires a version")
        normalized = tuple(
            sorted(
                (source.casefold().strip(), target.casefold().strip())
                for source, target in self.aliases
            )
        )
        if len({source for source, _ in normalized}) != len(normalized):
            raise DomainValidationError("identity aliases must be unique")
        object.__setattr__(self, "aliases", normalized)


@dataclass(frozen=True, slots=True)
class IdentityRecord:
    canonical_id: str
    seller_id: str
    product_id: str
    edition: str
    region: str
    record_ids: tuple[str, ...]
    pack_ids: tuple[str, ...]
    offer_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IdentityMerge:
    canonical_id: str
    merged_record_id: str
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RecallResult:
    identities: tuple[IdentityRecord, ...]
    merges: tuple[IdentityMerge, ...]
    representatives: tuple[RawCandidateRecord, ...]
    raw_record_count: int


@dataclass(frozen=True, slots=True)
class EvidencePolicy:
    field: str
    allowed_source_classes: tuple[str, ...]
    allowed_verification_methods: tuple[str, ...]
    required_scope: str
    freshness_sla_seconds: int

    def __post_init__(self) -> None:
        if not self.field or not self.required_scope or self.freshness_sla_seconds < 1:
            raise DomainValidationError("an evidence policy requires scope and a positive SLA")


@dataclass(frozen=True, slots=True)
class EvidenceAssessment:
    evidence_id: str
    record_id: str
    field: str
    source_allowed: bool
    method_allowed: bool
    scope_match: bool
    reconstructable: bool
    freshness_current: bool | None
    disputed: bool
    revoked: bool
    state: EvidenceState
    reasons: tuple[str, ...]
    age_bounds: EvidenceAgeBounds | None


@dataclass(frozen=True, slots=True)
class Predicate:
    field: str
    operator: str
    value: FactValue

    def __post_init__(self) -> None:
        if not self.field or not self.operator:
            raise DomainValidationError("a gate predicate requires field and operator")


@dataclass(frozen=True, slots=True)
class GateRule:
    gate_id: str
    predicates: tuple[Predicate, ...]
    mode: GateMode
    blocked_status: CandidateStatus
    reason_code: str
    source_fact_ids: tuple[str, ...]
    applies_to_actions: tuple[SolutionAction, ...]
    evidence_claim_ids: tuple[str, ...] = ()
    permitted_resolution: str | None = None
    overridable: bool = False

    def __post_init__(self) -> None:
        require_id(self.gate_id, "gate_id")
        if not self.predicates or not self.reason_code:
            raise DomainValidationError("a gate requires predicates and a reason")
        object.__setattr__(self, "predicates", tuple(self.predicates))
        object.__setattr__(self, "source_fact_ids", tuple(sorted(set(self.source_fact_ids))))
        object.__setattr__(self, "applies_to_actions", tuple(self.applies_to_actions))
        object.__setattr__(self, "evidence_claim_ids", tuple(sorted(set(self.evidence_claim_ids))))


@dataclass(frozen=True, slots=True)
class GateReason:
    reason_code: str
    status: CandidateStatus
    detail: str


@dataclass(frozen=True, slots=True)
class GateResult:
    gate_id: str
    truth: TruthValue
    reasons: tuple[GateReason, ...]
    evaluated_predicates: tuple[str, ...]
    permitted_resolution: str | None


@dataclass(frozen=True, slots=True)
class PreferenceCriterion:
    criterion_id: str
    field: str
    weight: int
    coverage_weight: int
    normalization: NormalizationKind
    expected: FactValue
    source_fact_ids: tuple[str, ...]
    applies_to_actions: tuple[SolutionAction, ...]
    allowed_satisfactions: tuple[ExactRatio, ...]
    lower_is_better_points: tuple[tuple[int, ExactRatio], ...] = ()
    unknown_upper: ExactRatio | None = None
    permitted_evidence_resolution: str | None = None
    neutral_prior: ExactRatio | None = None

    def __post_init__(self) -> None:
        require_id(self.criterion_id, "criterion_id")
        if not self.field or not 1 <= self.weight <= 5 or not 1 <= self.coverage_weight <= 5:
            raise DomainValidationError(
                "preference and coverage weights must be integers from 1 to 5"
            )
        allowed = tuple(sorted(set(self.allowed_satisfactions), key=lambda item: item.fraction))
        if not allowed or allowed[0].fraction < 0 or allowed[-1].fraction > 1:
            raise DomainValidationError("normalization must declare a finite satisfaction domain")
        if ExactRatio(0) not in allowed:
            raise DomainValidationError("normalization must define the zero satisfaction bound")
        if self.unknown_upper is not None and self.unknown_upper not in allowed:
            raise DomainValidationError("unknown preference bound must be in the declared domain")
        if self.neutral_prior is not None and self.neutral_prior not in allowed:
            raise DomainValidationError("neutral outcome prior must be in the declared domain")
        if self.normalization is NormalizationKind.LOWER_IS_BETTER:
            if not self.lower_is_better_points:
                raise DomainValidationError("numeric normalization requires piecewise points")
            if any(value not in allowed for _, value in self.lower_is_better_points):
                raise DomainValidationError("piecewise values must be in the declared domain")
        if self.normalization is NormalizationKind.SET_CONTAINS_ALL and not isinstance(
            self.expected, tuple
        ):
            raise DomainValidationError("set normalization requires a finite expected set")
        if self.normalization is NormalizationKind.OUTCOME_RATE and self.neutral_prior is None:
            raise DomainValidationError("an outcome preference requires an explicit neutral prior")
        object.__setattr__(self, "allowed_satisfactions", allowed)
        object.__setattr__(self, "source_fact_ids", tuple(sorted(set(self.source_fact_ids))))
        object.__setattr__(self, "applies_to_actions", tuple(self.applies_to_actions))
        object.__setattr__(
            self, "lower_is_better_points", tuple(sorted(self.lower_is_better_points))
        )


@dataclass(frozen=True, slots=True)
class RiskRule:
    rule_id: str
    actions: tuple[SolutionAction, ...]
    predicate: Predicate | None
    lower: StackRisk
    base: StackRisk
    upper: StackRisk
    missing_lower: StackRisk | None = None
    missing_base: StackRisk | None = None
    missing_upper: StackRisk | None = None

    def __post_init__(self) -> None:
        require_id(self.rule_id, "rule_id")
        if not self.actions:
            raise DomainValidationError("a risk rule requires an action scope")
        RiskBounds(self.lower, self.base, self.upper)
        missing = (self.missing_lower, self.missing_base, self.missing_upper)
        if any(value is not None for value in missing):
            if any(value is None for value in missing):
                raise DomainValidationError("a risk missing-input bound requires lower/base/upper")
            if (
                self.missing_lower is not None
                and self.missing_base is not None
                and self.missing_upper is not None
            ):
                RiskBounds(self.missing_lower, self.missing_base, self.missing_upper)


@dataclass(frozen=True, slots=True)
class CurrentActionRecord:
    action_id: str
    action: SolutionAction
    instance_id: str
    facts: tuple[ProductFact, ...]
    cost: OfferCost
    available: bool = True
    permitted_resolution: str | None = None

    def __post_init__(self) -> None:
        require_id(self.action_id, "action_id")
        require_id(self.instance_id, "instance_id")
        object.__setattr__(self, "facts", tuple(self.facts))


@dataclass(frozen=True, slots=True)
class PlanComponent:
    component_id: str
    source_type: str
    action: SolutionAction


@dataclass(frozen=True, slots=True)
class ScoreComponent:
    criterion_id: str
    weight: int
    conservative_satisfaction: ExactRatio
    optimistic_satisfaction: ExactRatio
    contribution_conservative: ExactRatio
    contribution_optimistic: ExactRatio
    evidence_ids: tuple[str, ...]
    evidence_state: EvidenceState
    prior_label: str | None = None


@dataclass(frozen=True, slots=True)
class HardCoverage:
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if self.denominator < 1 or not 0 <= self.numerator <= self.denominator:
            raise DomainValidationError("hard coverage requires 0 <= numerator <= denominator")


@dataclass(frozen=True, slots=True)
class PlanDimensions:
    preference: PreferenceScoreBounds | None
    stack_risk: RiskBounds | None
    total_cost: OfferCost
    decision_material_coverage: CoverageBounds | None
    maximum_evidence_age_ratio: EvidenceAgeBounds | None
    hard_coverage: HardCoverage
    universe_coverage: ExactRatio
    unresolved_count: int
    conflicting_count: int
    triggered_risk_rule_ids: tuple[str, ...]
    risk_input_hash: str
    bound_unavailable_reasons: tuple[str, ...]

    @property
    def ordering_bounds(self) -> OrderingBounds | None:
        if (
            self.preference is None
            or self.stack_risk is None
            or self.total_cost.low is None
            or self.total_cost.base is None
            or self.total_cost.high is None
            or self.decision_material_coverage is None
            or self.maximum_evidence_age_ratio is None
            or self.bound_unavailable_reasons
        ):
            return None
        from .bounds import CostBounds  # Local import keeps the value-object module acyclic.

        return OrderingBounds(
            preference=self.preference,
            stack_risk=self.stack_risk,
            total_cost=CostBounds(
                self.total_cost.low,
                self.total_cost.base,
                self.total_cost.high,
            ),
            decision_material_coverage=self.decision_material_coverage,
            maximum_evidence_age_ratio=self.maximum_evidence_age_ratio,
        )


@dataclass(frozen=True, slots=True)
class EvaluatedPlan:
    plan_id: str
    action: SolutionAction
    components: tuple[PlanComponent, ...]
    component_hash: str
    construction_lifecycle: PlanLifecycle
    lifecycle: PlanLifecycle
    status: CandidateStatus
    primary_reason: GateReason | None
    gate_results: tuple[GateResult, ...]
    score_components: tuple[ScoreComponent, ...]
    dimensions: PlanDimensions
    stable_action_ids: tuple[str, ...]
    ordering_frontier_member: bool = False
    resolution_frontier_member: bool = False
    quote_required: bool = False
    quote_policy_reason: str = "NONE"
    permitted_resolution: str | None = None
    autonomous_execution_allowed: bool = False


@dataclass(frozen=True, slots=True)
class EvaluationCoverage:
    raw_record_count: int
    pack_candidate_count: int
    canonical_product_count: int
    duplicate_count: int
    generated_solution_plan_count: int
    evaluated_solution_plan_count: int
    excluded_count: int
    statement: str


@dataclass(frozen=True, slots=True)
class OutcomeObservation:
    subject_id: str
    criterion_id: str
    value: ExactRatio
    evidence_ids: tuple[str, ...]
    source_fact_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        require_id(self.subject_id, "outcome_subject_id")
        require_id(self.criterion_id, "outcome_criterion_id")
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(self.evidence_ids))))
        object.__setattr__(self, "source_fact_ids", tuple(sorted(set(self.source_fact_ids))))


@dataclass(frozen=True, slots=True)
class DecisionGraphInput:
    versions: FrozenVersions
    evaluated_at: datetime
    buyer_facts: tuple[FrozenFact, ...]
    candidates: tuple[RawCandidateRecord, ...]
    offers: tuple[OfferCost, ...]
    evidence: tuple[EvidenceRecord, ...]
    evidence_policies: tuple[EvidencePolicy, ...]
    gates: tuple[GateRule, ...]
    preferences: tuple[PreferenceCriterion, ...]
    risk_rules: tuple[RiskRule, ...]
    risk_rule_set_complete: bool
    current_actions: tuple[CurrentActionRecord, ...]
    identity_normalization: IdentityNormalization
    outcome_values: tuple[OutcomeObservation, ...] = ()
    removed_private_fact_ids: frozenset[str] = field(default_factory=frozenset)
    actor_conflict_resolutions: tuple[ActorConflictResolution, ...] = ()

    def __post_init__(self) -> None:
        if self.evaluated_at.tzinfo is None:
            raise DomainValidationError("evaluated_at must be timezone-aware")
        object.__setattr__(self, "buyer_facts", tuple(self.buyer_facts))
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "offers", tuple(self.offers))
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "evidence_policies", tuple(self.evidence_policies))
        object.__setattr__(self, "gates", tuple(self.gates))
        object.__setattr__(self, "preferences", tuple(self.preferences))
        object.__setattr__(self, "risk_rules", tuple(self.risk_rules))
        object.__setattr__(self, "current_actions", tuple(self.current_actions))
        object.__setattr__(self, "outcome_values", tuple(self.outcome_values))
        object.__setattr__(
            self,
            "actor_conflict_resolutions",
            tuple(self.actor_conflict_resolutions),
        )
        object.__setattr__(
            self, "removed_private_fact_ids", frozenset(self.removed_private_fact_ids)
        )
        unique_groups: tuple[tuple[str, tuple[str, ...]], ...] = (
            ("buyer fact", tuple(item.fact_id for item in self.buyer_facts)),
            ("candidate record", tuple(item.record_id for item in self.candidates)),
            ("offer", tuple(item.offer_id for item in self.offers)),
            ("evidence", tuple(item.evidence_id for item in self.evidence)),
            ("evidence policy", tuple(item.field for item in self.evidence_policies)),
            ("gate", tuple(item.gate_id for item in self.gates)),
            ("preference", tuple(item.criterion_id for item in self.preferences)),
            ("risk rule", tuple(item.rule_id for item in self.risk_rules)),
            ("current action", tuple(item.action_id for item in self.current_actions)),
        )
        for label, identifiers in unique_groups:
            if len(set(identifiers)) != len(identifiers):
                raise DomainValidationError(f"{label} identifiers must be unique")


@dataclass(frozen=True, slots=True)
class DecisionGraphEvaluation:
    evaluation_id: str
    generated_at: datetime
    versions: FrozenVersions
    evaluated_at: datetime
    frozen_input_hashes: tuple[tuple[str, str], ...]
    removed_private_fact_ids: tuple[str, ...]
    identity_records: tuple[IdentityRecord, ...]
    identity_merges: tuple[IdentityMerge, ...]
    evidence_assessments: tuple[EvidenceAssessment, ...]
    plans: tuple[EvaluatedPlan, ...]
    ranked_plan_ids: tuple[str, ...]
    selected_plan_id: str | None
    rank_stability: str
    ordering_frontier_plan_ids: tuple[str, ...]
    bound_unavailable_plan_ids: tuple[str, ...]
    coverage: EvaluationCoverage
    evaluation_payload_hash: str


@dataclass(frozen=True, slots=True)
class CounterfactualRecord:
    outcome: CounterfactualOutcome
    removed_fact_ids: tuple[str, ...]
    alternative_fact_id_sets: tuple[tuple[str, ...], ...]
    tested_limit: int
    before_evaluation_payload_hash: str
    after_evaluation_payload_hash: str | None
    generic_evaluation_payload_hash: str
    before_selected_plan_id: str | None
    after_selected_plan_id: str | None
    generic_selected_plan_id: str | None
    changed_gate_ids: tuple[str, ...]
    record_hash: str


@dataclass(frozen=True, slots=True)
class DecisionGraphDecision:
    base: DecisionGraphEvaluation
    generic: DecisionGraphEvaluation
    counterfactual: CounterfactualRecord
    decision_hash: str
