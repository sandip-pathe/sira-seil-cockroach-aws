from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from decision_engine.bounds import ExactRatio
from decision_engine.graph_v1 import (
    _predicate_matches,
    _primary_status,
    evaluate_decision_graph,
    evaluate_decision_graph_once,
    evaluation_canonical_payload,
    search_private_fact_counterfactuals,
)
from decision_engine.graph_v1_fixtures import load_demo_decision_graph_input
from decision_engine.graph_v1_models import (
    CounterfactualOutcome,
    DecisionGraphEvaluation,
    EvaluatedPlan,
    GateReason,
    GateResult,
    NormalizationKind,
    OfferCost,
    Predicate,
    PreferenceCriterion,
    ProductFact,
    RiskRule,
)
from decision_engine.graph_v1_recall import _scope_matches, recall_and_deduplicate
from domain import content_hash
from domain.enums import (
    CandidateStatus,
    PackAuthority,
    RankStability,
    SolutionAction,
    StackRisk,
    TruthValue,
)
from domain.errors import DomainValidationError
from domain.money import Money

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "demo"


def _selected(evaluation: DecisionGraphEvaluation) -> EvaluatedPlan:
    return next(plan for plan in evaluation.plans if plan.plan_id == evaluation.selected_plan_id)


def test_graph_predicates_do_not_coerce_booleans_to_integers() -> None:
    assert not _predicate_matches(True, Predicate("product.flag", "eq", 1))
    assert _predicate_matches(True, Predicate("product.flag", "neq", 1))


def test_evidence_scope_requires_exact_match_or_explicit_wildcard() -> None:
    assert _scope_matches("US", "us")
    assert _scope_matches("*", "RUSSIA")
    assert not _scope_matches("US", "RUSSIA")


@pytest.mark.parametrize("change", ("currency", "horizon"))
def test_graph_rejects_incomparable_costs(change: str) -> None:
    decision_input = load_demo_decision_graph_input(FIXTURE_ROOT)
    selected_offer = next(item for item in decision_input.offers if "fixture_d" in item.offer_id)
    if change == "currency":
        replacement = replace(
            selected_offer,
            low=Money("89.00", "EUR"),
            base=Money("89.00", "EUR"),
            high=Money("109.00", "EUR"),
            line_items=(),
            payment_required=False,
        )
    else:
        replacement = replace(selected_offer, horizon_days=31)
    offers = tuple(
        replacement if item is selected_offer else item for item in decision_input.offers
    )

    with pytest.raises(DomainValidationError, match="currency and comparison horizon"):
        evaluate_decision_graph_once(replace(decision_input, offers=offers))


def test_risk_rules_use_assessed_evidence_instead_of_stale_raw_facts() -> None:
    decision_input = load_demo_decision_graph_input(FIXTURE_ROOT)
    selected_candidate = next(
        item for item in decision_input.candidates if item.product_id == "product_fixture_d"
    )
    stale_ids = {
        evidence_id for fact in selected_candidate.facts for evidence_id in fact.evidence_ids
    }
    stale_time = decision_input.evaluated_at - timedelta(days=365)
    evidence = tuple(
        replace(item, observed_at_lower=stale_time, observed_at_upper=stale_time)
        if item.evidence_id in stale_ids
        else item
        for item in decision_input.evidence
    )
    risk = RiskRule(
        "risk_stale_fact_must_not_match",
        (SolutionAction.REPLACE,),
        Predicate("product.deployment_days", "eq", 1),
        StackRisk.CRITICAL,
        StackRisk.CRITICAL,
        StackRisk.CRITICAL,
        StackRisk.LOW,
        StackRisk.LOW,
        StackRisk.LOW,
    )
    evaluation = evaluate_decision_graph_once(
        replace(decision_input, evidence=evidence, risk_rules=(*decision_input.risk_rules, risk))
    )
    plan = next(
        item for item in evaluation.plans if item.components[0].component_id == "product_fixture_d"
    )

    assert "risk_stale_fact_must_not_match:STALE_EVIDENCE" in (
        plan.dimensions.triggered_risk_rule_ids
    )
    assert plan.dimensions.stack_risk is not None
    assert plan.dimensions.stack_risk.base is StackRisk.LOW


