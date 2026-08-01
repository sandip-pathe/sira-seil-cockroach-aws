from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from decision_engine import PreferenceResult, SolutionPlan, rank_solution_plans
from domain import RuleCondition, RuleExpression, content_hash
from domain.enums import CandidateStatus, RuleOperator, SolutionAction, StackRisk, TruthValue
from domain.money import Money


@given(st.dictionaries(st.text(min_size=1), st.integers(), max_size=20))
def test_canonical_hash_is_independent_of_key_insertion_order(values: dict[str, int]) -> None:
    reversed_values = dict(reversed(tuple(values.items())))
    assert content_hash(values) == content_hash(reversed_values)


@given(st.from_regex(r"[a-z][a-z0-9_]{0,20}", fullmatch=True))
def test_unknown_taxonomy_field_never_becomes_true(field: str) -> None:
    rule = RuleExpression((RuleCondition(field, RuleOperator.EQ, True),))
    assert rule.evaluate({}).value is TruthValue.UNRESOLVED


def _property_plan(plan_id: str, satisfaction: str, cost: int) -> SolutionPlan:
    return SolutionPlan(
        plan_id=plan_id,
        action=SolutionAction.BUY,
        component_ids=(f"component_{plan_id}",),
        status=CandidateStatus.ELIGIBLE,
        preference_results=(PreferenceResult("criterion", 3, satisfaction),),
        stack_risk=StackRisk.LOW,
        total_cost=Money(cost, "USD"),
        horizon_days=30,
        required_evidence_coverage=Decimal(1),
        maximum_evidence_age_ratio=Decimal("0.1"),
    )


_PLANS = {
    "plan_a": _property_plan("plan_a", "1", 99),
    "plan_b": _property_plan("plan_b", "0.75", 49),
    "plan_c": _property_plan("plan_c", "0.5", 10),
    "plan_d": _property_plan("plan_d", "0", 1),
}


@given(st.permutations(tuple(_PLANS)))
def test_ranking_is_permutation_invariant(order: list[str]) -> None:
    ranked = rank_solution_plans(tuple(_PLANS[plan_id] for plan_id in order))
    assert tuple(plan.plan_id for plan in ranked) == ("plan_a", "plan_b", "plan_c", "plan_d")


@given(
    st.sampled_from(
        [
            CandidateStatus.SIRA_INELIGIBLE,
            CandidateStatus.SEIL_PASS,
            CandidateStatus.CONDITIONAL,
            CandidateStatus.INSUFFICIENT_EVIDENCE,
        ]
    )
)
def test_hard_blocked_plan_cannot_win(blocked_status: CandidateStatus) -> None:
    blocked = SolutionPlan(
        plan_id="blocked",
        action=SolutionAction.BUY,
        component_ids=("blocked_component",),
        status=blocked_status,
        preference_results=(PreferenceResult("criterion", 5, 1),),
        stack_risk=StackRisk.LOW,
        total_cost=Money(0, "USD"),
        horizon_days=30,
        required_evidence_coverage=1,
        maximum_evidence_age_ratio=0,
    )
    safe = _property_plan("safe", "0", 1000)
    assert rank_solution_plans((blocked, safe)) == (safe,)
