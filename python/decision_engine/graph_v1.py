"""Deterministic SIRA Decision Graph v1 pipeline.

The public entry point accepts frozen raw facts, rules, evidence, offers, and
current-stack action records.  No caller-supplied fit, score, eligibility,
rank, or decisive counterfactual is accepted.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from fractions import Fraction
from itertools import combinations
from typing import Any

from domain import content_hash
from domain.enums import (
    CandidateStatus,
    PackAuthority,
    RankStability,
    SolutionAction,
    StackRisk,
    TruthValue,
)
from domain.errors import DomainValidationError
from domain.money import Money

from .bounds import (
    BoundedPlan,
    CostBounds,
    CoverageBounds,
    CoverageCriterion,
    EvidenceAgeBounds,
    ExactRatio,
    PreferenceCriterionBound,
    RiskBounds,
    aggregate_coverage_bounds,
    aggregate_evidence_age_bounds,
    aggregate_preference_bounds,
    aggregate_risk_bounds,
    assess_rank_stability,
    authoritative_ordering_key,
    conservative_envelope_key,
    optimistic_envelope_key,
)
from .graph_v1_models import (
    CounterfactualOutcome,
    CounterfactualRecord,
    CurrentActionRecord,
    DecisionGraphDecision,
    DecisionGraphEvaluation,
    DecisionGraphInput,
    EvaluatedPlan,
    EvaluationCoverage,
    EvidenceAssessment,
    EvidenceState,
    FactValue,
    FrozenFact,
    GateMode,
    GateReason,
    GateResult,
    GateRule,
    HardCoverage,
    NormalizationKind,
    OfferCost,
    OutcomeObservation,
    PlanComponent,
    PlanDimensions,
    PlanLifecycle,
    Predicate,
    PreferenceCriterion,
    ProductFact,
    RecallResult,
    ScoreComponent,
)
from .graph_v1_recall import assess_evidence, recall_and_deduplicate

_STATUS_PRECEDENCE = (
    CandidateStatus.UNAVAILABLE,
    CandidateStatus.CONFLICTING_EVIDENCE,
    CandidateStatus.STALE_EVIDENCE,
    CandidateStatus.INSUFFICIENT_EVIDENCE,
    CandidateStatus.SIRA_INELIGIBLE,
    CandidateStatus.SEIL_PASS,
    CandidateStatus.AUTHORITY_REQUIRED,
    CandidateStatus.ADVISORY_ONLY,
    CandidateStatus.CONDITIONAL,
    CandidateStatus.ELIGIBLE_WITH_EXCEPTION,
    CandidateStatus.ELIGIBLE,
)
_STATUS_RANK = {status: rank for rank, status in enumerate(_STATUS_PRECEDENCE)}
_QUOTE_ACTIONS = {
    SolutionAction.BUY,
    SolutionAction.RENEW,
    SolutionAction.RESIZE,
    SolutionAction.REPLACE,
    SolutionAction.CONSOLIDATE,
}
_AUTONOMOUS_ACTIONS = {SolutionAction.REUSE_EXISTING, SolutionAction.NO_ACTION}


@dataclass(frozen=True, slots=True)
class _PlanMaterial:
    source_id: str
    action: SolutionAction
    component_id: str
    facts: tuple[ProductFact, ...]
    cost: OfferCost
    available: bool
    authority: PackAuthority | None
    seller_gate_ids: tuple[str, ...]
    permitted_resolution: str | None
    outcome_subject_id: str


@dataclass(frozen=True, slots=True)
class _FieldState:
    values: tuple[FactValue, ...]
    state: EvidenceState
    evidence_ids: tuple[str, ...]
    age_bounds: tuple[EvidenceAgeBounds, ...]
    bound_reasons: tuple[str, ...]


def _active_buyer_facts(decision_input: DecisionGraphInput) -> tuple[FrozenFact, ...]:
    return tuple(
        fact
        for fact in decision_input.buyer_facts
        if fact.fact_id not in decision_input.removed_private_fact_ids
    )


def _buyer_value_map(decision_input: DecisionGraphInput) -> dict[str, FactValue]:
    return {fact.field: fact.value for fact in _active_buyer_facts(decision_input)}


def _active_source_ids(decision_input: DecisionGraphInput) -> frozenset[str]:
    return frozenset(fact.fact_id for fact in _active_buyer_facts(decision_input))


def _exact_product(left: ExactRatio, right: int | ExactRatio) -> ExactRatio:
    right_fraction = Fraction(right) if isinstance(right, int) else right.fraction
    value = left.fraction * right_fraction
    return ExactRatio(value.numerator, value.denominator)


def _strict_equal(left: FactValue, right: FactValue) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left is right
    return left == right


def _predicate_matches(value: FactValue, predicate: Predicate) -> bool:
    expected = predicate.value
    if predicate.operator == "eq":
        return _strict_equal(value, expected)
    if predicate.operator == "neq":
        return not _strict_equal(value, expected)
    if predicate.operator == "in":
        return isinstance(expected, tuple) and any(
            _strict_equal(value, item) for item in expected
        )
    if predicate.operator == "contains_all":
        return (
            isinstance(value, tuple)
            and isinstance(expected, tuple)
            and all(any(_strict_equal(item, actual) for actual in value) for item in expected)
        )
    if predicate.operator in {"lte", "lt", "gte", "gt"}:
        if isinstance(value, bool) or isinstance(expected, bool):
            return False
        if not isinstance(value, (int, str)) or not isinstance(expected, (int, str)):
            return False
        left = Fraction(str(value))
        right = Fraction(str(expected))
        return {
            "lte": left <= right,
            "lt": left < right,
            "gte": left >= right,
            "gt": left > right,
        }[predicate.operator]
    if predicate.operator == "exists":
        return value is not None
    raise ValueError(f"unsupported deterministic predicate operator: {predicate.operator}")


def _assessment_index(
    assessments: Sequence[EvidenceAssessment],
) -> dict[tuple[str, str], EvidenceAssessment]:
    return {(item.evidence_id, item.field): item for item in assessments}


def _field_state(
    facts: Sequence[ProductFact],
    field: str,
    assessment_index: Mapping[tuple[str, str], EvidenceAssessment],
) -> _FieldState:
    matching = tuple(fact for fact in facts if fact.field == field)
    if not matching:
        return _FieldState((), EvidenceState.UNKNOWN, (), (), ())
    evidence_ids = tuple(sorted({item for fact in matching for item in fact.evidence_ids}))
    assessments = tuple(
        assessment_index[(evidence_id, field)]
        for evidence_id in evidence_ids
        if (evidence_id, field) in assessment_index
    )
    states = {item.state for item in assessments}
    values_by_hash = {content_hash(fact.value): fact.value for fact in matching}
    values = tuple(values_by_hash[key] for key in sorted(values_by_hash))
    bound_reasons = tuple(
        sorted(
            {
                reason
                for item in assessments
                for reason in item.reasons
                if reason.startswith("BOUND_UNAVAILABLE:")
            }
        )
    )
    if EvidenceState.CONFLICT in states or len(values) > 1:
        state = EvidenceState.CONFLICT
    elif EvidenceState.ACCEPTABLE in states:
        state = EvidenceState.ACCEPTABLE
    elif EvidenceState.STALE in states:
        state = EvidenceState.STALE
    else:
        state = EvidenceState.UNKNOWN
    return _FieldState(
        values=values,
        state=state,
        evidence_ids=evidence_ids,
        age_bounds=tuple(item.age_bounds for item in assessments if item.age_bounds is not None),
        bound_reasons=bound_reasons,
    )


def _gate_applies(
    gate: GateRule,
    material: _PlanMaterial,
    active_source_ids: frozenset[str],
) -> bool:
    if gate.source_fact_ids and not set(gate.source_fact_ids) <= active_source_ids:
        return False
    if gate.applies_to_actions and material.action not in gate.applies_to_actions:
        return False
    if gate.blocked_status is CandidateStatus.SEIL_PASS:
        return gate.gate_id in material.seller_gate_ids
    return True


def _availability_gate(material: _PlanMaterial) -> GateResult:
    reasons: tuple[GateReason, ...] = ()
    if not material.available:
        reasons = (GateReason("UNAVAILABLE", CandidateStatus.UNAVAILABLE, "Action is unavailable"),)
    return GateResult(
        gate_id=f"availability_{material.source_id}",
        truth=TruthValue.TRUE if material.available else TruthValue.FALSE,
        reasons=reasons,
        evaluated_predicates=("availability",),
        permitted_resolution=material.permitted_resolution,
    )


def _authority_gate(material: _PlanMaterial) -> GateResult | None:
    if material.authority is None or material.authority is PackAuthority.SELLER_SEALED:
        return None
    return GateResult(
        gate_id=f"authority_{material.source_id}",
        truth=TruthValue.FALSE,
        reasons=(
            GateReason(
                "SELLER_AUTHORITY_REQUIRED",
                CandidateStatus.ADVISORY_ONLY,
                "The package is research-only until a seller seals it",
            ),
        ),
        evaluated_predicates=("publisher_authority",),
        permitted_resolution="NEW_PACK_VERSION",
    )


def _evaluate_gate(
    gate: GateRule,
    material: _PlanMaterial,
    *,
    buyer_values: Mapping[str, FactValue],
    assessment_index: Mapping[tuple[str, str], EvidenceAssessment],
) -> GateResult:
    states: list[TruthValue] = []
    reasons: list[GateReason] = []
    evaluated: list[str] = []
    if gate.blocked_status is CandidateStatus.SEIL_PASS and gate.evidence_claim_ids:
        referenced_assessments = tuple(
            assessment
            for (evidence_id, _), assessment in assessment_index.items()
            if evidence_id in gate.evidence_claim_ids
        )
        evidence_states = {item.state for item in referenced_assessments}
        if not referenced_assessments or EvidenceState.UNKNOWN in evidence_states:
            states.append(TruthValue.UNKNOWN)
            reasons.append(
                GateReason(
                    "INSUFFICIENT_SELLER_RULE_EVIDENCE",
                    CandidateStatus.INSUFFICIENT_EVIDENCE,
                    "The published seller rule lacks reconstructable current evidence",
                )
            )
        if EvidenceState.STALE in evidence_states:
            states.append(TruthValue.UNKNOWN)
            reasons.append(
                GateReason(
                    "STALE_SELLER_RULE_EVIDENCE",
                    CandidateStatus.STALE_EVIDENCE,
                    "The published seller rule evidence is stale",
                )
            )
        if EvidenceState.CONFLICT in evidence_states:
            states.append(TruthValue.CONFLICT)
            reasons.append(
                GateReason(
                    "CONFLICTING_SELLER_RULE_EVIDENCE",
                    CandidateStatus.CONFLICTING_EVIDENCE,
                    "The published seller rule evidence is disputed or revoked",
                )
            )
    for predicate in gate.predicates:
        evaluated.append(predicate.field)
        if gate.blocked_status is CandidateStatus.SEIL_PASS:
            if predicate.field not in buyer_values:
                states.append(TruthValue.UNKNOWN)
                reasons.append(
                    GateReason(
                        "SELLER_CONDITION_UNRESOLVED",
                        CandidateStatus.CONDITIONAL,
                        f"Missing sanitized condition field {predicate.field}",
                    )
                )
                continue
            states.append(
                TruthValue.TRUE
                if _predicate_matches(buyer_values[predicate.field], predicate)
                else TruthValue.FALSE
            )
            continue

        field_state = _field_state(material.facts, predicate.field, assessment_index)
        if field_state.state is EvidenceState.CONFLICT:
            states.append(TruthValue.CONFLICT)
            reasons.append(
                GateReason(
                    "CONFLICTING_EVIDENCE",
                    CandidateStatus.CONFLICTING_EVIDENCE,
                    f"Conflicting values support {predicate.field}",
                )
            )
        elif field_state.state is EvidenceState.STALE:
            states.append(TruthValue.UNKNOWN)
            reasons.append(
                GateReason(
                    "STALE_EVIDENCE",
                    CandidateStatus.STALE_EVIDENCE,
                    f"Evidence for {predicate.field} is stale",
                )
            )
        elif field_state.state is EvidenceState.UNKNOWN or not field_state.values:
            states.append(TruthValue.UNKNOWN)
            reasons.append(
                GateReason(
                    "INSUFFICIENT_EVIDENCE",
                    CandidateStatus.INSUFFICIENT_EVIDENCE,
                    f"Current acceptable evidence for {predicate.field} is missing",
                )
            )
        else:
            states.append(
                TruthValue.TRUE
                if all(_predicate_matches(value, predicate) for value in field_state.values)
                else TruthValue.FALSE
            )

    if TruthValue.CONFLICT in states:
        truth = TruthValue.CONFLICT
    elif gate.mode is GateMode.REQUIRE_MATCH:
        if TruthValue.FALSE in states:
            truth = TruthValue.FALSE
            reasons.append(
                GateReason(gate.reason_code, gate.blocked_status, "Required predicate failed")
            )
        elif TruthValue.UNKNOWN in states:
            truth = TruthValue.UNKNOWN
        else:
            truth = TruthValue.TRUE
    elif TruthValue.FALSE in states:
        truth = TruthValue.TRUE
    elif TruthValue.UNKNOWN in states:
        truth = TruthValue.UNKNOWN
    else:
        truth = TruthValue.FALSE
        reasons.append(
            GateReason(gate.reason_code, gate.blocked_status, "Blocking predicate matched")
        )

    return GateResult(
        gate_id=gate.gate_id,
        truth=truth,
        reasons=tuple(
            sorted(
                set(reasons),
                key=lambda item: (_STATUS_RANK[item.status], item.reason_code, item.detail),
            )
        ),
        evaluated_predicates=tuple(evaluated),
        permitted_resolution=gate.permitted_resolution,
    )


def evaluate_gates(
    decision_input: DecisionGraphInput,
    material: _PlanMaterial,
    assessments: Sequence[EvidenceAssessment],
) -> tuple[GateResult, ...]:
    buyer_values = _buyer_value_map(decision_input)
    active_sources = _active_source_ids(decision_input)
    assessment_index = _assessment_index(assessments)
    results: list[GateResult] = [_availability_gate(material)]
    authority = _authority_gate(material)
    if authority is not None:
        results.append(authority)
    for gate in sorted(decision_input.gates, key=lambda item: item.gate_id):
        if _gate_applies(gate, material, active_sources):
            results.append(
                _evaluate_gate(
                    gate,
                    material,
                    buyer_values=buyer_values,
                    assessment_index=assessment_index,
                )
            )
    return tuple(results)


def _primary_status(gates: Sequence[GateResult]) -> tuple[CandidateStatus, GateReason | None]:
    reasons = tuple(reason for gate in gates for reason in gate.reasons)
    if not reasons:
        return CandidateStatus.ELIGIBLE, None
    primary = min(reasons, key=lambda item: (_STATUS_RANK[item.status], item.reason_code))
    return primary.status, primary


def _normalization_value(
    criterion: PreferenceCriterion,
    value: FactValue,
) -> ExactRatio:
    if criterion.normalization is NormalizationKind.BOOLEAN_EQUALS:
        return ExactRatio(1 if _strict_equal(value, criterion.expected) else 0)
    if criterion.normalization is NormalizationKind.SET_CONTAINS_ALL:
        matched = (
            isinstance(value, tuple)
            and isinstance(criterion.expected, tuple)
            and set(criterion.expected) <= set(value)
        )
        return ExactRatio(1 if matched else 0)
    if criterion.normalization is NormalizationKind.LOWER_IS_BETTER:
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            return ExactRatio(0)
        numeric = Fraction(str(value))
        for maximum, satisfaction in criterion.lower_is_better_points:
            if numeric <= maximum:
                return satisfaction
        return ExactRatio(0)
    raise ValueError("OUTCOME_RATE is resolved from frozen outcome observations")


def _outcome_value(
    decision_input: DecisionGraphInput,
    subject_id: str,
    criterion_id: str,
) -> OutcomeObservation | None:
    active_sources = _active_source_ids(decision_input)
    values = {
        (item.subject_id, item.criterion_id): item
        for item in decision_input.outcome_values
        if not item.source_fact_ids or set(item.source_fact_ids) <= active_sources
    }
    return values.get((subject_id, criterion_id))


def _score_components(
    decision_input: DecisionGraphInput,
    material: _PlanMaterial,
    assessments: Sequence[EvidenceAssessment],
) -> tuple[tuple[ScoreComponent, ...], tuple[str, ...]]:
    active_source_ids = _active_source_ids(decision_input)
    index = _assessment_index(assessments)
    components: list[ScoreComponent] = []
    bound_reasons: set[str] = set()
    for criterion in sorted(decision_input.preferences, key=lambda item: item.criterion_id):
        if criterion.applies_to_actions and material.action not in criterion.applies_to_actions:
            continue
        if criterion.source_fact_ids and not set(criterion.source_fact_ids) <= active_source_ids:
            continue
        field_state = _field_state(material.facts, criterion.field, index)
        prior_label = None
        score_evidence_ids = field_state.evidence_ids
        if criterion.normalization is NormalizationKind.OUTCOME_RATE:
            observed = _outcome_value(
                decision_input, material.outcome_subject_id, criterion.criterion_id
            )
            if observed is None:
                if criterion.neutral_prior is None:
                    bound_reasons.add(f"BOUND_UNAVAILABLE:{criterion.criterion_id}:NEUTRAL_PRIOR")
                    conservative = ExactRatio(0)
                    optimistic = ExactRatio(0)
                else:
                    conservative = criterion.neutral_prior
                    optimistic = criterion.neutral_prior
                    prior_label = "category prior—not observed outcome"
                evidence_state = EvidenceState.UNKNOWN
            else:
                score_evidence_ids = observed.evidence_ids
                observation_assessments = tuple(
                    index[(evidence_id, criterion.field)]
                    for evidence_id in observed.evidence_ids
                    if (evidence_id, criterion.field) in index
                )
                observation_states = {item.state for item in observation_assessments}
                if EvidenceState.CONFLICT in observation_states:
                    evidence_state = EvidenceState.CONFLICT
                elif EvidenceState.ACCEPTABLE in observation_states:
                    evidence_state = EvidenceState.ACCEPTABLE
                elif EvidenceState.STALE in observation_states:
                    evidence_state = EvidenceState.STALE
                else:
                    evidence_state = EvidenceState.UNKNOWN
                if evidence_state is EvidenceState.ACCEPTABLE:
                    conservative = observed.value
                    optimistic = observed.value
                else:
                    conservative = ExactRatio(0)
                    if criterion.unknown_upper is None:
                        optimistic = ExactRatio(0)
                        bound_reasons.add(
                            f"BOUND_UNAVAILABLE:{criterion.criterion_id}:UNKNOWN_BOUND"
                        )
                    else:
                        optimistic = criterion.unknown_upper
                bound_reasons.update(
                    reason
                    for item in observation_assessments
                    for reason in item.reasons
                    if reason.startswith("BOUND_UNAVAILABLE:")
                )
        elif field_state.state is EvidenceState.ACCEPTABLE and field_state.values:
            values = tuple(_normalization_value(criterion, value) for value in field_state.values)
            conservative = min(values, key=lambda item: item.fraction)
            optimistic = max(values, key=lambda item: item.fraction)
            evidence_state = field_state.state
        else:
            conservative = ExactRatio(0)
            evidence_state = field_state.state
            if criterion.unknown_upper is None:
                optimistic = ExactRatio(0)
                bound_reasons.add(f"BOUND_UNAVAILABLE:{criterion.criterion_id}:UNKNOWN_BOUND")
            else:
                optimistic = criterion.unknown_upper
        bound_reasons.update(field_state.bound_reasons)
        components.append(
            ScoreComponent(
                criterion_id=criterion.criterion_id,
                weight=criterion.weight,
                conservative_satisfaction=conservative,
                optimistic_satisfaction=optimistic,
                contribution_conservative=_exact_product(conservative, criterion.weight),
                contribution_optimistic=_exact_product(optimistic, criterion.weight),
                evidence_ids=score_evidence_ids,
                evidence_state=evidence_state,
                prior_label=prior_label,
            )
        )
    return tuple(components), tuple(sorted(bound_reasons))


def _risk_bounds(
    decision_input: DecisionGraphInput,
    material: _PlanMaterial,
    assessments: Sequence[EvidenceAssessment],
) -> tuple[RiskBounds | None, tuple[str, ...], tuple[str, ...]]:
    component_bounds: list[RiskBounds] = []
    triggered_ids: list[str] = []
    reasons: list[str] = []
    assessment_index = _assessment_index(assessments)
    for rule in sorted(decision_input.risk_rules, key=lambda item: item.rule_id):
        if material.action not in rule.actions:
            continue
        if rule.predicate is None:
            matched = True
        else:
            field_state = _field_state(material.facts, rule.predicate.field, assessment_index)
            values = (
                field_state.values if field_state.state is EvidenceState.ACCEPTABLE else ()
            )
            if not values:
                missing = (rule.missing_lower, rule.missing_base, rule.missing_upper)
                if any(item is None for item in missing):
                    reasons.append(f"BOUND_UNAVAILABLE:RISK:{rule.rule_id}")
                    continue
                if (
                    rule.missing_lower is not None
                    and rule.missing_base is not None
                    and rule.missing_upper is not None
                ):
                    component_bounds.append(
                        RiskBounds(rule.missing_lower, rule.missing_base, rule.missing_upper)
                    )
                suffix = (
                    "MISSING_INPUT"
                    if field_state.state is EvidenceState.UNKNOWN and not field_state.values
                    else f"{field_state.state.value}_EVIDENCE"
                )
                triggered_ids.append(f"{rule.rule_id}:{suffix}")
                continue
            matched = all(_predicate_matches(value, rule.predicate) for value in values)
        if matched:
            component_bounds.append(RiskBounds(rule.lower, rule.base, rule.upper))
            triggered_ids.append(rule.rule_id)
    if reasons:
        return None, tuple(sorted(reasons)), tuple(sorted(triggered_ids))
    if not component_bounds:
        if not decision_input.risk_rule_set_complete:
            return None, ("BOUND_UNAVAILABLE:RISK_RULE_COVERAGE",), ()
        component_bounds.append(RiskBounds(StackRisk.LOW, StackRisk.LOW, StackRisk.LOW))
        triggered_ids.append("COMPLETE_RULE_SET_DEFAULT_LOW")
    return aggregate_risk_bounds(tuple(component_bounds)), (), tuple(sorted(triggered_ids))


def _coverage_and_age(
    decision_input: DecisionGraphInput,
    material: _PlanMaterial,
    gates: Sequence[GateResult],
    score_components: Sequence[ScoreComponent],
    assessments: Sequence[EvidenceAssessment],
) -> tuple[CoverageBounds, EvidenceAgeBounds, HardCoverage, tuple[str, ...]]:
    active_source_ids = _active_source_ids(decision_input)
    score_by_id = {item.criterion_id: item for item in score_components}
    coverage_criteria: list[CoverageCriterion] = []
    for criterion in sorted(decision_input.preferences, key=lambda item: item.criterion_id):
        if criterion.applies_to_actions and material.action not in criterion.applies_to_actions:
            continue
        if criterion.source_fact_ids and not set(criterion.source_fact_ids) <= active_source_ids:
            continue
        score = score_by_id[criterion.criterion_id]
        conservative = (
            score.evidence_state is EvidenceState.ACCEPTABLE and score.prior_label is None
        )
        optimistic = conservative or (
            criterion.permitted_evidence_resolution is not None
            and score.evidence_state in {EvidenceState.UNKNOWN, EvidenceState.STALE}
        )
        coverage_criteria.append(
            CoverageCriterion(
                criterion.criterion_id,
                criterion.coverage_weight,
                conservative,
                optimistic,
            )
        )

    seller_gate_ids = {
        gate.gate_id
        for gate in decision_input.gates
        if gate.blocked_status is CandidateStatus.SEIL_PASS
    }
    active_hard_gates = tuple(
        gate
        for gate in gates
        if not gate.gate_id.startswith(("availability_", "authority_"))
        and gate.gate_id not in seller_gate_ids
    )
    if active_hard_gates:
        hard_coverage = HardCoverage(
            sum(gate.truth is TruthValue.TRUE for gate in active_hard_gates),
            len(active_hard_gates),
        )
    else:
        hard_coverage = HardCoverage(1, 1)

    material_evidence_ids = {
        evidence_id for fact in material.facts for evidence_id in fact.evidence_ids
    } | {evidence_id for score in score_components for evidence_id in score.evidence_ids}
    material_assessments = tuple(
        item for item in assessments if item.evidence_id in material_evidence_ids
    )
    ages = tuple(item.age_bounds for item in material_assessments if item.age_bounds is not None)
    age_bounds = aggregate_evidence_age_bounds(ages)
    reasons = tuple(
        sorted(
            {
                reason
                for item in material_assessments
                for reason in item.reasons
                if reason.startswith("BOUND_UNAVAILABLE:")
            }
        )
    )
    return aggregate_coverage_bounds(tuple(coverage_criteria)), age_bounds, hard_coverage, reasons


def _valid_cost(cost: OfferCost) -> tuple[bool, tuple[str, ...]]:
    if cost.low is None or cost.base is None or cost.high is None:
        return False, (f"BOUND_UNAVAILABLE:TCO:{cost.offer_id}",)
    CostBounds(cost.low, cost.base, cost.high)
    if cost.line_items:
        for field in ("low", "base", "high"):
            total = getattr(cost, field)
            assert total is not None
            line_total = sum(
                (getattr(item, field).amount for item in cost.line_items),
                start=Money(0, total.currency).amount,
            )
            if line_total != total.amount:
                return False, (f"BOUND_UNAVAILABLE:TCO_LINE_ITEMS:{cost.offer_id}:{field}",)
    fee_items = tuple(
        item for item in cost.line_items if item.line_item_type == "SIRA_TRANSACTION_FEE"
    )
    if cost.payment_required and len(fee_items) != 1:
        return False, (f"BOUND_UNAVAILABLE:TRANSACTION_FEE:{cost.offer_id}",)
    if not cost.payment_required and fee_items:
        return False, (f"BOUND_UNAVAILABLE:UNEXPECTED_TRANSACTION_FEE:{cost.offer_id}",)
    return True, ()


def _material_dimensions(
    decision_input: DecisionGraphInput,
    material: _PlanMaterial,
    gates: Sequence[GateResult],
    assessments: Sequence[EvidenceAssessment],
    universe_count: int,
) -> tuple[tuple[ScoreComponent, ...], PlanDimensions, tuple[str, ...]]:
    scores, score_reasons = _score_components(decision_input, material, assessments)
    preference = None
    if scores:
        preference = aggregate_preference_bounds(
            tuple(
                PreferenceCriterionBound(
                    item.criterion_id,
                    item.weight,
                    item.conservative_satisfaction,
                    item.optimistic_satisfaction,
                )
                for item in scores
            )
        )
    else:
        score_reasons = (*score_reasons, "BOUND_UNAVAILABLE:NO_APPLICABLE_PREFERENCE")
    risk, risk_reasons, risk_rule_ids = _risk_bounds(decision_input, material, assessments)
    coverage, age, hard_coverage, evidence_reasons = _coverage_and_age(
        decision_input, material, gates, scores, assessments
    )
    _, cost_reasons = _valid_cost(material.cost)
    reasons = tuple(sorted(set((*score_reasons, *risk_reasons, *evidence_reasons, *cost_reasons))))
    risk_input_hash = content_hash(
        {
            "action": material.action.value,
            "inputs": tuple(
                sorted(
                    ((fact.field, fact.value) for fact in material.facts),
                    key=lambda item: (item[0], content_hash(item[1])),
                )
            ),
        }
    )
    dimensions = PlanDimensions(
        preference=preference,
        stack_risk=risk,
        total_cost=material.cost,
        decision_material_coverage=coverage,
        maximum_evidence_age_ratio=age,
        hard_coverage=hard_coverage,
        universe_coverage=ExactRatio(universe_count, universe_count)
        if universe_count
        else ExactRatio(0),
        unresolved_count=sum(gate.truth is TruthValue.UNKNOWN for gate in gates),
        conflicting_count=sum(gate.truth is TruthValue.CONFLICT for gate in gates),
        triggered_risk_rule_ids=risk_rule_ids,
        risk_input_hash=risk_input_hash,
        bound_unavailable_reasons=reasons,
    )
    return scores, dimensions, risk_rule_ids


def _plan_id(action: SolutionAction, component_id: str) -> str:
    digest = content_hash({"action": action.value, "component_id": component_id}).split(":", 1)[1]
    return f"plan_{digest[:20]}"


def _pack_materials(
    decision_input: DecisionGraphInput, recall: RecallResult
) -> tuple[_PlanMaterial, ...]:
    aliases = dict(decision_input.identity_normalization.aliases)

    def canonical_offer(value: str) -> str:
        current = value.casefold().strip()
        visited: set[str] = set()
        while current in aliases and current not in visited:
            visited.add(current)
            current = aliases[current]
        return current

    offers = {canonical_offer(item.offer_id): item for item in decision_input.offers}
    return tuple(
        _PlanMaterial(
            source_id=item.record_id,
            action=SolutionAction.REPLACE,
            component_id=item.product_id,
            facts=item.facts,
            cost=offers.get(
                canonical_offer(item.offer_id),
                OfferCost(item.offer_id, None, None, None, 1),
            ),
            available=item.available,
            authority=item.authority,
            seller_gate_ids=item.seller_gate_ids,
            permitted_resolution=None,
            outcome_subject_id=item.product_id,
        )
        for item in recall.representatives
    )


def _current_material(item: CurrentActionRecord) -> _PlanMaterial:
    outcome_subject_id = (
        f"cancelled_{item.instance_id}"
        if item.action is SolutionAction.CANCEL
        else item.instance_id
    )
    return _PlanMaterial(
        source_id=item.action_id,
        action=item.action,
        component_id=item.instance_id,
        facts=item.facts,
        cost=item.cost,
        available=item.available,
        authority=None,
        seller_gate_ids=(),
        permitted_resolution=item.permitted_resolution,
        outcome_subject_id=outcome_subject_id,
    )


def build_solution_plans(
    decision_input: DecisionGraphInput,
    recall: RecallResult,
    assessments: Sequence[EvidenceAssessment],
) -> tuple[EvaluatedPlan, ...]:
    """Construct action-neutral plans, then derive lifecycle from gates and bounds."""

    materials = (
        *_pack_materials(decision_input, recall),
        *map(_current_material, decision_input.current_actions),
    )
    universe_count = len(materials)
    results: list[EvaluatedPlan] = []
    for material in sorted(
        materials, key=lambda item: (item.action.value, item.component_id, item.source_id)
    ):
        gates = evaluate_gates(decision_input, material, assessments)
        status, primary_reason = _primary_status(gates)
        scores, dimensions, _ = _material_dimensions(
            decision_input, material, gates, assessments, universe_count
        )
        stable_ids = (material.action.value.lower(), material.component_id)
        component_payload = {
            "action": material.action.value,
            "ordered_component_ids": (material.component_id,),
        }
        component_hash = content_hash(component_payload)
        permitted_resolutions = tuple(
            sorted(
                {
                    resolution
                    for gate in gates
                    if gate.reasons and (resolution := gate.permitted_resolution) is not None
                }
            )
        )
        permitted_resolution = (
            permitted_resolutions[0]
            if len(permitted_resolutions) == 1
            else "+".join(permitted_resolutions) or material.permitted_resolution
        )
        if status in {CandidateStatus.ELIGIBLE, CandidateStatus.ELIGIBLE_WITH_EXCEPTION}:
            lifecycle = (
                PlanLifecycle.EXECUTABLE
                if dimensions.ordering_bounds is not None
                else PlanLifecycle.BLOCKED
            )
        elif (
            status
            in {
                CandidateStatus.CONDITIONAL,
                CandidateStatus.STALE_EVIDENCE,
                CandidateStatus.INSUFFICIENT_EVIDENCE,
                CandidateStatus.ADVISORY_ONLY,
            }
            and permitted_resolution
        ):
            lifecycle = PlanLifecycle.RESOLUTION_PENDING
        else:
            lifecycle = PlanLifecycle.BLOCKED
        results.append(
            EvaluatedPlan(
                plan_id=_plan_id(material.action, material.component_id),
                action=material.action,
                components=(
                    PlanComponent(
                        material.component_id,
                        "PACK" if material.authority else "CURRENT_INSTANCE",
                        material.action,
                    ),
                ),
                component_hash=component_hash,
                construction_lifecycle=PlanLifecycle.CANDIDATE,
                lifecycle=lifecycle,
                status=status,
                primary_reason=primary_reason,
                gate_results=gates,
                score_components=scores,
                dimensions=dimensions,
                stable_action_ids=stable_ids,
                permitted_resolution=permitted_resolution,
            )
        )
    return tuple(results)


def _bounded_plan(plan: EvaluatedPlan, *, resolved: bool = False) -> BoundedPlan:
    status = CandidateStatus.ELIGIBLE if resolved else plan.status
    return BoundedPlan(
        plan_id=plan.plan_id,
        status=status,
        stable_action_ids=plan.stable_action_ids,
        bounds=plan.dimensions.ordering_bounds,
        bound_unavailable_reasons=plan.dimensions.bound_unavailable_reasons,
    )


def _rank_and_frontiers(
    plans: tuple[EvaluatedPlan, ...],
) -> tuple[tuple[EvaluatedPlan, ...], tuple[str, ...], str, tuple[str, ...], tuple[str, ...]]:
    eligible = tuple(
        plan
        for plan in plans
        if plan.status in {CandidateStatus.ELIGIBLE, CandidateStatus.ELIGIBLE_WITH_EXCEPTION}
    )
    bounded = tuple(_bounded_plan(plan) for plan in eligible)
    rankable = tuple(plan for plan in bounded if plan.bounds is not None)
    horizon_by_plan = {
        plan.plan_id: plan.dimensions.total_cost.horizon_days for plan in eligible
    }
    cost_signatures = {
        (plan.bounds.total_cost.base.currency, horizon_by_plan[plan.plan_id])
        for plan in rankable
        if plan.bounds is not None
    }
    if len(cost_signatures) > 1:
        raise DomainValidationError(
            "authoritative ranking requires one currency and comparison horizon"
        )
    ranked = tuple(sorted(rankable, key=authoritative_ordering_key))
    ranked_ids = tuple(item.plan_id for item in ranked)
    selected = ranked[0] if ranked else None
    if selected is None:
        stability = RankStability.UNDETERMINED
        ordering_frontier: tuple[str, ...] = ()
        unavailable = tuple(sorted(item.plan_id for item in bounded if item.bounds is None))
    else:
        competitors = tuple(item for item in bounded if item.plan_id != selected.plan_id)
        stability_result = assess_rank_stability(selected, competitors)
        stability = stability_result.status
        ordering_frontier = tuple(
            sorted({selected.plan_id, *stability_result.ordering_frontier_plan_ids})
        )
        unavailable = stability_result.bound_unavailable_plan_ids

    selected_worst = conservative_envelope_key(selected) if selected is not None else None
    resolution_frontier: set[str] = set()
    if selected_worst is not None:
        for plan in plans:
            if (
                plan.lifecycle is PlanLifecycle.RESOLUTION_PENDING
                and plan.permitted_resolution is not None
                and plan.dimensions.ordering_bounds is not None
            ):
                hypothetical = _bounded_plan(plan, resolved=True)
                if optimistic_envelope_key(hypothetical) < selected_worst:
                    resolution_frontier.add(plan.plan_id)

    preliminary_top_three = set(ranked_ids[:3])
    updated: list[EvaluatedPlan] = []
    for plan in plans:
        ordering_member = plan.plan_id in ordering_frontier
        resolution_member = plan.plan_id in resolution_frontier
        if selected is not None and plan.plan_id == selected.plan_id:
            quote_reason = "SELECTED_PLAN"
        elif ordering_member:
            quote_reason = "ORDERING_FRONTIER"
        elif resolution_member:
            quote_reason = "RESOLUTION_FRONTIER"
        elif plan.plan_id in preliminary_top_three:
            quote_reason = "PRELIMINARY_TOP_THREE"
        else:
            quote_reason = "NONE"
        quote_required = quote_reason != "NONE" and plan.action in _QUOTE_ACTIONS
        autonomous = (
            plan.lifecycle is PlanLifecycle.EXECUTABLE
            and stability is RankStability.STABLE
            and not plan.dimensions.total_cost.payment_required
            and plan.action in _AUTONOMOUS_ACTIONS
        )
        updated.append(
            replace(
                plan,
                ordering_frontier_member=ordering_member,
                resolution_frontier_member=resolution_member,
                quote_required=quote_required,
                quote_policy_reason=quote_reason,
                autonomous_execution_allowed=autonomous,
            )
        )
    return tuple(updated), ranked_ids, stability.value, ordering_frontier, unavailable


def _ratio_payload(value: ExactRatio) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _money_payload(value: Money | None) -> dict[str, str] | None:
    return None if value is None else value.to_dict()


def _canonical_plan(plan: EvaluatedPlan) -> dict[str, Any]:
    dimensions = plan.dimensions
    return {
        "action": plan.action.value,
        "stable_action_ids": plan.stable_action_ids,
        "component_hash": plan.component_hash,
        "lifecycle": plan.lifecycle.value,
        "status": plan.status.value,
        "primary_reason": None
        if plan.primary_reason is None
        else {
            "code": plan.primary_reason.reason_code,
            "status": plan.primary_reason.status.value,
            "detail": plan.primary_reason.detail,
        },
        "gates": tuple(
            {
                "gate_id": gate.gate_id,
                "truth": gate.truth.value,
                "reasons": tuple(
                    {
                        "code": reason.reason_code,
                        "status": reason.status.value,
                        "detail": reason.detail,
                    }
                    for reason in gate.reasons
                ),
                "predicates": gate.evaluated_predicates,
                "permitted_resolution": gate.permitted_resolution,
            }
            for gate in plan.gate_results
        ),
        "scores": tuple(
            {
                "criterion_id": item.criterion_id,
                "weight": item.weight,
                "conservative": _ratio_payload(item.conservative_satisfaction),
                "optimistic": _ratio_payload(item.optimistic_satisfaction),
                "evidence_ids": item.evidence_ids,
                "evidence_state": item.evidence_state.value,
                "prior_label": item.prior_label,
            }
            for item in plan.score_components
        ),
        "bounds": {
            "preference": None
            if dimensions.preference is None
            else {
                "conservative": _ratio_payload(dimensions.preference.conservative),
                "optimistic": _ratio_payload(dimensions.preference.optimistic),
            },
            "risk": {
                "lower": None
                if dimensions.stack_risk is None
                else dimensions.stack_risk.lower.value,
                "base": None if dimensions.stack_risk is None else dimensions.stack_risk.base.value,
                "upper": None
                if dimensions.stack_risk is None
                else dimensions.stack_risk.upper.value,
                "triggered_rule_ids": dimensions.triggered_risk_rule_ids,
                "input_hash": dimensions.risk_input_hash,
            },
            "tco": {
                "low": _money_payload(dimensions.total_cost.low),
                "base": _money_payload(dimensions.total_cost.base),
                "high": _money_payload(dimensions.total_cost.high),
                "horizon_days": dimensions.total_cost.horizon_days,
                "payment_required": dimensions.total_cost.payment_required,
                "line_items": tuple(
                    {
                        "type": item.line_item_type,
                        "low": item.low.to_dict(),
                        "base": item.base.to_dict(),
                        "high": item.high.to_dict(),
                        "schedule_version": item.schedule_version,
                    }
                    for item in dimensions.total_cost.line_items
                ),
            },
            "coverage": None
            if dimensions.decision_material_coverage is None
            else {
                "conservative": _ratio_payload(dimensions.decision_material_coverage.conservative),
                "optimistic": _ratio_payload(dimensions.decision_material_coverage.optimistic),
            },
            "age": None
            if dimensions.maximum_evidence_age_ratio is None
            else {
                "lower": _ratio_payload(dimensions.maximum_evidence_age_ratio.lower),
                "upper": _ratio_payload(dimensions.maximum_evidence_age_ratio.upper),
            },
            "hard_coverage": {
                "numerator": dimensions.hard_coverage.numerator,
                "denominator": dimensions.hard_coverage.denominator,
            },
            "bound_unavailable_reasons": dimensions.bound_unavailable_reasons,
        },
        "ordering_frontier_member": plan.ordering_frontier_member,
        "resolution_frontier_member": plan.resolution_frontier_member,
        "quote_required": plan.quote_required,
        "quote_policy_reason": plan.quote_policy_reason,
        "permitted_resolution": plan.permitted_resolution,
        "autonomous_execution_allowed": plan.autonomous_execution_allowed,
    }


def evaluation_canonical_payload(evaluation: DecisionGraphEvaluation) -> dict[str, Any]:
    """Return the canonical base-evaluation payload, excluding generated metadata."""

    selected = next(
        (
            plan.stable_action_ids
            for plan in evaluation.plans
            if plan.plan_id == evaluation.selected_plan_id
        ),
        None,
    )
    ranked = tuple(
        next(plan.stable_action_ids for plan in evaluation.plans if plan.plan_id == plan_id)
        for plan_id in evaluation.ranked_plan_ids
    )
    return {
        "versions": evaluation.versions,
        "evaluated_at": evaluation.evaluated_at,
        "frozen_input_hashes": evaluation.frozen_input_hashes,
        "removed_private_fact_ids": evaluation.removed_private_fact_ids,
        "identities": tuple(
            {
                "seller_id": item.seller_id,
                "product_id": item.product_id,
                "edition": item.edition,
                "region": item.region,
                "record_ids": item.record_ids,
                "pack_ids": item.pack_ids,
                "offer_ids": item.offer_ids,
            }
            for item in evaluation.identity_records
        ),
        "identity_merges": evaluation.identity_merges,
        "evidence_assessments": evaluation.evidence_assessments,
        "plans": tuple(_canonical_plan(plan) for plan in evaluation.plans),
        "ranked_stable_action_ids": ranked,
        "selected_stable_action_ids": selected,
        "rank_stability": evaluation.rank_stability,
        "ordering_frontier_stable_action_ids": tuple(
            next(plan.stable_action_ids for plan in evaluation.plans if plan.plan_id == plan_id)
            for plan_id in evaluation.ordering_frontier_plan_ids
        ),
        "bound_unavailable_stable_action_ids": tuple(
            next(plan.stable_action_ids for plan in evaluation.plans if plan.plan_id == plan_id)
            for plan_id in evaluation.bound_unavailable_plan_ids
        ),
        "coverage": evaluation.coverage,
    }


def _frozen_input_hashes(decision_input: DecisionGraphInput) -> tuple[tuple[str, str], ...]:
    active_facts = tuple(sorted(_active_buyer_facts(decision_input), key=lambda item: item.fact_id))
    artifacts: dict[str, object] = {
        "buyer_facts": active_facts,
        "candidate_records": tuple(
            sorted(decision_input.candidates, key=lambda item: item.record_id)
        ),
        "offers": tuple(sorted(decision_input.offers, key=lambda item: item.offer_id)),
        "evidence": tuple(sorted(decision_input.evidence, key=lambda item: item.evidence_id)),
        "evidence_policies": tuple(
            sorted(decision_input.evidence_policies, key=lambda item: item.field)
        ),
        "gates": tuple(sorted(decision_input.gates, key=lambda item: item.gate_id)),
        "preferences": tuple(
            sorted(decision_input.preferences, key=lambda item: item.criterion_id)
        ),
        "risk_rules": {
            "complete_input_coverage": decision_input.risk_rule_set_complete,
            "rules": tuple(sorted(decision_input.risk_rules, key=lambda item: item.rule_id)),
        },
        "current_actions": tuple(
            sorted(decision_input.current_actions, key=lambda item: item.action_id)
        ),
        "identity_normalization": decision_input.identity_normalization,
        "outcome_observations": tuple(
            sorted(
                decision_input.outcome_values,
                key=lambda item: (item.subject_id, item.criterion_id),
            )
        ),
    }
    return tuple((name, content_hash(value)) for name, value in sorted(artifacts.items()))


def evaluate_decision_graph_once(
    decision_input: DecisionGraphInput,
    *,
    evaluation_id: str = "generated_evaluation_id",
    generated_at: datetime | None = None,
) -> DecisionGraphEvaluation:
    recall = recall_and_deduplicate(decision_input)
    assessments = assess_evidence(decision_input, recall)
    plans = build_solution_plans(decision_input, recall, assessments)
    plans, ranked_ids, stability, ordering_frontier, unavailable = _rank_and_frontiers(plans)
    coverage = EvaluationCoverage(
        raw_record_count=recall.raw_record_count,
        pack_candidate_count=len(decision_input.candidates),
        canonical_product_count=len(recall.identities),
        duplicate_count=len(recall.merges),
        generated_solution_plan_count=len(plans),
        evaluated_solution_plan_count=len(plans),
        excluded_count=0,
        statement=(
            f"Best supported action among {len(recall.identities)} canonical products and "
            f"{len(decision_input.current_actions)} current-stack/contract actions"
        ),
    )
    provisional = DecisionGraphEvaluation(
        evaluation_id=evaluation_id,
        generated_at=generated_at or datetime.now(UTC),
        versions=decision_input.versions,
        evaluated_at=decision_input.evaluated_at,
        frozen_input_hashes=_frozen_input_hashes(decision_input),
        removed_private_fact_ids=tuple(sorted(decision_input.removed_private_fact_ids)),
        identity_records=recall.identities,
        identity_merges=recall.merges,
        evidence_assessments=assessments,
        plans=plans,
        ranked_plan_ids=ranked_ids,
        selected_plan_id=ranked_ids[0] if ranked_ids else None,
        rank_stability=stability,
        ordering_frontier_plan_ids=ordering_frontier,
        bound_unavailable_plan_ids=unavailable,
        coverage=coverage,
        evaluation_payload_hash="",
    )
    return replace(
        provisional,
        evaluation_payload_hash=content_hash(evaluation_canonical_payload(provisional)),
    )


def _gate_truth_map(evaluation: DecisionGraphEvaluation) -> dict[tuple[tuple[str, ...], str], str]:
    return {
        (plan.stable_action_ids, gate.gate_id): gate.truth.value
        for plan in evaluation.plans
        for gate in plan.gate_results
    }


def _changed_gate_ids(
    before: DecisionGraphEvaluation, after: DecisionGraphEvaluation
) -> tuple[str, ...]:
    before_map = _gate_truth_map(before)
    after_map = _gate_truth_map(after)
    keys = set(before_map) | set(after_map)
    return tuple(
        sorted(
            {
                gate_id
                for action_ids, gate_id in keys
                if before_map.get((action_ids, gate_id)) != after_map.get((action_ids, gate_id))
            }
        )
    )


def _counterfactual_payload(record: CounterfactualRecord) -> dict[str, Any]:
    return {
        "outcome": record.outcome.value,
        "removed_fact_ids": record.removed_fact_ids,
        "alternative_fact_id_sets": record.alternative_fact_id_sets,
        "tested_limit": record.tested_limit,
        "before_evaluation_payload_hash": record.before_evaluation_payload_hash,
        "after_evaluation_payload_hash": record.after_evaluation_payload_hash,
        "generic_evaluation_payload_hash": record.generic_evaluation_payload_hash,
        "before_selected_plan_id": record.before_selected_plan_id,
        "after_selected_plan_id": record.after_selected_plan_id,
        "generic_selected_plan_id": record.generic_selected_plan_id,
        "changed_gate_ids": record.changed_gate_ids,
    }


def search_private_fact_counterfactuals(
    decision_input: DecisionGraphInput,
    base: DecisionGraphEvaluation,
    generic: DecisionGraphEvaluation,
    *,
    limit: int = 3,
) -> CounterfactualRecord:
    """Rerun stable fact ablations by cardinality and fact ID up to ``limit``."""

    if not 1 <= limit <= 3:
        raise DomainValidationError("Decision Graph v1 counterfactual limit must be from 1 to 3")

    private_ids = tuple(
        sorted(
            fact.fact_id
            for fact in decision_input.buyer_facts
            if fact.private and fact.fact_id not in decision_input.removed_private_fact_ids
        )
    )
    winners: list[tuple[tuple[str, ...], DecisionGraphEvaluation]] = []
    for cardinality in range(1, min(limit, len(private_ids)) + 1):
        for removed in combinations(private_ids, cardinality):
            alternate_input = replace(
                decision_input,
                removed_private_fact_ids=(
                    decision_input.removed_private_fact_ids | frozenset(removed)
                ),
            )
            alternate = evaluate_decision_graph_once(
                alternate_input,
                evaluation_id="counterfactual_evaluation_id",
                generated_at=base.generated_at,
            )
            if alternate.selected_plan_id != base.selected_plan_id:
                winners.append((removed, alternate))
        if winners:
            break

    if winners:
        winners.sort(key=lambda item: item[0])
        chosen_ids, chosen = winners[0]
        outcome = CounterfactualOutcome.WINNER_CHANGED
        alternatives = tuple(item[0] for item in winners[1:])
        after_hash: str | None = chosen.evaluation_payload_hash
        after_selected = chosen.selected_plan_id
        changed_gates = _changed_gate_ids(base, chosen)
    else:
        chosen_ids = ()
        outcome = CounterfactualOutcome.NO_SMALL_COUNTERFACTUAL_FOUND
        alternatives = ()
        after_hash = None
        after_selected = None
        changed_gates = ()
    provisional = CounterfactualRecord(
        outcome=outcome,
        removed_fact_ids=chosen_ids,
        alternative_fact_id_sets=alternatives,
        tested_limit=limit,
        before_evaluation_payload_hash=base.evaluation_payload_hash,
        after_evaluation_payload_hash=after_hash,
        generic_evaluation_payload_hash=generic.evaluation_payload_hash,
        before_selected_plan_id=base.selected_plan_id,
        after_selected_plan_id=after_selected,
        generic_selected_plan_id=generic.selected_plan_id,
        changed_gate_ids=changed_gates,
        record_hash="",
    )
    return replace(provisional, record_hash=content_hash(_counterfactual_payload(provisional)))


def evaluate_decision_graph(
    decision_input: DecisionGraphInput,
    *,
    evaluation_id: str = "generated_evaluation_id",
    generated_at: datetime | None = None,
    counterfactual_limit: int = 3,
) -> DecisionGraphDecision:
    """Evaluate the base, generic, and smallest private-fact counterfactual reruns."""

    frozen_generated_at = generated_at or datetime.now(UTC)
    base = evaluate_decision_graph_once(
        decision_input, evaluation_id=evaluation_id, generated_at=frozen_generated_at
    )
    all_private = frozenset(fact.fact_id for fact in decision_input.buyer_facts if fact.private)
    generic_input = replace(
        decision_input,
        removed_private_fact_ids=decision_input.removed_private_fact_ids | all_private,
    )
    generic = evaluate_decision_graph_once(
        generic_input,
        evaluation_id="generic_evaluation_id",
        generated_at=frozen_generated_at,
    )
    counterfactual = search_private_fact_counterfactuals(
        decision_input,
        base,
        generic,
        limit=counterfactual_limit,
    )
    selected = next(
        (plan.stable_action_ids for plan in base.plans if plan.plan_id == base.selected_plan_id),
        None,
    )
    decision_hash = content_hash(
        {
            "base_evaluation_payload_hash": base.evaluation_payload_hash,
            "counterfactual_record_hashes": (counterfactual.record_hash,),
            "selected_outcome": selected,
        }
    )
    return DecisionGraphDecision(base, generic, counterfactual, decision_hash)


__all__ = [
    "build_solution_plans",
    "evaluate_decision_graph",
    "evaluate_decision_graph_once",
    "evaluate_gates",
    "evaluation_canonical_payload",
    "search_private_fact_counterfactuals",
]
