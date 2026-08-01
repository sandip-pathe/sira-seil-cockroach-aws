"""Generic-request versus company-aware decision explanation."""

from __future__ import annotations

from collections.abc import Sequence

from domain.enums import CandidateStatus

from .models import CandidateResult, Counterfactual, SolutionPlan
from .ranking import rank_solution_plans


def build_counterfactual(
    *,
    generic_plans: Sequence[SolutionPlan],
    company_aware_plans: Sequence[SolutionPlan],
    company_candidate_results: Sequence[CandidateResult],
    decisive_private_fact_ids: Sequence[str],
    coverage_statement: str,
    uncertainties: Sequence[str] = (),
) -> Counterfactual:
    generic_ranked = rank_solution_plans(generic_plans)
    aware_ranked = rank_solution_plans(company_aware_plans)
    generic_winner = generic_ranked[0].plan_id if generic_ranked else None
    aware_winner = aware_ranked[0].plan_id if aware_ranked else None
    buyer_eliminations = tuple(
        (result.candidate_id, result.reason_code or "", result.reason)
        for result in company_candidate_results
        if result.status is CandidateStatus.SIRA_INELIGIBLE
    )
    seller_passes = tuple(
        (result.candidate_id, result.reason_code or "", result.reason)
        for result in company_candidate_results
        if result.status is CandidateStatus.SEIL_PASS
    )
    return Counterfactual(
        generic_winner_plan_id=generic_winner,
        company_aware_winner_plan_id=aware_winner,
        changed=generic_winner != aware_winner,
        decisive_private_fact_ids=tuple(decisive_private_fact_ids),
        buyer_eliminations=buyer_eliminations,
        seller_passes=seller_passes,
        coverage_statement=coverage_statement,
        uncertainties=tuple(uncertainties),
    )
