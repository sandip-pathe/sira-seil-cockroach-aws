"""Serialize the pure Decision Graph into the frozen Decision Ledger contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from decision_engine.bounds import ExactRatio
from decision_engine.graph_v1_models import (
    DecisionGraphDecision,
    DecisionGraphInput,
    EvaluatedPlan,
    EvidenceAssessment,
    GateReason,
    GateResult,
)
from domain.hashing import content_hash


@dataclass(frozen=True, slots=True)
class DecisionLedgerMetadata:
    """Database-owned identifiers that are deliberately outside the pure graph."""

    decision_id: str
    decision_version: int
    supersedes_decision_id: str | None
    request_id: str
    purchase_brief_id: str
    purchase_brief_version: int
    requirement_brief_id: str
    requirement_brief_version: int
    company_profile_version: int
    stack_snapshot: int
    policy_version: int
    created_at: datetime
    selected_stack_patch_id: str | None = None


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("Decision Ledger timestamps must be timezone-aware")
    return (
        value.astimezone(UTC)
        .isoformat(timespec="microseconds")
        .replace(".000000+00:00", "Z")
        .replace("+00:00", "Z")
    )


def _ratio(value: ExactRatio, *, display: bool = False) -> dict[str, int | str]:
    return value.to_dict(include_display=display)


def _unavailable(reason_code: str) -> dict[str, str]:
    return {"status": "BOUND_UNAVAILABLE", "reason_code": reason_code}


def _reason(value: GateReason | None) -> dict[str, str] | None:
    if value is None:
        return None
    return {
        "reason_code": value.reason_code,
        "status": value.status.value,
        "detail": value.detail,
    }


def _gate(value: GateResult) -> dict[str, Any]:
    return {
        "gate_id": value.gate_id,
        "truth": value.truth.value,
        "reasons": [_reason(item) for item in value.reasons],
        "evaluated_predicates": list(value.evaluated_predicates),
        "permitted_resolution": value.permitted_resolution,
    }


def _evidence_assessment(
    value: EvidenceAssessment,
    *,
    evidence_by_id: dict[str, Any],
) -> dict[str, Any]:
    source = evidence_by_id[value.evidence_id]
    return {
        "evidence_id": value.evidence_id,
        "record_id": value.record_id,
        "field": value.field,
        "source_class": source.source_class,
        "verification_method": source.verification_method,
        "scope_match": value.scope_match,
        "reconstructable": value.reconstructable,
        "freshness_current": value.freshness_current,
        "disputed": value.disputed,
        "revoked": value.revoked,
        "state": value.state.value,
        "reasons": list(value.reasons),
        "age_bounds": None
        if value.age_bounds is None
        else {
            "lower": _ratio(value.age_bounds.lower),
            "upper": _ratio(value.age_bounds.upper),
        },
    }


def _dimensions(plan: EvaluatedPlan) -> dict[str, Any]:
    value = plan.dimensions
    missing_reason = (
        value.bound_unavailable_reasons[0]
        if value.bound_unavailable_reasons
        else "BOUND_INPUT_UNAVAILABLE"
    )
    preference = value.preference
    stack_risk = value.stack_risk
    coverage = value.decision_material_coverage
    age = value.maximum_evidence_age_ratio
    total_cost = value.total_cost
    return {
        "preference": (
            {
                "conservative": _ratio(preference.conservative, display=True),
                "optimistic": _ratio(preference.optimistic, display=True),
            }
            if preference is not None
            else _unavailable(missing_reason)
        ),
        "stack_risk": {
            "lower": stack_risk.lower.value if stack_risk else _unavailable(missing_reason),
            "base": stack_risk.base.value if stack_risk else _unavailable(missing_reason),
            "upper": stack_risk.upper.value if stack_risk else _unavailable(missing_reason),
        },
        "total_cost": {
            "low": total_cost.low.to_dict()
            if total_cost.low is not None
            else _unavailable(missing_reason),
            "base": total_cost.base.to_dict()
            if total_cost.base is not None
            else _unavailable(missing_reason),
            "high": total_cost.high.to_dict()
            if total_cost.high is not None
            else _unavailable(missing_reason),
        },
        "cost_line_items": [
            {
                "type": item.line_item_type,
                "low": item.low.to_dict(),
                "base": item.base.to_dict(),
                "high": item.high.to_dict(),
                "schedule_version": item.schedule_version,
            }
            for item in total_cost.line_items
        ],
        "payment_required": total_cost.payment_required,
        "hard_coverage": {
            "numerator": value.hard_coverage.numerator,
            "denominator": value.hard_coverage.denominator,
        },
        "decision_material_coverage": {
            "conservative": _ratio(coverage.conservative)
            if coverage
            else _unavailable(missing_reason),
            "optimistic": _ratio(coverage.optimistic) if coverage else _unavailable(missing_reason),
        },
        "maximum_evidence_age_ratio": {
            "lower": _ratio(age.lower) if age else _unavailable(missing_reason),
            "upper": _ratio(age.upper) if age else _unavailable(missing_reason),
        },
        "universe_coverage": _ratio(value.universe_coverage),
        "unresolved_count": value.unresolved_count,
        "conflicting_count": value.conflicting_count,
        "bound_unavailable_reasons": list(value.bound_unavailable_reasons),
    }


def _solution_plan(
    plan: EvaluatedPlan,
    *,
    decision: DecisionGraphDecision,
    decision_input: DecisionGraphInput,
    rank_by_id: dict[str, int],
    selected_stack_patch_id: str | None,
) -> dict[str, Any]:
    candidate_by_product = {item.product_id: item for item in decision_input.candidates}
    coverage_weight = {
        item.criterion_id: item.coverage_weight for item in decision_input.preferences
    }
    components: list[dict[str, str]] = []
    for component in plan.components:
        candidate = candidate_by_product.get(component.component_id)
        components.append(
            {
                "component_id": component.component_id,
                "source_type": "PRODUCT_EVIDENCE" if candidate is not None else "CURRENT_INSTANCE",
                "source_id": candidate.record_id
                if candidate is not None
                else component.component_id,
                "action_type": component.action.value,
            }
        )
    return {
        "solution_plan_id": plan.plan_id,
        "action_type": plan.action.value,
        "components": components,
        "component_hash": plan.component_hash,
        "construction_lifecycle": plan.construction_lifecycle.value,
        "lifecycle": plan.lifecycle.value,
        "status": plan.status.value,
        "primary_reason": _reason(plan.primary_reason),
        "gate_results": [_gate(item) for item in plan.gate_results],
        "score_components": [
            {
                "criterion_id": item.criterion_id,
                "weight": item.weight,
                "coverage_weight": coverage_weight[item.criterion_id],
                "conservative_satisfaction": _ratio(item.conservative_satisfaction),
                "optimistic_satisfaction": _ratio(item.optimistic_satisfaction),
                "conservative_contribution": _ratio(item.contribution_conservative),
                "optimistic_contribution": _ratio(item.contribution_optimistic),
                "evidence_ids": list(item.evidence_ids),
                "evidence_state": item.evidence_state.value,
                "prior_label": item.prior_label,
            }
            for item in plan.score_components
        ],
        "dimensions": _dimensions(plan),
        "stable_action_ids": list(plan.stable_action_ids),
        "rank": rank_by_id.get(plan.plan_id),
        "ordering_frontier_member": plan.ordering_frontier_member,
        "resolution_frontier_member": plan.resolution_frontier_member,
        "quote_required": plan.quote_required,
        "quote_policy_reason": plan.quote_policy_reason,
        "permitted_resolution": plan.permitted_resolution,
        "autonomous_execution_allowed": plan.autonomous_execution_allowed,
        "stack_patch_id": selected_stack_patch_id
        if plan.plan_id == decision.base.selected_plan_id
        else None,
    }


def build_decision_ledger(
    decision: DecisionGraphDecision,
    decision_input: DecisionGraphInput,
    metadata: DecisionLedgerMetadata,
    *,
    component_names: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a closed, hash-stable Decision Ledger from one graph evaluation."""

    evaluation = decision.base
    versions = evaluation.versions
    rank_by_id = {
        solution_plan_id: rank
        for rank, solution_plan_id in enumerate(evaluation.ranked_plan_ids, start=1)
    }
    plan_by_product = {
        plan.components[-1].component_id: plan
        for plan in evaluation.plans
        if plan.components and plan.components[-1].source_type == "PACK"
    }
    assessment_by_key = {
        (item.evidence_id, item.field): item for item in evaluation.evidence_assessments
    }
    evidence_by_id = {item.evidence_id: item for item in decision_input.evidence}
    names = component_names or {}
    component_results: list[dict[str, Any]] = []
    recalled_record_ids = {
        record_id for item in evaluation.identity_records for record_id in item.record_ids
    }
    emitted_products: set[str] = set()
    for candidate in sorted(decision_input.candidates, key=lambda item: item.record_id):
        if (
            candidate.record_id not in recalled_record_ids
            or candidate.product_id in emitted_products
        ):
            continue
        emitted_products.add(candidate.product_id)
        plan = plan_by_product[candidate.product_id]
        relevant_assessments = []
        for fact in candidate.facts:
            for evidence_id in fact.evidence_ids:
                assessment = assessment_by_key.get((evidence_id, fact.field))
                if assessment is not None:
                    relevant_assessments.append(assessment)
        unique_assessments = {(item.evidence_id, item.field): item for item in relevant_assessments}
        component_results.append(
            {
                "component_id": candidate.product_id,
                "name": names.get(candidate.pack_id, candidate.pack_id),
                "pack_id": candidate.pack_id,
                "pack_version": candidate.pack_version,
                "current_instance_id": None,
                "publisher_authority": candidate.authority.value,
                "status": plan.status.value,
                "primary_reason": _reason(plan.primary_reason),
                "gate_results": [_gate(item) for item in plan.gate_results],
                "evidence_assessments": [
                    _evidence_assessment(item, evidence_by_id=evidence_by_id)
                    for item in sorted(
                        unique_assessments.values(),
                        key=lambda value: (value.evidence_id, value.field),
                    )
                ],
            }
        )

    frozen_versions = {
        "request": versions.request_version,
        "company_profile": versions.company_profile_version,
        "stackfile": versions.stackfile_version,
        "registry": versions.registry_version,
        "pack_set": versions.pack_set_version,
        "offer_set": versions.offer_set_version,
        "taxonomy": versions.taxonomy_version,
        "normalization": versions.normalization_version,
        "policy": versions.policy_version,
        "fx": versions.fx_version,
        "pipeline": versions.pipeline_version,
        "engine": versions.engine_version,
    }
    included_record_ids = sorted(recalled_record_ids)
    all_record_ids = {item.record_id for item in decision_input.candidates}
    excluded_record_ids = sorted(all_record_ids - set(included_record_ids))
    stability_summary = {
        "STABLE": "The selected plan remains first across the supported uncertainty bounds.",
        "UNSTABLE": "One or more plans can outrank the selection within supported bounds.",
        "UNDETERMINED": "At least one ordering bound is unavailable.",
    }[evaluation.rank_stability]
    evidence_frontier = [
        {
            "criterion_id": "ordering_frontier",
            "reason_code": "ORDERING_OVERLAP",
            "option_ids": [plan_id],
            "permitted_resolution": "Collect fresher decision-material evidence.",
        }
        for plan_id in evaluation.ordering_frontier_plan_ids
    ]
    counterfactual = decision.counterfactual
    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "decision_id": metadata.decision_id,
        "decision_version": metadata.decision_version,
        "decision_state": "CURRENT",
        "supersedes_decision_id": metadata.supersedes_decision_id,
        "request_id": metadata.request_id,
        "purchase_brief_id": metadata.purchase_brief_id,
        "purchase_brief_version": metadata.purchase_brief_version,
        "requirement_brief_id": metadata.requirement_brief_id,
        "requirement_brief_version": metadata.requirement_brief_version,
        "company_profile_version": metadata.company_profile_version,
        "stack_snapshot": metadata.stack_snapshot,
        "policy_version": metadata.policy_version,
        "evaluation": {
            "evaluation_id": evaluation.evaluation_id,
            "evaluated_at": _timestamp(evaluation.evaluated_at),
            "evaluation_payload_hash": evaluation.evaluation_payload_hash,
            "frozen_versions": frozen_versions,
            "ranked_solution_plan_ids": list(evaluation.ranked_plan_ids),
            "ordering_frontier_plan_ids": list(evaluation.ordering_frontier_plan_ids),
            "bound_unavailable_plan_ids": list(evaluation.bound_unavailable_plan_ids),
        },
        "evaluated_universe": {
            "raw_record_count": evaluation.coverage.raw_record_count,
            "product_evidence_option_count": evaluation.coverage.pack_candidate_count,
            "canonical_product_count": evaluation.coverage.canonical_product_count,
            "duplicate_count": evaluation.coverage.duplicate_count,
            "generated_solution_plan_count": evaluation.coverage.generated_solution_plan_count,
            "evaluated_solution_plan_count": evaluation.coverage.evaluated_solution_plan_count,
            "excluded_count": evaluation.coverage.excluded_count,
            "included_record_ids": included_record_ids,
            "excluded_record_ids": excluded_record_ids,
            "identity_merges": [
                {
                    "canonical_id": item.canonical_id,
                    "merged_record_id": item.merged_record_id,
                    "reasons": list(item.reasons),
                }
                for item in evaluation.identity_merges
            ],
            "coverage_statement": evaluation.coverage.statement,
        },
        "component_results": component_results,
        "solution_plans": [
            _solution_plan(
                plan,
                decision=decision,
                decision_input=decision_input,
                rank_by_id=rank_by_id,
                selected_stack_patch_id=metadata.selected_stack_patch_id,
            )
            for plan in evaluation.plans
        ],
        "decision_outcome": "SELECTED_SOLUTION_PLAN"
        if evaluation.selected_plan_id is not None
        else "NO_ELIGIBLE_SUPPORTED_ACTION",
        "selected_solution_plan_id": evaluation.selected_plan_id,
        "rank_stability": {
            "status": evaluation.rank_stability,
            "summary": stability_summary,
            "evidence_frontier": evidence_frontier,
        },
        "counterfactuals": [
            {
                "outcome": counterfactual.outcome.value,
                "removed_fact_ids": list(counterfactual.removed_fact_ids),
                "alternative_fact_id_sets": [
                    list(item) for item in counterfactual.alternative_fact_id_sets
                ],
                "tested_limit": counterfactual.tested_limit,
                "before_evaluation_payload_hash": counterfactual.before_evaluation_payload_hash,
                "after_evaluation_payload_hash": counterfactual.after_evaluation_payload_hash,
                "generic_evaluation_payload_hash": counterfactual.generic_evaluation_payload_hash,
                "before_selected_plan_id": counterfactual.before_selected_plan_id,
                "after_selected_plan_id": counterfactual.after_selected_plan_id,
                "generic_selected_plan_id": counterfactual.generic_selected_plan_id,
                "changed_gate_ids": list(counterfactual.changed_gate_ids),
                "record_hash": counterfactual.record_hash,
            }
        ],
        "created_at": _timestamp(metadata.created_at),
    }
    if evaluation.recall_exclusions:
        payload["evaluated_universe"]["exclusion_reasons"] = [
            {
                "record_id": item.record_id,
                "reason_code": item.reason_code,
                "detail": item.detail,
            }
            for item in evaluation.recall_exclusions
        ]
    if decision_input.actor_conflict_resolutions:
        payload["actor_conflict_resolutions"] = [
            {
                "field": item.field,
                "fact_ids": list(item.fact_ids),
                "selected_fact_id": item.selected_fact_id,
                "selected_role": item.selected_role,
                "decided_by_role": item.decided_by_role,
                "strategy": item.strategy,
                "reason": item.reason,
            }
            for item in decision_input.actor_conflict_resolutions
        ]
    payload["decision_hash"] = content_hash(payload)
    return payload
