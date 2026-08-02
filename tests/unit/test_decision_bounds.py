from datetime import UTC, datetime, timedelta

from decision_engine.bounds import (
    BoundedPlan,
    CostBounds,
    CoverageBounds,
    CoverageCriterion,
    EvidenceAgeBounds,
    ExactRatio,
    OrderingBounds,
    PreferenceCriterionBound,
    PreferenceScoreBounds,
    RiskBounds,
    aggregate_coverage_bounds,
    aggregate_evidence_age_bounds,
    aggregate_preference_bounds,
    aggregate_risk_bounds,
    assess_rank_stability,
    authoritative_ordering_key,
    evidence_age_bounds,
)
from domain.enums import CandidateStatus, RankStability, StackRisk
from domain.money import Money


def _plan(
    plan_id: str,
    *,
    conservative_score: ExactRatio,
    optimistic_score: ExactRatio,
    low_cost: str = "80.00",
    base_cost: str = "90.00",
    high_cost: str = "100.00",
) -> BoundedPlan:
    return BoundedPlan(
        plan_id=plan_id,
        status=CandidateStatus.ELIGIBLE,
        stable_action_ids=(plan_id,),
        bounds=OrderingBounds(
            preference=PreferenceScoreBounds(conservative_score, optimistic_score),
            stack_risk=RiskBounds(StackRisk.LOW, StackRisk.LOW, StackRisk.MEDIUM),
            total_cost=CostBounds(
                Money(low_cost, "USD"),
                Money(base_cost, "USD"),
                Money(high_cost, "USD"),
            ),
            decision_material_coverage=CoverageBounds(ExactRatio(7, 8), ExactRatio(1)),
            maximum_evidence_age_ratio=EvidenceAgeBounds(ExactRatio(12, 90), ExactRatio(20, 90)),
        ),
    )


def test_preference_bounds_are_exact_and_proportional_weights_are_equivalent() -> None:
    first = aggregate_preference_bounds(
        (
            PreferenceCriterionBound("fit", 1, ExactRatio(3, 4), ExactRatio(1)),
            PreferenceCriterionBound("admin", 2, ExactRatio(1, 2), ExactRatio(1, 2)),
        )
    )
    scaled = aggregate_preference_bounds(
        (
            PreferenceCriterionBound("fit", 2, ExactRatio(3, 4), ExactRatio(1)),
            PreferenceCriterionBound("admin", 4, ExactRatio(1, 2), ExactRatio(1, 2)),
        )
    )

    assert first == scaled
    assert first.conservative == ExactRatio(175, 3)
    assert first.optimistic == ExactRatio(200, 3)
    assert first.to_dict()["conservative"]["display"] == "58.33"


def test_weighted_coverage_and_component_intervals_use_declared_aggregation() -> None:
    coverage = aggregate_coverage_bounds(
        (
            CoverageCriterion("privacy", 5, True, True),
            CoverageCriterion("crm", 3, False, True),
        )
    )
    risk = aggregate_risk_bounds(
        (
            RiskBounds(StackRisk.LOW, StackRisk.LOW, StackRisk.MEDIUM),
            RiskBounds(StackRisk.LOW, StackRisk.MEDIUM, StackRisk.HIGH),
        )
    )

    assert coverage == CoverageBounds(ExactRatio(5, 8), ExactRatio(1))
    assert risk == RiskBounds(StackRisk.LOW, StackRisk.MEDIUM, StackRisk.HIGH)


def test_evidence_age_uses_exact_observed_time_bounds_and_plan_maximum() -> None:
    evaluated_at = datetime(2026, 8, 2, 12, tzinfo=UTC)
    first = evidence_age_bounds(
        evaluated_at=evaluated_at,
        observed_at_lower=evaluated_at - timedelta(days=20),
        observed_at_upper=evaluated_at - timedelta(days=12),
        sla_seconds=90 * 24 * 60 * 60,
    )
    second = evidence_age_bounds(
        evaluated_at=evaluated_at,
        observed_at_lower=evaluated_at - timedelta(days=5),
        observed_at_upper=evaluated_at - timedelta(days=4),
        sla_seconds=90 * 24 * 60 * 60,
    )

    assert first == EvidenceAgeBounds(ExactRatio(2, 15), ExactRatio(2, 9))
    assert aggregate_evidence_age_bounds((first, second)) == first


def test_rank_stability_uses_every_authoritative_interval() -> None:
    selected = _plan(
        "selected",
        conservative_score=ExactRatio(86),
        optimistic_score=ExactRatio(92),
    )
    unstable_competitor = _plan(
        "competitor",
        conservative_score=ExactRatio(80),
        optimistic_score=ExactRatio(87),
    )
    stable_competitor = _plan(
        "stable_competitor",
        conservative_score=ExactRatio(80),
        optimistic_score=ExactRatio(85),
    )

    unstable = assess_rank_stability(selected, (unstable_competitor,))
    stable = assess_rank_stability(selected, (stable_competitor,))

    assert unstable.status is RankStability.UNSTABLE
    assert unstable.ordering_frontier_plan_ids == ("competitor",)
    assert stable.status is RankStability.STABLE


def test_missing_bound_makes_robustness_undetermined() -> None:
    selected = _plan(
        "selected",
        conservative_score=ExactRatio(86),
        optimistic_score=ExactRatio(92),
    )
    missing = BoundedPlan(
        plan_id="missing",
        status=CandidateStatus.ELIGIBLE,
        stable_action_ids=("missing",),
        bounds=None,
        bound_unavailable_reasons=("BOUND_UNAVAILABLE:TCO_HIGH",),
    )

    result = assess_rank_stability(selected, (missing,))

    assert result.status is RankStability.UNDETERMINED
    assert result.bound_unavailable_plan_ids == ("missing",)


def test_exact_values_break_a_display_rounded_tie() -> None:
    higher = _plan(
        "higher",
        conservative_score=ExactRatio(861_249, 10_000),
        optimistic_score=ExactRatio(861_249, 10_000),
    )
    lower = _plan(
        "lower",
        conservative_score=ExactRatio(861_241, 10_000),
        optimistic_score=ExactRatio(861_241, 10_000),
    )

    assert higher.bounds is not None
    assert lower.bounds is not None
    assert higher.bounds.preference.conservative.display() == "86.12"
    assert lower.bounds.preference.conservative.display() == "86.12"
    assert authoritative_ordering_key(higher) < authoritative_ordering_key(lower)
