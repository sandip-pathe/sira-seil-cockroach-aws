from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

import pytest
from sira_api.commercial_terms import (
    CommercialTermsConflict,
    build_demo_plan_commercial_terms,
    build_purchase_intent_payload,
    validate_plan_commercial_terms,
)
from sira_api.fixtures import DemoFixtureBundle

from decision_engine import evaluate_decision_graph, load_demo_decision_graph_input
from domain import content_hash


def test_demo_commercial_terms_bind_exact_selected_plan_and_intent() -> None:
    fixtures = DemoFixtureBundle.load()
    decision_input = load_demo_decision_graph_input()
    decision = evaluate_decision_graph(decision_input)
    selected_plan_id = decision.base.selected_plan_id
    assert selected_plan_id is not None

    terms_by_plan = build_demo_plan_commercial_terms(
        fixtures,
        decision_input,
        decision,
        stack_patch_id="patch_exact",
    )
    terms = terms_by_plan[selected_plan_id]
    assert terms["pack_id"] == "fixture_selected_fit"
    assert terms["offer_id"] == "offer_fixture_d_monthly"
    assert terms["quote_id"] == "quote_fixture_d_v1"
    assert terms["landed_total"] == "89.00"
    assert terms["commercial_terms_hash"] == content_hash(
        {key: value for key, value in terms.items() if key != "commercial_terms_hash"}
    )

    intent = build_purchase_intent_payload(
        organization_id="org_consultco",
        decision_id="dec_exact",
        decision_version=3,
        decision_hash="sha256:" + "1" * 64,
        selection_id="selection_exact",
        solution_plan_id=selected_plan_id,
        stack_patch_id="patch_exact",
        purchase_intent_id="pi_exact",
        commercial_terms=terms,
        locked_at=datetime(2026, 8, 2, 7, 0, tzinfo=UTC),
    )
    assert intent["decision_id"] == "dec_exact"
    assert intent["solution_plan_id"] == selected_plan_id
    assert intent["merchant"] == fixtures.live_quote["merchant"]
    assert intent["intent_hash"] == content_hash(
        {key: value for key, value in intent.items() if key != "intent_hash"}
    )
    assert "source_quote_hash" not in intent
    assert "commercial_terms_hash" not in intent


def test_commercial_terms_tampering_fails_closed() -> None:
    fixtures = DemoFixtureBundle.load()
    decision_input = load_demo_decision_graph_input()
    decision = evaluate_decision_graph(decision_input)
    selected_plan_id = decision.base.selected_plan_id
    assert selected_plan_id is not None
    terms = build_demo_plan_commercial_terms(
        fixtures,
        decision_input,
        decision,
        stack_patch_id="patch_exact",
    )[selected_plan_id]

    tampered = deepcopy(terms)
    tampered["amount"] = "1.00"
    with pytest.raises(CommercialTermsConflict, match="hash"):
        validate_plan_commercial_terms(
            tampered,
            solution_plan_id=selected_plan_id,
            stack_patch_id="patch_exact",
        )