def test_dedup_representative_keeps_a_real_pack_version_offer_binding() -> None:
    decision_input = load_demo_decision_graph_input(FIXTURE_ROOT)
    original = next(
        item for item in decision_input.candidates if item.product_id == "product_fixture_d"
    )
    newer = replace(
        original,
        record_id="record_fixture_d_newer",
        pack_id="pack_fixture_d_newer",
        pack_version=2,
        offer_id="offer_fixture_d_newer",
    )
    recalled = recall_and_deduplicate(
        replace(decision_input, candidates=(*decision_input.candidates, newer))
    )
    representative = next(
        item for item in recalled.representatives if item.product_id == original.product_id
    )

    assert (
        representative.pack_id,
        representative.pack_version,
        representative.offer_id,
    ) == (newer.pack_id, newer.pack_version, newer.offer_id)


def test_frozen_fixture_runs_from_raw_facts_and_builds_every_locked_action() -> None:
    decision_input = load_demo_decision_graph_input(FIXTURE_ROOT)
    decision = evaluate_decision_graph(
        decision_input,
        evaluation_id="eval_not_hashed",
        generated_at=datetime(2030, 1, 1, tzinfo=UTC),
    )
    selected = _selected(decision.base)

    assert selected.action is SolutionAction.REPLACE
    assert selected.components[0].component_id == "product_fixture_d"
    assert decision.base.rank_stability == RankStability.STABLE.value
    assert len(decision.base.plans) == 10
    assert {plan.action for plan in decision.base.plans} == {
        SolutionAction.REPLACE,
        SolutionAction.REUSE_EXISTING,
        SolutionAction.CONFIGURE_EXISTING,
        SolutionAction.NO_ACTION,
        SolutionAction.RENEW,
        SolutionAction.RESIZE,
        SolutionAction.CANCEL,
    }
    assert all(plan.construction_lifecycle.value == "CANDIDATE" for plan in decision.base.plans)
    runner_up = next(
        plan for plan in decision.base.plans if plan.plan_id == decision.base.ranked_plan_ids[1]
    )
    assert runner_up.action is SolutionAction.RENEW
    assert runner_up.components[0].component_id == "inst_meeting_intelligence_incumbent"
    assert decision.base.versions.offer_set_version == "demo_offer_set_v1_buyer_txn_demo_v1"


def test_demo_retains_buyer_and_seller_provenance_and_orders_runner_up() -> None:
    decision = evaluate_decision_graph(load_demo_decision_graph_input(FIXTURE_ROOT))
    plans_by_component = {plan.components[0].component_id: plan for plan in decision.base.plans}

    assert plans_by_component["product_fixture_a"].status is CandidateStatus.SIRA_INELIGIBLE
    assert plans_by_component["product_fixture_a"].primary_reason is not None
    assert plans_by_component["product_fixture_a"].primary_reason.reason_code.startswith(
        "BUYER_POLICY_"
    )
    assert plans_by_component["product_fixture_b"].status is CandidateStatus.SEIL_PASS
    assert plans_by_component["product_fixture_b"].primary_reason is not None
    assert (
        plans_by_component["product_fixture_b"].primary_reason.reason_code
        == "SHARED_CLIENT_WORKSPACE_UNSUPPORTED"
    )
    ranked_components = tuple(
        next(
            plan.components[0].component_id
            for plan in decision.base.plans
            if plan.plan_id == plan_id
        )
        for plan_id in decision.base.ranked_plan_ids
    )
    assert ranked_components.index("product_fixture_d") < ranked_components.index(
        "product_fixture_c"
    )


def test_generic_rerun_selects_cheapest_replacement_and_counterfactual_replays() -> None:
    decision_input = load_demo_decision_graph_input(FIXTURE_ROOT)
    decision = evaluate_decision_graph(decision_input)
    generic = _selected(decision.generic)

    assert generic.components[0].component_id == "product_fixture_a"
    assert decision.counterfactual.outcome is CounterfactualOutcome.WINNER_CHANGED
    assert decision.counterfactual.removed_fact_ids == ("bf_restricted_client_conversations",)
    assert decision.counterfactual.alternative_fact_id_sets == (("rf_shared_client_workspace",),)

    alternate = evaluate_decision_graph_once(
        replace(
            decision_input,
            removed_private_fact_ids=frozenset(decision.counterfactual.removed_fact_ids),
        )
    )
    assert (
        alternate.evaluation_payload_hash == decision.counterfactual.after_evaluation_payload_hash
    )
    assert (
        decision.counterfactual.before_evaluation_payload_hash
        == decision.base.evaluation_payload_hash
    )
    assert (
        decision.counterfactual.generic_evaluation_payload_hash
        == decision.generic.evaluation_payload_hash
    )


