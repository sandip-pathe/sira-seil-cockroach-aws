from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sira_api.graph_ledger import DecisionLedgerMetadata, build_decision_ledger

from decision_engine import (
    compile_decision_graph_input,
    evaluate_decision_graph,
    load_demo_decision_source,
)
from domain import DomainValidationError

ROOT = Path(__file__).resolve().parents[2]


def _source_with_conflict(
    *,
    kind: str,
    selected_fact_id: str | None = None,
    decided_by_role: str = "security_privacy_owner",
):
    source = load_demo_decision_source(ROOT / "fixtures" / "demo")
    passport = deepcopy(source.buyer_passport)
    competing = deepcopy(passport["facts"][0])
    competing.update(
        {
            "fact_id": "bf_training_allowed_requester",
            "value": True,
            "kind": kind,
            "stakeholder_role": "requester"
            if kind == "context"
            else "security_privacy_owner",
        }
    )
    passport["facts"].append(competing)
    purchase = deepcopy(source.purchase_brief)
    if selected_fact_id is not None:
        purchase["actor_conflict_resolutions"] = [
            {
                "field": "product.trains_on_customer_data",
                "selected_fact_id": selected_fact_id,
                "decided_by_role": decided_by_role,
                "reason": "The security owner reviewed the competing assertions.",
            }
        ]
    return replace(source, buyer_passport=passport, purchase_brief=purchase)


def test_unique_higher_authority_fact_controls_conflict_and_is_hash_bound() -> None:
    graph_input = compile_decision_graph_input(_source_with_conflict(kind="context"))

    facts = [
        fact
        for fact in graph_input.buyer_facts
        if fact.field == "product.trains_on_customer_data"
    ]
    assert [fact.fact_id for fact in facts] == ["bf_no_customer_training"]
    assert facts[0].authority_level == "POLICY_OWNER"
    assert graph_input.actor_conflict_resolutions[0].strategy == "AUTHORITY_PRECEDENCE"

    decision = evaluate_decision_graph(graph_input)
    hashes = dict(decision.base.frozen_input_hashes)
    assert "actor_conflict_resolutions" in hashes
    selected = next(
        plan for plan in decision.base.plans if plan.plan_id == decision.base.selected_plan_id
    )
    assert selected.components[0].component_id == "product_fixture_d"


def test_equal_authority_conflict_stops_compilation_without_owner_decision() -> None:
    with pytest.raises(
        DomainValidationError,
        match=r"unresolved equal-authority actor conflict for product\.trains_on_customer_data",
    ):
        compile_decision_graph_input(_source_with_conflict(kind="hard_constraint"))


def test_declared_field_owner_can_resolve_equal_authority_conflict() -> None:
    graph_input = compile_decision_graph_input(
        _source_with_conflict(
            kind="hard_constraint",
            selected_fact_id="bf_training_allowed_requester",
        )
    )

    resolution = graph_input.actor_conflict_resolutions[0]
    assert resolution.strategy == "EXPLICIT_OWNER_DECISION"
    assert resolution.selected_fact_id == "bf_training_allowed_requester"
    assert resolution.decided_by_role == "security_privacy_owner"
    gate = next(item for item in graph_input.gates if item.gate_id == "gate_no_customer_training")
    assert gate.predicates[0].value is True
    assert gate.source_fact_ids == ("bf_training_allowed_requester",)

    decision = evaluate_decision_graph(graph_input)
    ledger = build_decision_ledger(
        decision,
        graph_input,
        DecisionLedgerMetadata(
            decision_id="dec_actor_conflict",
            decision_version=1,
            supersedes_decision_id=None,
            request_id="req_demo",
            purchase_brief_id="pb_consultco_v1",
            purchase_brief_version=1,
            requirement_brief_id="rb_consultco_v1",
            requirement_brief_version=1,
            company_profile_version=1,
            stack_snapshot=1,
            policy_version=1,
            created_at=datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
            selected_stack_patch_id="patch_consultco_fixture_d",
        ),
    )
    assert ledger["actor_conflict_resolutions"][0]["selected_fact_id"] == (
        "bf_training_allowed_requester"
    )


def test_non_owner_cannot_resolve_equal_authority_conflict() -> None:
    with pytest.raises(
        DomainValidationError,
        match="requires decision by security_privacy_owner",
    ):
        compile_decision_graph_input(
            _source_with_conflict(
                kind="hard_constraint",
                selected_fact_id="bf_training_allowed_requester",
                decided_by_role="legal_owner",
            )
        )


def test_undeclared_owner_role_cannot_gain_authority_by_name() -> None:
    source = load_demo_decision_source(ROOT / "fixtures" / "demo")
    passport = deepcopy(source.buyer_passport)
    passport["facts"][0]["stakeholder_role"] = "invented_owner"

    with pytest.raises(DomainValidationError, match="undeclared actor role invented_owner"):
        compile_decision_graph_input(replace(source, buyer_passport=passport))


def test_purchase_gate_cannot_disagree_with_its_source_fact() -> None:
    source = load_demo_decision_source(ROOT / "fixtures" / "demo")
    purchase = deepcopy(source.purchase_brief)
    purchase["hard_gates"][0]["value"] = True

    with pytest.raises(
        DomainValidationError,
        match="gate_no_customer_training disagrees with its source facts",
    ):
        compile_decision_graph_input(replace(source, purchase_brief=purchase))
