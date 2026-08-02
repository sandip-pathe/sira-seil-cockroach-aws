from __future__ import annotations

from copy import deepcopy

import pytest

from decision_engine import (
    DecisionSourceBundle,
    compile_decision_graph_input,
    evaluate_decision_graph,
    load_demo_decision_source,
)


def _selected_component(source: DecisionSourceBundle) -> tuple[str, dict[str, str]]:
    graph_input = compile_decision_graph_input(source)
    decision = evaluate_decision_graph(
        graph_input,
        evaluation_id="eval_compiler_test",
        generated_at=graph_input.evaluated_at,
    )
    assert decision.base.selected_plan_id is not None
    selected = next(
        plan for plan in decision.base.plans if plan.plan_id == decision.base.selected_plan_id
    )
    return selected.components[0].component_id, dict(decision.base.frozen_input_hashes)


def test_persistable_source_bundle_round_trips_without_changing_the_graph() -> None:
    source = load_demo_decision_source()

    restored = DecisionSourceBundle.from_payload(source.to_payload())

    assert compile_decision_graph_input(restored) == compile_decision_graph_input(source)


def test_two_persisted_company_policies_produce_distinct_inputs_and_winners() -> None:
    company_aware = load_demo_decision_source()
    generic_payload = company_aware.to_payload()
    generic_purchase_brief = deepcopy(generic_payload["purchase_brief"])
    generic_purchase_brief["hard_gates"] = []
    generic_payload["purchase_brief"] = generic_purchase_brief
    generic = DecisionSourceBundle.from_payload(generic_payload)

    company_winner, company_hashes = _selected_component(company_aware)
    generic_winner, generic_hashes = _selected_component(generic)

    assert company_winner == "product_fixture_d"
    assert generic_winner == "product_fixture_a"
    assert company_hashes["gates"] != generic_hashes["gates"]
    assert company_hashes != generic_hashes


def test_incomplete_source_bundle_fails_before_evaluation() -> None:
    payload = load_demo_decision_source().to_payload()
    del payload["buyer_passport"]

    with pytest.raises(ValueError, match="buyer_passport"):
        DecisionSourceBundle.from_payload(payload)
