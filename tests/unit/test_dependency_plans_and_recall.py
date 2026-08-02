from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from sira_api.graph_ledger import DecisionLedgerMetadata, build_decision_ledger
from sira_api.graph_persistence import (
    EvaluationPersistenceMetadata,
    build_evaluation_graph_write,
)

from decision_engine import (
    evaluate_decision_graph,
    evaluate_decision_graph_once,
    load_demo_decision_graph_input,
)
from domain.enums import CandidateStatus


def _plan_for_product(evaluation, product_id: str):
    return next(
        plan
        for plan in evaluation.plans
        if plan.components[-1].component_id == product_id
    )


def test_required_components_are_closed_in_dependency_order_and_costed_together() -> None:
    graph_input = load_demo_decision_graph_input()
    candidates = tuple(
        replace(candidate, required_product_ids=("product_fixture_c",))
        if candidate.product_id == "product_fixture_d"
        else candidate
        for candidate in graph_input.candidates
    )

    evaluation = evaluate_decision_graph_once(replace(graph_input, candidates=candidates))
    plan = _plan_for_product(evaluation, "product_fixture_d")

    assert [item.component_id for item in plan.components] == [
        "product_fixture_c",
        "product_fixture_d",
    ]
    assert plan.stable_action_ids == (
        "replace",
        "product_fixture_c",
        "product_fixture_d",
    )
    assert plan.dimensions.total_cost.base is not None
    assert plan.dimensions.total_cost.base.to_dict() == {
        "amount": "188.00",
        "currency": "USD",
    }
    assert plan.status is CandidateStatus.SIRA_INELIGIBLE
    budget = next(item for item in plan.gate_results if item.gate_id == "gate_budget")
    assert budget.truth.value == "FALSE"
    scores = {item.criterion_id: item for item in plan.score_components}
    assert scores["pref_native_integrations"].conservative_satisfaction.to_dict() == {
        "numerator": 1,
        "denominator": 1,
    }
    assert scores["pref_admin_hours"].conservative_satisfaction.to_dict() == {
        "numerator": 0,
        "denominator": 1,
    }


def test_missing_and_cyclic_dependencies_are_explicit_blocking_gates() -> None:
    graph_input = load_demo_decision_graph_input()
    missing = tuple(
        replace(candidate, required_product_ids=("product_not_discovered",))
        if candidate.product_id == "product_fixture_d"
        else candidate
        for candidate in graph_input.candidates
    )
    missing_plan = _plan_for_product(
        evaluate_decision_graph_once(replace(graph_input, candidates=missing)),
        "product_fixture_d",
    )
    assert any(
        reason.reason_code == "MISSING_REQUIRED_COMPONENT"
        for gate in missing_plan.gate_results
        for reason in gate.reasons
    )
    assert missing_plan.lifecycle.value == "BLOCKED"

    cyclic = tuple(
        replace(candidate, required_product_ids=("product_fixture_c",))
        if candidate.product_id == "product_fixture_d"
        else replace(candidate, required_product_ids=("product_fixture_d",))
        if candidate.product_id == "product_fixture_c"
        else candidate
        for candidate in graph_input.candidates
    )
    cyclic_plan = _plan_for_product(
        evaluate_decision_graph_once(replace(graph_input, candidates=cyclic)),
        "product_fixture_d",
    )
    assert any(
        reason.reason_code == "CYCLIC_COMPONENT_DEPENDENCY"
        for gate in cyclic_plan.gate_results
        for reason in gate.reasons
    )
    assert cyclic_plan.lifecycle.value == "BLOCKED"


def test_bundle_hard_gates_use_weakest_component_without_calling_it_evidence_conflict() -> None:
    graph_input = load_demo_decision_graph_input()
    candidates = []
    for candidate in graph_input.candidates:
        if candidate.product_id == "product_fixture_c":
            facts = tuple(
                replace(fact, value=True)
                if fact.field == "product.trains_on_customer_data"
                else fact
                for fact in candidate.facts
            )
            candidate = replace(candidate, facts=facts)
        if candidate.product_id == "product_fixture_d":
            candidate = replace(candidate, required_product_ids=("product_fixture_c",))
        candidates.append(candidate)

    plan = _plan_for_product(
        evaluate_decision_graph_once(
            replace(graph_input, candidates=tuple(candidates))
        ),
        "product_fixture_d",
    )
    gate = next(
        item for item in plan.gate_results if item.gate_id == "gate_no_customer_training"
    )
    assert gate.truth.value == "FALSE"
    assert plan.status is CandidateStatus.SIRA_INELIGIBLE
    assert all(reason.reason_code != "CONFLICTING_EVIDENCE" for reason in gate.reasons)


def test_recall_reports_deduplicated_and_excluded_records_exactly() -> None:
    graph_input = load_demo_decision_graph_input()
    candidate_c = next(
        item for item in graph_input.candidates if item.product_id == "product_fixture_c"
    )
    duplicate_c = replace(candidate_c, record_id="record_fixture_c_duplicate")
    candidates = (
        *(
            replace(candidate, pack_status="REVOKED")
            if candidate.product_id == "product_fixture_d"
            else candidate
            for candidate in graph_input.candidates
        ),
        duplicate_c,
    )
    changed_input = replace(graph_input, candidates=candidates)
    decision = evaluate_decision_graph(changed_input)

    assert decision.base.coverage.raw_record_count == 5
    assert decision.base.coverage.canonical_product_count == 3
    assert decision.base.coverage.duplicate_count == 1
    assert decision.base.coverage.excluded_count == 1
    assert [(item.record_id, item.reason_code) for item in decision.base.recall_exclusions] == [
        ("record_fixture_selected_fit", "PACK_REVOKED")
    ]

    ledger = build_decision_ledger(
        decision,
        changed_input,
        DecisionLedgerMetadata(
            decision_id="dec_recall_coverage",
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
            selected_stack_patch_id="patch_recall_coverage",
        ),
    )
    universe = ledger["evaluated_universe"]
    assert universe["excluded_record_ids"] == ["record_fixture_selected_fit"]
    assert universe["exclusion_reasons"] == [
        {
            "record_id": "record_fixture_selected_fit",
            "reason_code": "PACK_REVOKED",
            "detail": "Pack version is revoked",
        }
    ]
    assert "record_fixture_c_duplicate" in universe["included_record_ids"]
    assert len(universe["identity_merges"]) == 1

    persisted = build_evaluation_graph_write(
        decision,
        changed_input,
        ledger,
        EvaluationPersistenceMetadata(
            organization_id="org_consultco",
            purchase_request_id="req_demo",
            purchase_brief_id="pb_consultco_v1",
            decision_id="dec_recall_coverage",
            candidate_set_version="candidate_set_recall_v1",
            quote_set_version="quote_set_recall_v1",
            risk_rule_set_version="meeting_intelligence_risk_v1",
            valuation_currency="USD",
        ),
    )
    excluded = next(
        item
        for item in persisted.candidate_set_members
        if item.source_record_id == "record_fixture_selected_fit"
    )
    assert excluded.disposition == "EXCLUDED"
    assert excluded.payload["exclusion"]["reason_code"] == "PACK_REVOKED"