def test_counterfactual_limit_reports_no_small_claim_without_overclaiming() -> None:
    original = load_demo_decision_graph_input(FIXTURE_ROOT)
    public_only = replace(
        original,
        buyer_facts=tuple(replace(fact, private=False) for fact in original.buyer_facts),
    )
    base = evaluate_decision_graph_once(public_only)
    record = search_private_fact_counterfactuals(public_only, base, base, limit=3)

    assert record.outcome is CounterfactualOutcome.NO_SMALL_COUNTERFACTUAL_FOUND
    assert record.tested_limit == 3
    assert record.removed_fact_ids == ()
    assert record.after_evaluation_payload_hash is None


def test_evaluation_and_decision_hashes_exclude_generated_metadata_and_are_non_circular() -> None:
    decision_input = load_demo_decision_graph_input(FIXTURE_ROOT)
    first = evaluate_decision_graph(
        decision_input,
        evaluation_id="eval_random_1",
        generated_at=datetime(2026, 8, 2, 13, tzinfo=UTC),
    )
    second = evaluate_decision_graph(
        decision_input,
        evaluation_id="eval_random_2",
        generated_at=datetime(2031, 1, 1, tzinfo=UTC),
    )

    assert first.base.evaluation_payload_hash == second.base.evaluation_payload_hash
    assert first.decision_hash == second.decision_hash
    assert "evaluation_id" not in evaluation_canonical_payload(first.base)
    assert "generated_at" not in evaluation_canonical_payload(first.base)
    assert not hasattr(first.counterfactual, "decision_hash")
    assert first.counterfactual.record_hash == content_hash(
        {
            "outcome": first.counterfactual.outcome.value,
            "removed_fact_ids": first.counterfactual.removed_fact_ids,
            "alternative_fact_id_sets": first.counterfactual.alternative_fact_id_sets,
            "tested_limit": first.counterfactual.tested_limit,
            "before_evaluation_payload_hash": first.counterfactual.before_evaluation_payload_hash,
            "after_evaluation_payload_hash": first.counterfactual.after_evaluation_payload_hash,
            "generic_evaluation_payload_hash": first.counterfactual.generic_evaluation_payload_hash,
            "before_selected_plan_id": first.counterfactual.before_selected_plan_id,
            "after_selected_plan_id": first.counterfactual.after_selected_plan_id,
            "generic_selected_plan_id": first.counterfactual.generic_selected_plan_id,
            "changed_gate_ids": first.counterfactual.changed_gate_ids,
        }
    )


def test_unknown_optional_evidence_is_zero_conservative_and_visible_optimistically() -> None:
    evaluation = evaluate_decision_graph_once(load_demo_decision_graph_input(FIXTURE_ROOT))
    selected = _selected(evaluation)
    crm = next(
        item for item in selected.score_components if item.criterion_id == "pref_native_crm_sync"
    )
    coverage = selected.dimensions.decision_material_coverage

    assert crm.conservative_satisfaction == ExactRatio(0)
    assert crm.optimistic_satisfaction == ExactRatio(1)
    assert coverage is not None
    assert coverage.conservative.fraction < coverage.optimistic.fraction


def test_all_gate_reasons_survive_and_primary_status_uses_exact_precedence() -> None:
    decision_input = load_demo_decision_graph_input(FIXTURE_ROOT)
    candidate = next(
        item for item in decision_input.candidates if item.product_id == "product_fixture_d"
    )
    stale_ids = {evidence_id for fact in candidate.facts for evidence_id in fact.evidence_ids}
    stale_time = decision_input.evaluated_at - timedelta(days=365)
    evidence = tuple(
        replace(item, observed_at_lower=stale_time, observed_at_upper=stale_time)
        if item.evidence_id in stale_ids
        else item
        for item in decision_input.evidence
    )
    candidates = tuple(
        replace(item, available=False) if item.record_id == candidate.record_id else item
        for item in decision_input.candidates
    )
    evaluation = evaluate_decision_graph_once(
        replace(decision_input, evidence=evidence, candidates=candidates)
    )
    plan = next(
        item for item in evaluation.plans if item.components[0].component_id == "product_fixture_d"
    )
    statuses = {reason.status for gate in plan.gate_results for reason in gate.reasons}

    assert CandidateStatus.UNAVAILABLE in statuses
    assert CandidateStatus.STALE_EVIDENCE in statuses
    assert plan.status is CandidateStatus.UNAVAILABLE

    for first_index, first in enumerate(tuple(CandidateStatus)):
        for second in tuple(CandidateStatus)[first_index + 1 :]:
            gate = GateResult(
                "precedence_gate",
                TruthValue.FALSE,
                (GateReason("first", first, "first"), GateReason("second", second, "second")),
                ("field",),
                None,
            )
            status, _ = _primary_status((gate,))
            assert status is min(
                (first, second), key=lambda item: tuple(_status_order()).index(item)
            )


