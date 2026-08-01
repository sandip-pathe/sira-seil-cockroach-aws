from decimal import Decimal

import pytest

from decision_engine import (
    CandidateResult,
    PreferenceResult,
    SolutionPlan,
    build_counterfactual,
    rank_solution_plans,
    select_winner,
)
from domain.enums import CandidateStatus, SolutionAction, StackRisk
from domain.errors import DomainValidationError
from domain.money import Money


def _plan(
    plan_id: str,
    *,
    status: CandidateStatus = CandidateStatus.ELIGIBLE,
    satisfaction: str = "1",
    risk: StackRisk = StackRisk.LOW,
    cost: str = "89",
    coverage: str = "1",
    age: str = "0.1",
    horizon: int = 30,
    positioning: str | None = None,
    stable: tuple[str, ...] = (),
) -> SolutionPlan:
    return SolutionPlan(
        plan_id=plan_id,
        action=SolutionAction.BUY,
        component_ids=(plan_id.removeprefix("sol_"),),
        status=status,
        preference_results=(PreferenceResult("fit", 4, satisfaction),),
        stack_risk=risk,
        total_cost=Money(cost, "USD"),
        horizon_days=horizon,
        required_evidence_coverage=coverage,
        maximum_evidence_age_ratio=age,
        seller_positioning=positioning,
        stable_action_ids=stable,
    )


@pytest.mark.parametrize(
    ("winner", "runner"),
    [
        (
            _plan("sol_eligible", status=CandidateStatus.ELIGIBLE, satisfaction="0"),
            _plan(
                "sol_exception",
                status=CandidateStatus.ELIGIBLE_WITH_EXCEPTION,
                satisfaction="1",
            ),
        ),
        (_plan("sol_score", satisfaction="1"), _plan("sol_lower_score", satisfaction="0.75")),
        (_plan("sol_risk", risk=StackRisk.LOW), _plan("sol_higher_risk", risk=StackRisk.MEDIUM)),
        (_plan("sol_cost", cost="80"), _plan("sol_higher_cost", cost="90")),
        (_plan("sol_evidence", coverage="1"), _plan("sol_less_evidence", coverage="0.75")),
        (_plan("sol_fresh", age="0.1"), _plan("sol_stale", age="0.2")),
        (
            _plan("sol_z", stable=("BUY", "component_a")),
            _plan("sol_a", stable=("BUY", "component_b")),
        ),
    ],
)
def test_exact_lexicographic_ordering(winner: SolutionPlan, runner: SolutionPlan) -> None:
    assert rank_solution_plans((runner, winner)) == (winner, runner)


def test_seller_positioning_has_zero_ranking_effect() -> None:
    plain = _plan("sol_a", positioning=None)
    persuasive = _plan("sol_b", positioning="The world's most persuasive claim")
    before = tuple(plan.plan_id for plan in rank_solution_plans((plain, persuasive)))
    after = tuple(
        plan.plan_id
        for plan in rank_solution_plans(
            (
                _plan("sol_a", positioning="New prose"),
                _plan("sol_b", positioning=None),
            )
        )
    )
    assert before == after == ("sol_a", "sol_b")


def test_ineligible_plans_never_receive_a_rank() -> None:
    eligible = _plan("sol_safe", satisfaction="0")
    failed = _plan(
        "sol_failed",
        status=CandidateStatus.SIRA_INELIGIBLE,
        satisfaction="1",
        cost="1",
    )
    assert rank_solution_plans((failed, eligible)) == (eligible,)
    assert select_winner((failed,)) is None


def test_ranking_rejects_incomparable_currency_and_horizon() -> None:
    usd = _plan("sol_usd")
    eur = SolutionPlan(
        plan_id="sol_eur",
        action=usd.action,
        component_ids=("eur",),
        status=usd.status,
        preference_results=usd.preference_results,
        stack_risk=usd.stack_risk,
        total_cost=Money("89", "EUR"),
        horizon_days=usd.horizon_days,
        required_evidence_coverage=usd.required_evidence_coverage,
        maximum_evidence_age_ratio=usd.maximum_evidence_age_ratio,
    )
    with pytest.raises(DomainValidationError, match="currency"):
        rank_solution_plans((usd, eur))

    longer = _plan("sol_longer", horizon=365)
    with pytest.raises(DomainValidationError, match="horizon"):
        rank_solution_plans((usd, longer))


def test_zero_component_no_action_plan_is_valid() -> None:
    plan = SolutionPlan(
        plan_id="sol_no_action",
        action=SolutionAction.NO_ACTION,
        component_ids=(),
        status=CandidateStatus.ELIGIBLE,
        preference_results=(PreferenceResult("fit", 1, 1),),
        stack_risk=StackRisk.LOW,
        total_cost=Money(0, "USD"),
        horizon_days=30,
        required_evidence_coverage=1,
        maximum_evidence_age_ratio=0,
    )
    assert select_winner((plan,)) is plan


def test_unknown_optional_evidence_is_zero_not_a_hidden_failure() -> None:
    preference = PreferenceResult("optional", 5, 0, unknown=True)
    assert preference.contribution == 0
    with pytest.raises(DomainValidationError, match="contribute zero"):
        PreferenceResult("optional", 5, Decimal("0.25"), unknown=True)


def test_counterfactual_records_buyer_and_seller_provenance_separately() -> None:
    cheapest = _plan("sol_cheap", cost="49")
    winner = _plan("sol_winner", cost="89")
    buyer_failure = CandidateResult(
        candidate_id="cheap",
        name="Cheap",
        pack_id="cheap",
        pack_version=1,
        status=CandidateStatus.SIRA_INELIGIBLE,
        reason_code="NO_TRAINING",
        reason="Buyer policy prohibits training",
        preference_results=(),
        buyer_rule_id="policy_no_training",
    )
    seller_pass = CandidateResult(
        candidate_id="honest_pass",
        name="Pass",
        pack_id="honest_pass",
        pack_version=1,
        status=CandidateStatus.SEIL_PASS,
        reason_code="WORKSPACE_UNSUPPORTED",
        reason="Seller does not support this workspace",
        preference_results=(),
        seller_rule_id="seller_workspace",
        evidence_claim_ids=("claim_workspace",),
    )
    result = build_counterfactual(
        generic_plans=(cheapest, winner),
        company_aware_plans=(winner,),
        company_candidate_results=(buyer_failure, seller_pass),
        decisive_private_fact_ids=("bf_no_training",),
        coverage_statement="Best supported action among four executable Packs",
    )
    assert result.changed
    assert result.generic_winner_plan_id == "sol_cheap"
    assert result.company_aware_winner_plan_id == "sol_winner"
    assert result.buyer_eliminations[0][0] == "cheap"
    assert result.seller_passes[0][0] == "honest_pass"
