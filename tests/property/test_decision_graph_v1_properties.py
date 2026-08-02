from __future__ import annotations

from dataclasses import replace
from itertools import permutations
from pathlib import Path

import pytest

from decision_engine.graph_v1 import evaluate_decision_graph_once
from decision_engine.graph_v1_fixtures import load_demo_decision_graph_input

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "demo"


@pytest.mark.parametrize("order", tuple(permutations(range(4))))
def test_input_permutation_cannot_change_order_or_hash(order: tuple[int, ...]) -> None:
    decision_input = load_demo_decision_graph_input(FIXTURE_ROOT)
    expected = evaluate_decision_graph_once(decision_input)
    permuted = evaluate_decision_graph_once(
        replace(
            decision_input, candidates=tuple(decision_input.candidates[index] for index in order)
        )
    )

    assert permuted.ranked_plan_ids == expected.ranked_plan_ids
    assert permuted.evaluation_payload_hash == expected.evaluation_payload_hash


def test_proportionally_equivalent_weights_cannot_change_order() -> None:
    decision_input = load_demo_decision_graph_input(FIXTURE_ROOT)
    criteria = tuple(
        replace(item, weight=weight)
        for item, weight in zip(decision_input.preferences[:2], (1, 2), strict=True)
    )
    scaled = tuple(
        replace(item, weight=weight) for item, weight in zip(criteria, (2, 4), strict=True)
    )
    first = evaluate_decision_graph_once(replace(decision_input, preferences=criteria))
    second = evaluate_decision_graph_once(replace(decision_input, preferences=scaled))

    assert first.ranked_plan_ids == second.ranked_plan_ids


def test_alias_duplicate_cannot_increase_options_coverage_or_rank() -> None:
    decision_input = load_demo_decision_graph_input(FIXTURE_ROOT)
    baseline = evaluate_decision_graph_once(decision_input)
    original = next(
        item for item in decision_input.candidates if item.product_id == "product_fixture_d"
    )
    duplicate = replace(
        original,
        record_id="record_fixture_d_reseller_alias",
        seller_id="seller_fixture_d_inc",
        product_id="fixture_d_meeting_notes",
        edition="Team Annual",
        region="US-East",
        offer_id="reseller_offer_fixture_d",
    )
    duplicated = evaluate_decision_graph_once(
        replace(decision_input, candidates=(*decision_input.candidates, duplicate))
    )

    assert duplicated.coverage.raw_record_count == baseline.coverage.raw_record_count + 1
    assert duplicated.coverage.canonical_product_count == baseline.coverage.canonical_product_count
    assert (
        duplicated.coverage.generated_solution_plan_count
        == baseline.coverage.generated_solution_plan_count
    )
    assert duplicated.ranked_plan_ids == baseline.ranked_plan_ids
    assert duplicated.coverage.duplicate_count == 1