def _status_order() -> tuple[CandidateStatus, ...]:
    return (
        CandidateStatus.UNAVAILABLE,
        CandidateStatus.CONFLICTING_EVIDENCE,
        CandidateStatus.STALE_EVIDENCE,
        CandidateStatus.INSUFFICIENT_EVIDENCE,
        CandidateStatus.SIRA_INELIGIBLE,
        CandidateStatus.SEIL_PASS,
        CandidateStatus.AUTHORITY_REQUIRED,
        CandidateStatus.ADVISORY_ONLY,
        CandidateStatus.CONDITIONAL,
        CandidateStatus.ELIGIBLE_WITH_EXCEPTION,
        CandidateStatus.ELIGIBLE,
    )


def test_rank_stability_detects_unknown_frontier_and_missing_bounds() -> None:
    decision_input = load_demo_decision_graph_input(FIXTURE_ROOT)
    uncertain_cancel = PreferenceCriterion(
        criterion_id="pref_cancel_uncertain",
        field="outcome.cancel_recovery",
        weight=5,
        coverage_weight=5,
        normalization=NormalizationKind.BOOLEAN_EQUALS,
        expected=True,
        source_fact_ids=(),
        applies_to_actions=(SolutionAction.CANCEL,),
        allowed_satisfactions=(ExactRatio(0), ExactRatio(1)),
        unknown_upper=ExactRatio(1),
        permitted_evidence_resolution="BUYER_INPUT",
    )
    second_uncertain_cancel = replace(
        uncertain_cancel,
        criterion_id="pref_cancel_uncertain_secondary",
        field="outcome.cancel_transition",
    )
    unstable = evaluate_decision_graph_once(
        replace(
            decision_input,
            preferences=(
                *decision_input.preferences,
                uncertain_cancel,
                second_uncertain_cancel,
            ),
        )
    )
    cancel = next(plan for plan in unstable.plans if plan.action is SolutionAction.CANCEL)
    assert unstable.rank_stability == RankStability.UNSTABLE.value
    assert cancel.ordering_frontier_member

    current_actions = tuple(
        replace(
            item,
            cost=OfferCost(
                item.cost.offer_id,
                item.cost.low,
                item.cost.base,
                None,
                item.cost.horizon_days,
            ),
        )
        if item.action is SolutionAction.CANCEL
        else item
        for item in decision_input.current_actions
    )
    undetermined = evaluate_decision_graph_once(
        replace(decision_input, current_actions=current_actions)
    )
    assert undetermined.rank_stability == RankStability.UNDETERMINED.value
    assert len(undetermined.bound_unavailable_plan_ids) == 1


def test_ordering_resolution_and_quote_frontiers_are_independent() -> None:
    decision_input = load_demo_decision_graph_input(FIXTURE_ROOT)
    candidates = tuple(
        replace(item, authority=PackAuthority.PLATFORM_COMPILED)
        if item.product_id == "product_fixture_d"
        else item
        for item in decision_input.candidates
    )
    evaluation = evaluate_decision_graph_once(replace(decision_input, candidates=candidates))
    research = next(
        plan for plan in evaluation.plans if plan.components[0].component_id == "product_fixture_d"
    )

    assert research.status is CandidateStatus.ADVISORY_ONLY
    assert not research.ordering_frontier_member
    assert research.resolution_frontier_member
    assert research.quote_required
    assert research.quote_policy_reason == "RESOLUTION_FRONTIER"
    assert not research.autonomous_execution_allowed


