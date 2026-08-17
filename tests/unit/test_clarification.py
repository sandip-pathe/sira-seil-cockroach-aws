from __future__ import annotations

from decision_engine.clarification import (
    ClarificationCandidate,
    select_material_clarification,
)


def test_selects_one_question_only_when_answer_can_change_decision() -> None:
    selected = select_material_clarification(
        (
            ClarificationCandidate(
                fact_id="preferred_color",
                question="Which color do you prefer?",
                expected_uncertainty_reduction=0.8,
            ),
            ClarificationCandidate(
                fact_id="data_residency",
                question="Must recordings stay in the EU?",
                affects_hard_gate=True,
                can_change_rank=True,
                expected_uncertainty_reduction=0.7,
                user_effort=1,
            ),
            ClarificationCandidate(
                fact_id="billing_cycle",
                question="Do you prefer annual billing?",
                can_change_rank=True,
                expected_uncertainty_reduction=0.2,
                user_effort=2,
            ),
        )
    )
    assert selected is not None
    assert selected.fact_id == "data_residency"
    assert (
        select_material_clarification(
            (
                ClarificationCandidate(
                    fact_id="preferred_color",
                    question="Which color do you prefer?",
                ),
            )
        )
        is None
    )


def test_clarification_ties_are_stable() -> None:
    first = ClarificationCandidate(fact_id="a_fact", question="A?", can_change_rank=True)
    second = ClarificationCandidate(fact_id="b_fact", question="B?", can_change_rank=True)
    assert select_material_clarification((second, first)) == first
