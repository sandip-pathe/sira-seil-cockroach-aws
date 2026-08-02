from __future__ import annotations

import json
from datetime import UTC, datetime
from fractions import Fraction
from typing import Any

import pytest
from sira_api.graph_ledger import DecisionLedgerMetadata, build_decision_ledger
from sira_api.graph_persistence import (
    EvaluationPersistenceMetadata,
    build_counterfactual_record,
    build_evaluation_graph_write,
    build_evaluation_pipeline_version,
)

from decision_engine import evaluate_decision_graph, load_demo_decision_graph_input
from decision_engine.graph_v1_models import DecisionGraphDecision, DecisionGraphInput
from domain import content_hash

NOW = datetime(2026, 8, 2, 6, 0, tzinfo=UTC)


def _artifacts() -> tuple[
    DecisionGraphInput,
    DecisionGraphDecision,
    dict[str, Any],
    EvaluationPersistenceMetadata,
]:
    decision_input = load_demo_decision_graph_input()
    decision = evaluate_decision_graph(decision_input, generated_at=NOW)
    ledger = build_decision_ledger(
        decision,
        decision_input,
        DecisionLedgerMetadata(
            decision_id="dec_graph_demo",
            decision_version=1,
            supersedes_decision_id=None,
            request_id="req_graph_demo",
            purchase_brief_id="pb_graph_demo",
            purchase_brief_version=1,
            requirement_brief_id="rb_graph_demo",
            requirement_brief_version=1,
            company_profile_version=1,
            stack_snapshot=1,
            policy_version=1,
            created_at=NOW,
        ),
    )
    metadata = EvaluationPersistenceMetadata(
        organization_id="org_graph_demo",
        purchase_request_id="req_graph_demo",
        purchase_brief_id="pb_graph_demo",
        decision_id="dec_graph_demo",
        candidate_set_version="candidate_set_demo_v1",
        quote_set_version="quote_set_demo_v1",
        risk_rule_set_version="risk_rules_demo_v1",
        valuation_currency="USD",
    )
    return decision_input, decision, ledger, metadata


def test_adapter_builds_complete_stable_evaluation_graph() -> None:
    decision_input, decision, ledger, metadata = _artifacts()
    graph = build_evaluation_graph_write(decision, decision_input, ledger, metadata)
    repeated = build_evaluation_graph_write(decision, decision_input, ledger, metadata)

    evaluation = decision.base
    assert graph.evaluation_run.id == repeated.evaluation_run.id
    assert graph.evaluation_run.input_payload_hash == repeated.evaluation_run.input_payload_hash
    assert graph.evaluation_run.evaluation_payload_hash == evaluation.evaluation_payload_hash
    assert (
        content_hash(graph.evaluation_run.input_payload) == graph.evaluation_run.input_payload_hash
    )
    assert (
        content_hash(graph.evaluation_run.evaluation_payload)
        == graph.evaluation_run.evaluation_payload_hash
    )
    assert set(graph.evaluation_run.input_payload) == {
        "schema_version",
        "run_kind",
        "versions",
        "evaluated_at",
        "candidate_set_version",
        "quote_set_version",
        "risk_rule_set_version",
        "frozen_input_hashes",
        "removed_private_fact_ids",
    }

    assert len(graph.candidate_set_members) == (
        len(decision_input.candidates) + len(decision_input.current_actions)
    )
    assert len(graph.solution_plans) == len(evaluation.plans)
    assert len(graph.solution_plan_components) == sum(
        len(plan.components) for plan in evaluation.plans
    )
    assert len(graph.decision_gate_results) == sum(
        len(plan.gate_results) for plan in evaluation.plans
    )
    assert len(graph.evidence_assessments) == len(evaluation.evidence_assessments)
    assert len(graph.score_components) == sum(
        len(plan.score_components) for plan in evaluation.plans
    )
    assert len(graph.score_bounds) == 7 * len(evaluation.plans)
    assert len(graph.robustness_frontiers) == 3 * len(evaluation.plans)

    plan_record_ids = {plan.id for plan in graph.solution_plans}
    assert all(
        child.solution_plan_record_id in plan_record_ids for child in graph.solution_plan_components
    )
    assert all(
        child.solution_plan_record_id in plan_record_ids for child in graph.decision_gate_results
    )
    assert all(child.solution_plan_record_id in plan_record_ids for child in graph.score_components)
    assert all(child.solution_plan_record_id in plan_record_ids for child in graph.score_bounds)
    assert all(
        child.solution_plan_record_id in plan_record_ids for child in graph.robustness_frontiers
    )
    assert {bound.dimension for bound in graph.score_bounds} == {
        "PREFERENCE",
        "STACK_RISK",
        "TCO",
        "DECISION_MATERIAL_COVERAGE",
        "EVIDENCE_AGE",
        "HARD_COVERAGE",
        "UNIVERSE_COVERAGE",
    }
    for bound in graph.score_bounds:
        if bound.bound_status != "AVAILABLE":
            continue
        assert bound.lower_numerator is not None
        assert bound.lower_denominator is not None
        assert bound.base_numerator is not None
        assert bound.base_denominator is not None
        assert bound.upper_numerator is not None
        assert bound.upper_denominator is not None
        lower = Fraction(bound.lower_numerator, bound.lower_denominator)
        base = Fraction(bound.base_numerator, bound.base_denominator)
        upper = Fraction(bound.upper_numerator, bound.upper_denominator)
        assert lower <= base <= upper
        if bound.dimension in {
            "PREFERENCE",
            "DECISION_MATERIAL_COVERAGE",
            "EVIDENCE_AGE",
        }:
            assert base == (lower + upper) / 2

    current_member_kinds = {
        member.current_action_id: member.member_kind
        for member in graph.candidate_set_members
        if member.current_action_id is not None
    }
    assert current_member_kinds["current_no_action"] == "NO_ACTION"
    assert current_member_kinds["current_reuse_existing"] == "CURRENT_STACK"
    assert current_member_kinds["current_renew"] == "CONTRACT_ACTION"


def test_pipeline_and_counterfactual_rows_are_idempotent_and_privacy_safe() -> None:
    decision_input, decision, _, metadata = _artifacts()
    first = build_evaluation_pipeline_version(decision_input, metadata)
    second = build_evaluation_pipeline_version(decision_input, metadata)

    assert first.id == second.id
    assert first.payload == second.payload
    assert first.content_hash == second.content_hash == content_hash(first.payload)
    assert first.payload["risk_rule_set_complete"] is True
    assert first.payload["risk_rule_set_hash"].startswith("sha256:")

    row = build_counterfactual_record(decision, metadata)
    assert row.record_hash == content_hash(row.payload)
    assert set(row.payload) == {
        "outcome",
        "removed_fact_ids",
        "alternative_fact_id_sets",
        "tested_limit",
        "before_evaluation_payload_hash",
        "after_evaluation_payload_hash",
        "generic_evaluation_payload_hash",
        "before_selected_plan_id",
        "after_selected_plan_id",
        "generic_selected_plan_id",
        "changed_gate_ids",
    }
    serialized = json.dumps(row.payload, sort_keys=True)
    assert "buyer_facts" not in serialized
    assert "private" not in serialized
    for fact in decision_input.buyer_facts:
        assert fact.field not in serialized


def test_adapter_rejects_a_mutated_decision_ledger() -> None:
    decision_input, decision, ledger, metadata = _artifacts()
    ledger["selected_solution_plan_id"] = "plan_tampered"

    with pytest.raises(ValueError, match="decision_hash"):
        build_evaluation_graph_write(decision, decision_input, ledger, metadata)
