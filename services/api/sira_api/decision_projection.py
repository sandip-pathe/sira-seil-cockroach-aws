"""Deterministic projections for a versioned demo Purchase Brief decision."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from decision_engine import evaluate_demo, rank_solution_plans
from domain.enums import CandidateStatus

from .fixtures import DEMO, DemoFixtureBundle, content_hash

_RANKABLE = frozenset({CandidateStatus.ELIGIBLE, CandidateStatus.ELIGIBLE_WITH_EXCEPTION})


@dataclass(frozen=True, slots=True)
class DemoDecisionProjection:
    ledger: dict[str, Any]
    decision_view: dict[str, Any]
    stack_patch: dict[str, Any]


def _display_score(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def build_demo_decision_projection(
    *,
    fixtures: DemoFixtureBundle,
    purchase_brief: dict[str, Any],
    requirement_brief: dict[str, Any],
    request_id: str,
    decision_id: str,
    created_at: datetime | None = None,
) -> DemoDecisionProjection:
    """Re-evaluate one accepted brief version and build its immutable API artifacts."""

    timestamp = (created_at or datetime.now(UTC)).astimezone(UTC)
    timestamp_text = timestamp.isoformat().replace("+00:00", "Z")
    evaluation = evaluate_demo(
        DEMO,
        purchase_brief_override=purchase_brief,
        requirement_brief_override=requirement_brief,
    )
    ranked = rank_solution_plans(evaluation.company_aware_plans)
    if not ranked:
        raise ValueError("an accepted demo Purchase Brief produced no executable solution plan")

    result_by_id = {item.candidate_id: item for item in evaluation.candidate_results}
    plan_by_candidate = {item.component_ids[0]: item for item in evaluation.company_aware_plans}

    ledger = deepcopy(fixtures.decision_ledger())
    ledger.update(
        {
            "decision_id": decision_id,
            "request_id": request_id,
            "purchase_brief_id": purchase_brief["purchase_brief_id"],
            "purchase_brief_version": purchase_brief["version"],
            "requirement_brief_id": requirement_brief["requirement_brief_id"],
            "requirement_brief_version": requirement_brief["version"],
            "created_at": timestamp_text,
        }
    )

    candidate_rows = ledger.get("candidate_results")
    if not isinstance(candidate_rows, list):
        raise ValueError("demo ledger candidate results are invalid")
    for row in candidate_rows:
        candidate_id = str(row["candidate_id"])
        result = result_by_id[candidate_id]
        plan = plan_by_candidate[candidate_id]
        row["status"] = result.status.value
        row["reason_code"] = result.reason_code
        row["reason"] = result.reason
        row["seller_positioning"] = result.seller_positioning
        if result.status not in _RANKABLE:
            row["preference_scores"] = []
            row["preference_score"] = None
            continue
        existing_evidence = {
            str(item["id"]): list(item.get("evidence_ids", []))
            for item in row.get("preference_scores", [])
            if isinstance(item, dict) and "id" in item
        }
        row["preference_scores"] = [
            {
                "id": item.criterion_id,
                "weight": item.weight,
                "satisfaction": str(item.satisfaction),
                "contribution": str(item.contribution),
                "evidence_ids": existing_evidence.get(item.criterion_id, []),
            }
            for item in result.preference_results
        ]
        row["preference_score"] = _display_score(plan.preference_score)

    plan_templates = {
        str(row["component_candidate_ids"][0]): row
        for row in ledger.get("solution_plans", [])
        if isinstance(row, dict) and row.get("component_candidate_ids")
    }
    ranked_rows: list[dict[str, Any]] = []
    for rank, plan in enumerate(ranked, start=1):
        candidate_id = plan.component_ids[0]
        template = plan_templates.get(candidate_id)
        if template is None:
            raise ValueError(f"demo Stackfile patch template is missing for {candidate_id}")
        projected = deepcopy(template)
        projected.update(
            {
                "status": plan.status.value,
                "preference_score": _display_score(plan.preference_score),
                "stack_risk": plan.stack_risk.value,
                "total_cost": plan.total_cost.to_dict(),
                "rank": rank,
            }
        )
        ranked_rows.append(projected)
    ledger["solution_plans"] = ranked_rows
    selected_row = ranked_rows[0]
    ledger["selected_solution_plan_id"] = selected_row["solution_plan_id"]

    selected_candidate_id = ranked[0].component_ids[0]
    if selected_candidate_id != evaluation.selected_plan.component_ids[0]:
        raise ValueError("demo ranking projection disagrees with the decision engine")
    counterfactual = deepcopy(ledger["counterfactual"])
    counterfactual["generic_selected_candidate_id"] = evaluation.generic_winner.component_ids[0]
    counterfactual["company_aware_selected_candidate_id"] = selected_candidate_id
    ledger["counterfactual"] = counterfactual

    stack_patch = deepcopy(fixtures.stack_patch())
    if stack_patch.get("solution_plan_id") != selected_row["solution_plan_id"]:
        raise ValueError("the selected demo plan has no complete Stackfile patch fixture")
    stack_patch.update(
        {
            "patch_id": f"patch_{decision_id}",
            "decision_id": decision_id,
            "created_at": timestamp_text,
        }
    )
    stack_patch["content_hash"] = content_hash(
        {key: value for key, value in stack_patch.items() if key != "content_hash"}
    )
    selected_row["stack_patch_id"] = stack_patch["patch_id"]

    ledger["decision_hash"] = content_hash(
        {key: value for key, value in ledger.items() if key != "decision_hash"}
    )

    decision_view = deepcopy(fixtures.decision_view())
    decision_view["request"]["id"] = request_id
    view_candidates = {
        str(row["id"]): row for row in decision_view.get("candidates", []) if isinstance(row, dict)
    }
    for row in candidate_rows:
        view_row = view_candidates[str(row["candidate_id"])]
        view_row.update(
            {
                "status": row["status"],
                "reason_code": row["reason_code"],
                "reason": row["reason"],
                "preference_score": row["preference_score"],
                "seller_positioning": row["seller_positioning"],
            }
        )
    decision_view["selected_solution_plan"] = deepcopy(selected_row)
    decision_view["counterfactual"] = deepcopy(counterfactual)
    decision_view["stack_patch"] = deepcopy(stack_patch)
    return DemoDecisionProjection(
        ledger=ledger,
        decision_view=decision_view,
        stack_patch=stack_patch,
    )
