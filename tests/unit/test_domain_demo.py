from pathlib import Path

from decision_engine import evaluate_demo
from domain.enums import CandidateStatus

FIXTURES = Path(__file__).parents[2] / "fixtures" / "demo"


def test_frozen_demo_reproduces_all_four_roles_and_counterfactual() -> None:
    decision = evaluate_demo(FIXTURES)
    statuses = {result.candidate_id: result.status for result in decision.candidate_results}

    assert statuses == {
        "fixture_low_price_policy_fail": CandidateStatus.SIRA_INELIGIBLE,
        "fixture_honest_anti_fit": CandidateStatus.SEIL_PASS,
        "fixture_eligible_runner_up": CandidateStatus.ELIGIBLE,
        "fixture_selected_fit": CandidateStatus.ELIGIBLE,
    }
    assert decision.generic_winner.component_ids == ("fixture_low_price_policy_fail",)
    assert decision.selected_plan.component_ids == ("fixture_selected_fit",)
    assert decision.counterfactual.decisive_private_fact_ids == ("bf_no_customer_training",)


def test_frozen_demo_runner_up_and_winner_are_deterministic() -> None:
    first = evaluate_demo(FIXTURES)
    second = evaluate_demo(FIXTURES)
    eligible = [
        plan.component_ids[0]
        for plan in first.company_aware_plans
        if plan.status is CandidateStatus.ELIGIBLE
    ]
    ranked = [
        first.selected_plan.component_ids[0],
        next(
            candidate for candidate in eligible if candidate != first.selected_plan.component_ids[0]
        ),
    ]
    assert ranked == ["fixture_selected_fit", "fixture_eligible_runner_up"]
    assert first == second
    assert round(first.selected_plan.preference_score) == 86
