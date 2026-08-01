"""The sole authoritative lexicographic SolutionPlan ordering."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from domain.enums import CandidateStatus
from domain.errors import DomainValidationError

from .models import SolutionPlan

_ELIGIBILITY_ORDER = {
    CandidateStatus.ELIGIBLE: 0,
    CandidateStatus.ELIGIBLE_WITH_EXCEPTION: 1,
}


def ranking_key(plan: SolutionPlan) -> tuple[Any, ...]:
    """Return the PRD Section 12.6 key; lower tuples rank first."""

    if plan.status not in _ELIGIBILITY_ORDER:
        raise DomainValidationError("only eligible SolutionPlans receive a final rank")
    return (
        _ELIGIBILITY_ORDER[plan.status],
        -plan.preference_score_exact,
        plan.stack_risk.rank,
        plan.total_cost.amount,
        -plan.required_evidence_coverage,
        plan.maximum_evidence_age_ratio,
        plan.stable_action_ids,
        plan.plan_id,
    )


def rank_solution_plans(plans: Sequence[SolutionPlan]) -> tuple[SolutionPlan, ...]:
    eligible = tuple(plan for plan in plans if plan.status in _ELIGIBILITY_ORDER)
    if not eligible:
        return ()
    currencies = {plan.total_cost.currency for plan in eligible}
    horizons = {plan.horizon_days for plan in eligible}
    if len(currencies) != 1:
        raise DomainValidationError("plans require one quote currency or an approved FX snapshot")
    if len(horizons) != 1:
        raise DomainValidationError("plans require one declared comparison horizon")
    return tuple(sorted(eligible, key=ranking_key))


def select_winner(plans: Sequence[SolutionPlan]) -> SolutionPlan | None:
    ranked = rank_solution_plans(plans)
    return ranked[0] if ranked else None