def test_selected_tco_contains_fee_once_and_current_actions_never_do() -> None:
    evaluation = evaluate_decision_graph_once(load_demo_decision_graph_input(FIXTURE_ROOT))
    selected = _selected(evaluation)
    cost = selected.dimensions.total_cost

    assert cost.base is not None and cost.base.to_dict() == {"amount": "89.00", "currency": "USD"}
    assert [(item.line_item_type, item.base.to_dict()) for item in cost.line_items] == [
        ("MERCHANT_SUBTOTAL", {"amount": "87.00", "currency": "USD"}),
        ("SIRA_TRANSACTION_FEE", {"amount": "2.00", "currency": "USD"}),
    ]
    assert cost.line_items[1].schedule_version == "buyer_txn_demo_v1"
    renewal = next(plan for plan in evaluation.plans if plan.action is SolutionAction.RENEW)
    assert renewal.quote_required
    assert not renewal.dimensions.total_cost.payment_required
    ledger_schema = json.loads(
        (
            FIXTURE_ROOT.parents[1] / "contracts" / "jsonschema" / "decision-ledger.schema.json"
        ).read_text(encoding="utf-8")
    )
    allowed_line_types = set(
        ledger_schema["$defs"]["CostLineItemBounds"]["properties"]["type"]["enum"]
    )
    produced_line_types = {
        item.line_item_type
        for plan in evaluation.plans
        for item in plan.dimensions.total_cost.line_items
    }
    assert produced_line_types <= allowed_line_types
    for plan in evaluation.plans:
        if plan.components[0].source_type == "CURRENT_INSTANCE":
            assert not plan.dimensions.total_cost.payment_required
            assert {item.line_item_type for item in plan.dimensions.total_cost.line_items} == {
                "CONTRACT_COST"
            }
            assert all(
                item.line_item_type != "SIRA_TRANSACTION_FEE"
                for item in plan.dimensions.total_cost.line_items
            )


def test_zero_applicable_hard_gates_use_vacuous_full_coverage() -> None:
    evaluation = evaluate_decision_graph_once(load_demo_decision_graph_input(FIXTURE_ROOT))
    cancel = next(plan for plan in evaluation.plans if plan.action is SolutionAction.CANCEL)

    assert cancel.dimensions.hard_coverage.numerator == 1
    assert cancel.dimensions.hard_coverage.denominator == 1
    assert all(plan.dimensions.hard_coverage.denominator > 0 for plan in evaluation.plans)


def test_missing_evidence_record_is_never_silently_accepted() -> None:
    decision_input = load_demo_decision_graph_input(FIXTURE_ROOT)
    selected_candidate = next(
        item for item in decision_input.candidates if item.product_id == "product_fixture_d"
    )
    removed_id = selected_candidate.facts[0].evidence_ids[0]
    evidence = tuple(item for item in decision_input.evidence if item.evidence_id != removed_id)
    evaluation = evaluate_decision_graph_once(replace(decision_input, evidence=evidence))
    assessment = next(
        item for item in evaluation.evidence_assessments if item.evidence_id == removed_id
    )

    assert assessment.state.value == "UNKNOWN"
    assert "MISSING_EVIDENCE_RECORD" in assessment.reasons
    assert "BOUND_UNAVAILABLE:EVIDENCE_TIME" in assessment.reasons
    plan = next(
        item for item in evaluation.plans if item.components[0].component_id == "product_fixture_d"
    )
    affected = next(
        gate for gate in plan.gate_results if gate.gate_id == "gate_no_customer_training"
    )
    assert affected.truth is TruthValue.UNKNOWN
    assert plan.status is CandidateStatus.INSUFFICIENT_EVIDENCE


def test_conflicting_raw_values_emit_conflict_without_dropping_the_gate_reason() -> None:
    decision_input = load_demo_decision_graph_input(FIXTURE_ROOT)
    candidates = tuple(
        replace(
            item,
            facts=(
                *item.facts,
                ProductFact(
                    "product.trains_on_customer_data",
                    True,
                    ("ev_fixture_d_product",),
                ),
            ),
        )
        if item.product_id == "product_fixture_d"
        else item
        for item in decision_input.candidates
    )
    evaluation = evaluate_decision_graph_once(replace(decision_input, candidates=candidates))
    plan = next(
        item for item in evaluation.plans if item.components[0].component_id == "product_fixture_d"
    )
    gate = next(item for item in plan.gate_results if item.gate_id == "gate_no_customer_training")

    assert gate.truth is TruthValue.CONFLICT
    assert plan.status is CandidateStatus.CONFLICTING_EVIDENCE
    assert any(reason.reason_code == "CONFLICTING_EVIDENCE" for reason in gate.reasons)
