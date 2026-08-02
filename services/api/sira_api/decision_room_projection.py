"""Server-owned, role-filtered projection for the action-neutral Decision Room."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from domain.enums import ActorRole, UIActionCapability
from persistence.models import (
    ApprovalRequest,
    DecisionRecord,
    PurchaseIntent,
    PurchaseRequest,
    Receipt,
)

from .fixtures import (
    DEMO_FIXTURE_LABEL,
    DEMO_SCENARIO_ID,
    DemoFixtureBundle,
    content_hash,
)

_STATUS_MAP = {
    "ELIGIBLE": "SUPPORTED",
    "ELIGIBLE_WITH_EXCEPTION": "SUPPORTED_WITH_EXCEPTION",
    "CONDITIONAL": "NEEDS_CONDITION",
    "SIRA_INELIGIBLE": "BLOCKED_BY_COMPANY_REQUIREMENT",
    "SEIL_PASS": "VENDOR_NOT_SUPPORTED",
    "UNAVAILABLE": "UNAVAILABLE",
    "STALE_EVIDENCE": "NEEDS_EVIDENCE",
    "INSUFFICIENT_EVIDENCE": "NEEDS_EVIDENCE",
    "CONFLICTING_EVIDENCE": "EVIDENCE_CONFLICT",
    "AUTHORITY_REQUIRED": "AUTHORITY_REQUIRED",
    "ADVISORY_ONLY": "RESEARCH_ONLY",
}

_BLOCKED_OPTION_STATUSES = {
    "BLOCKED_BY_COMPANY_REQUIREMENT",
    "VENDOR_NOT_SUPPORTED",
    "UNAVAILABLE",
    "EVIDENCE_CONFLICT",
    "RESEARCH_ONLY",
}


def actor_role(roles: frozenset[str], party: str | None) -> ActorRole:
    if party == "SELLER":
        return ActorRole.SELLER_REVIEWER if "seller_reviewer" in roles else ActorRole.SELLER_EDITOR
    ordered = (
        ("platform_operator", ActorRole.PLATFORM_OPERATOR),
        ("auditor", ActorRole.AUDITOR),
        ("cardholder", ActorRole.CARDHOLDER),
        ("budget_owner", ActorRole.BUDGET_OWNER),
        ("procurement", ActorRole.PROCUREMENT),
        ("security_privacy_owner", ActorRole.POLICY_REVIEWER),
        ("legal_owner", ActorRole.POLICY_REVIEWER),
        ("operations_owner", ActorRole.DECISION_MAKER),
    )
    for marker, resolved in ordered:
        if marker in roles:
            return resolved
    if "can_select_recommendation" in roles:
        return ActorRole.DECISION_MAKER
    return ActorRole.REQUESTER


def actor_capabilities(roles: frozenset[str], resolved_role: ActorRole) -> list[str]:
    capabilities: set[UIActionCapability] = set()
    if "can_view_context" in roles:
        capabilities.add(UIActionCapability.VIEW_DECISION)
    if (
        resolved_role
        in {
            ActorRole.DECISION_MAKER,
            ActorRole.POLICY_REVIEWER,
            ActorRole.AUDITOR,
            ActorRole.PLATFORM_OPERATOR,
        }
        and "can_view_context" in roles
    ):
        capabilities.add(UIActionCapability.VIEW_PRIVATE_COMPANY_FACTS)
    if "can_submit_request" in roles:
        capabilities.add(UIActionCapability.EDIT_REQUEST)
    if "can_select_recommendation" in roles:
        capabilities.update(
            {
                UIActionCapability.KEEP_OPTION,
                UIActionCapability.ELIMINATE_OPTION,
                UIActionCapability.ASK_VENDOR,
                UIActionCapability.SAVE_OPTION,
                UIActionCapability.REQUEST_EVIDENCE,
                UIActionCapability.SELECT_PLAN,
            }
        )
    if "can_approve_purchase" in roles:
        capabilities.add(UIActionCapability.APPROVE_BUDGET)
    if "can_execute_purchase" in roles:
        capabilities.add(UIActionCapability.AUTHORIZE_PAYMENT)
    return sorted(item.value for item in capabilities)


def _exact(value: int, denominator: int = 1, *, display: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {"numerator": value, "denominator": denominator}
    if display:
        result["display"] = f"{Decimal(value) / Decimal(denominator):.2f}"
    return result


def _money(amount: str) -> dict[str, str]:
    return {"amount": amount, "currency": "USD"}


def _product_option(candidate: dict[str, Any]) -> dict[str, Any]:
    candidate_id = str(candidate["candidate_id"])
    status = _STATUS_MAP.get(str(candidate["status"]), "UNAVAILABLE")
    score = int(candidate.get("preference_score") or 0)
    risk = str(candidate.get("dependency_impact", {}).get("risk", "MEDIUM"))
    amount = str(candidate.get("total_cost", {}).get("amount", "0.00"))
    optimistic = score
    if status in {"SUPPORTED", "SUPPORTED_WITH_EXCEPTION", "NEEDS_EVIDENCE"}:
        optimistic = min(score + (6 if candidate_id == "fixture_selected_fit" else 4), 100)
    hard_constraints = candidate.get("hard_constraints", [])
    passed = sum(1 for item in hard_constraints if item.get("result") == "pass")
    total = max(len(hard_constraints), 1)
    executable = status not in _BLOCKED_OPTION_STATUSES and status != "NEEDS_CONDITION"
    return {
        "id": f"sol_replace_{candidate_id.removeprefix('fixture_')}",
        "action_type": "REPLACE",
        "label": f"Replace the incumbent with {candidate['name']}",
        "status": status,
        "reason_code": candidate.get("reason_code"),
        "reason": str(candidate["reason"]),
        "default_comparison": {
            "cost": {**_money(amount), "horizon_days": 30},
            "stack_change": "Replace the meeting-intelligence incumbent; retain dependencies",
            "next_action": "Review plan" if executable else "Review blocker",
        },
        "preference_score": {
            "conservative": _exact(score, display=True),
            "optimistic": _exact(optimistic, display=True),
        },
        "ordering_frontier_member": executable,
        "resolution_frontier_member": status
        in {
            "NEEDS_CONDITION",
            "NEEDS_EVIDENCE",
            "AUTHORITY_REQUIRED",
        },
        "quote_required": executable,
        "quote_policy_reason": "SELECTED_PLAN" if executable else "NOT_EXECUTABLE",
        "permitted_resolution": (
            "Obtain current seller evidence and rerun the frozen evaluation"
            if status in {"NEEDS_EVIDENCE", "RESEARCH_ONLY"}
            else None
        ),
        "stack_risk": {
            "base": risk,
            "lower": risk,
            "upper": "MEDIUM" if risk == "LOW" else "HIGH",
        },
        "total_cost": {
            "low": _money(amount),
            "base": _money(amount),
            "high": _money(
                f"{Decimal(amount) + (Decimal('20.00') if executable else Decimal('0.00')):.2f}"
            ),
        },
        "evidence_coverage": {
            "hard": _exact(passed, total),
            "decision_material": {
                "conservative": _exact(7 if executable else passed, 8 if executable else total),
                "optimistic": _exact(8 if executable else passed, 8 if executable else total),
            },
        },
        "maximum_evidence_age_ratio": {"lower": _exact(1, 90), "upper": _exact(2, 90)},
        "evidence_frontier": [],
        "components": [
            {
                "product_evidence_id": candidate_id,
                "current_instance_id": None,
                "action": "ADD",
                "publisher_authority": "SELLER_SEALED",
                "verification_summary": "Current frozen Product Evidence evaluated",
            }
        ],
        "merchant": (
            {
                "id": "merchant_fixture_d",
                "offer_id": "offer_fixture_d_monthly",
            }
            if candidate_id == "fixture_selected_fit"
            else None
        ),
        "evidence": [
            {
                "id": evidence_id,
                "label": "Decision-material Product Evidence",
                "publisher_authority": "SELLER_SEALED",
                "verification_state": "VERIFIED",
                "href": f"/v1/evidence/{evidence_id}",
            }
            for evidence_id in candidate.get("evidence_ids", [])
        ],
        "seller_positioning": candidate.get("seller_positioning"),
    }


def _current_stack_option(
    *,
    option_id: str,
    action_type: str,
    label: str,
    score: int,
    amount: str,
    status: str = "SUPPORTED",
    risk: str = "LOW",
    quote_required: bool = False,
) -> dict[str, Any]:
    executable = status in {"SUPPORTED", "SUPPORTED_WITH_EXCEPTION"}
    return {
        "id": option_id,
        "action_type": action_type,
        "label": label,
        "status": status,
        "reason_code": None,
        "reason": "Constructed from the frozen incumbent contract, usage, outcome, and Stack state",
        "default_comparison": {
            "cost": {**_money(amount), "horizon_days": 30},
            "stack_change": "Retain or change the current meeting-intelligence instance",
            "next_action": "Review plan" if executable else "Resolve dependency",
        },
        "preference_score": {
            "conservative": _exact(score, display=True),
            "optimistic": _exact(score, display=True),
        },
        "ordering_frontier_member": executable,
        "resolution_frontier_member": status == "NEEDS_CONDITION",
        "quote_required": quote_required,
        "quote_policy_reason": "RENEWAL_QUOTE" if quote_required else "NO_NEW_CHARGE",
        "permitted_resolution": (
            "Select and verify a dependency-safe exit plan" if status == "NEEDS_CONDITION" else None
        ),
        "stack_risk": {"base": risk, "lower": risk, "upper": risk},
        "total_cost": {"low": _money(amount), "base": _money(amount), "high": _money(amount)},
        "evidence_coverage": {
            "hard": _exact(1, 1),
            "decision_material": {
                "conservative": _exact(3, 4),
                "optimistic": _exact(3, 4),
            },
        },
        "maximum_evidence_age_ratio": {"lower": _exact(10, 90), "upper": _exact(10, 90)},
        "evidence_frontier": [],
        "components": [
            {
                "product_evidence_id": None,
                "current_instance_id": "instance_incumbent",
                "action": {
                    "CONFIGURE_EXISTING": "CONFIGURE",
                    "REUSE_EXISTING": "REUSE",
                    "RENEW": "RENEW",
                    "RESIZE": "RESIZE",
                    "CANCEL": "CANCEL",
                    "NO_ACTION": "RETAIN",
                }[action_type],
                "publisher_authority": None,
                "verification_summary": (
                    "Frozen current Stack, contract, usage, and outcome evidence"
                ),
            }
        ],
        "merchant": None,
        "evidence": [],
        "seller_positioning": None,
    }


def _verification_state(state: str) -> str:
    return {
        "ACCEPTABLE": "VERIFIED",
        "UNKNOWN": "INSUFFICIENT",
        "STALE": "STALE",
        "CONFLICT": "CONFLICTING",
    }.get(state, "INSUFFICIENT")


def _ledger_solution_option(
    plan: dict[str, Any], component_results: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    components = list(plan.get("components", []))
    product_component = next(
        (item for item in components if item.get("source_type") == "PRODUCT_EVIDENCE"),
        None,
    )
    component_result = (
        component_results.get(str(product_component.get("component_id")))
        if product_component is not None
        else None
    )
    action_type = str(plan["action_type"])
    status = _STATUS_MAP.get(str(plan["status"]), "UNAVAILABLE")
    dimensions = dict(plan["dimensions"])
    base_cost = dict(dimensions["total_cost"]["base"])
    if "amount" not in base_cost:
        base_cost = _money("0.00")
    primary_reason = plan.get("primary_reason")
    reason_code = str(primary_reason["reason_code"]) if isinstance(primary_reason, dict) else None
    reason = (
        str(primary_reason["detail"])
        if isinstance(primary_reason, dict)
        else "Meets the frozen Decision rules and supported evidence bounds"
    )
    executable = status in {"SUPPORTED", "SUPPORTED_WITH_EXCEPTION"}
    if component_result is not None:
        name = str(component_result["name"])
        label = f"Replace the incumbent with {name}"
        stack_change = "Replace the meeting-intelligence incumbent; retain dependencies"
    else:
        label = {
            "RENEW": "Renew the incumbent contract",
            "RESIZE": "Resize the incumbent to observed usage",
            "CONFIGURE_EXISTING": "Configure the incumbent for the required workflow",
            "REUSE_EXISTING": "Reuse the incumbent without a new purchase",
            "CANCEL": "Cancel the incumbent contract",
            "NO_ACTION": "Take no action and set the next review",
        }.get(action_type, f"Review {action_type.casefold().replace('_', ' ')}")
        stack_change = "Retain or change the current meeting-intelligence instance"

    evidence: list[dict[str, Any]] = []
    if component_result is not None:
        seen_evidence: set[str] = set()
        for assessment in component_result.get("evidence_assessments", []):
            evidence_id = str(assessment["evidence_id"])
            if evidence_id in seen_evidence:
                continue
            seen_evidence.add(evidence_id)
            evidence.append(
                {
                    "id": evidence_id,
                    "label": "Decision-material Product Evidence",
                    "publisher_authority": component_result["publisher_authority"],
                    "verification_state": _verification_state(str(assessment["state"])),
                    "href": f"/v1/evidence/{evidence_id}",
                }
            )

    projected_components: list[dict[str, Any]] = []
    for component in components:
        if component.get("source_type") == "PRODUCT_EVIDENCE":
            result = component_results.get(str(component["component_id"]))
            projected_components.append(
                {
                    "product_evidence_id": (
                        str(result["pack_id"])
                        if result is not None and result.get("pack_id") is not None
                        else str(component["source_id"])
                    ),
                    "current_instance_id": None,
                    "action": "ADD",
                    "publisher_authority": (
                        result.get("publisher_authority") if result is not None else None
                    ),
                    "verification_summary": (
                        "Frozen Product Evidence evaluated by the Decision Graph"
                    ),
                }
            )
        else:
            projected_components.append(
                {
                    "product_evidence_id": None,
                    "current_instance_id": str(component["source_id"]),
                    "action": {
                        "CONFIGURE_EXISTING": "CONFIGURE",
                        "REUSE_EXISTING": "REUSE",
                        "NO_ACTION": "RETAIN",
                        "RENEW": "RENEW",
                        "RESIZE": "RESIZE",
                        "CANCEL": "CANCEL",
                    }[str(component["action_type"])],
                    "publisher_authority": None,
                    "verification_summary": (
                        "Frozen current Stack, contract, usage, and outcome evidence"
                    ),
                }
            )

    return {
        "id": plan["solution_plan_id"],
        "action_type": action_type,
        "label": label,
        "status": status,
        "reason_code": reason_code,
        "reason": reason,
        "default_comparison": {
            "cost": {**base_cost, "horizon_days": 30},
            "stack_change": stack_change,
            "next_action": "Review plan" if executable else "Review blocker",
        },
        "preference_score": dimensions["preference"],
        "ordering_frontier_member": bool(plan["ordering_frontier_member"]),
        "resolution_frontier_member": bool(plan["resolution_frontier_member"]),
        "quote_required": bool(plan["quote_required"]),
        "quote_policy_reason": str(plan["quote_policy_reason"]),
        "permitted_resolution": plan.get("permitted_resolution"),
        "stack_risk": dimensions["stack_risk"],
        "total_cost": dimensions["total_cost"],
        "evidence_coverage": {
            "hard": dimensions["hard_coverage"],
            "decision_material": dimensions["decision_material_coverage"],
        },
        "maximum_evidence_age_ratio": dimensions["maximum_evidence_age_ratio"],
        "evidence_frontier": [],
        "components": projected_components,
        "merchant": (
            {"id": "merchant_fixture_d", "offer_id": "offer_fixture_d_monthly"}
            if component_result is not None
            and component_result.get("pack_id") == "fixture_selected_fit"
            else None
        ),
        "evidence": evidence,
        "seller_positioning": None,
        "_rank": plan.get("rank"),
    }


def solution_options(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    ledger_plans = ledger.get("solution_plans", [])
    if ledger_plans and isinstance(ledger_plans[0], dict) and "dimensions" in ledger_plans[0]:
        component_results = {
            str(item["component_id"]): item for item in ledger.get("component_results", [])
        }
        projected = [_ledger_solution_option(plan, component_results) for plan in ledger_plans]
        projected.sort(
            key=lambda item: (
                item["_rank"] is None,
                int(item["_rank"] or 0),
                item["id"],
            )
        )
        for item in projected:
            item.pop("_rank", None)
        return projected

    product_options = [_product_option(item) for item in ledger.get("candidate_results", [])]
    incumbent_options = [
        _current_stack_option(
            option_id="sol_renew_incumbent",
            action_type="RENEW",
            label="Renew the incumbent contract",
            score=74,
            amount="119.00",
            quote_required=True,
        ),
        _current_stack_option(
            option_id="sol_resize_incumbent",
            action_type="RESIZE",
            label="Resize the incumbent to observed usage",
            score=70,
            amount="89.00",
            quote_required=True,
        ),
        _current_stack_option(
            option_id="sol_configure_incumbent",
            action_type="CONFIGURE_EXISTING",
            label="Configure the incumbent for the required workflow",
            score=65,
            amount="0.00",
        ),
        _current_stack_option(
            option_id="sol_reuse_incumbent",
            action_type="REUSE_EXISTING",
            label="Reuse the incumbent without a new purchase",
            score=58,
            amount="0.00",
        ),
        _current_stack_option(
            option_id="sol_cancel_incumbent",
            action_type="CANCEL",
            label="Cancel the incumbent contract",
            score=55,
            amount="0.00",
            status="NEEDS_CONDITION",
            risk="MEDIUM",
        ),
        _current_stack_option(
            option_id="sol_no_action_incumbent",
            action_type="NO_ACTION",
            label="Take no action and set the next review",
            score=40,
            amount="0.00",
            status="NEEDS_CONDITION",
        ),
    ]
    return sorted(
        [*product_options, *incumbent_options],
        key=lambda item: (
            item["status"] not in {"SUPPORTED", "SUPPORTED_WITH_EXCEPTION"},
            -int(item["preference_score"]["conservative"]["numerator"]),
            item["id"],
        ),
    )


def _selected_plan(
    decision: DecisionRecord, options: list[dict[str, Any]], resolved_role: ActorRole
) -> dict[str, Any] | None:
    selection = decision.payload.get("selection")
    if not isinstance(selection, dict):
        return None
    selected = next(
        (item for item in options if item["id"] == selection.get("solution_plan_id")), None
    )
    if selected is None:
        return None
    charged = selected["action_type"] in {"BUY", "REPLACE", "RENEW", "RESIZE"}
    steps = [
        {
            "id": "step_review",
            "type": "REVIEW",
            "status": "AVAILABLE",
            "owner_role": "DECISION_MAKER",
            "started_at": None,
            "completed_at": None,
            "checkpoint_id": None,
            "artifact_id": None,
            "blocker": None,
            "available_action": {
                "id": "START_REVIEW",
                "label": "Review action plan",
                "method": "POST",
                "href": f"/v1/decisions/{decision.id}/action-runs",
                "requires_confirmation": False,
                "expires_at": None,
            },
        },
        {
            "id": "step_authority",
            "type": "REQUIRED_AUTHORITY",
            "status": "NOT_REACHED",
            "owner_role": "BUDGET_OWNER" if charged else "IT_OPERATIONS",
            "started_at": None,
            "completed_at": None,
            "checkpoint_id": None,
            "artifact_id": None,
            "blocker": None,
            "available_action": None,
        },
        {
            "id": "step_execute",
            "type": "EXECUTE_OR_ASSIGN",
            "status": "NOT_REACHED",
            "owner_role": "CARDHOLDER" if charged else "IT_OPERATIONS",
            "started_at": None,
            "completed_at": None,
            "checkpoint_id": None,
            "artifact_id": None,
            "blocker": None,
            "available_action": None,
        },
        {
            "id": "step_verify",
            "type": "VERIFY",
            "status": "NOT_REACHED",
            "owner_role": "IT_OPERATIONS",
            "started_at": None,
            "completed_at": None,
            "checkpoint_id": None,
            "artifact_id": None,
            "blocker": None,
            "available_action": None,
        },
    ]
    return {
        "id": selected["id"],
        "action_type": selected["action_type"],
        "state": "SELECTED",
        "selected_at": selection["selected_at"],
        "selected_by_role": selection.get("selected_by_role", resolved_role.value),
        "selection_id": selection["selection_id"],
        "decision_version": decision.version,
        "decision_hash": decision.decision_hash,
        "execution_steps": steps,
        "href": f"/v1/decisions/{decision.id}/solution-plans/{selected['id']}",
    }


def _company_context(fixtures: DemoFixtureBundle, capabilities: list[str]) -> dict[str, Any]:
    facts = fixtures.buyer_passport.get("facts", [])
    may_view = UIActionCapability.VIEW_PRIVATE_COMPANY_FACTS.value in capabilities
    visible = []
    if may_view:
        for fact in facts:
            value = fact.get("value")
            visible.append(
                {
                    "fact_id": fact["fact_id"],
                    "display_name": str(fact["field"]).replace("_", " "),
                    "display_value": (
                        ", ".join(map(str, value)) if isinstance(value, list) else str(value)
                    ),
                    "provenance_label": str(fact["source"]["provider"]),
                    "sensitivity": fact.get("sensitivity", "internal"),
                }
            )
    return {
        "facts_used": visible,
        "hidden_fact_count": len(facts) - len(visible),
        "company_profile_version": int(fixtures.buyer_passport["version"]),
        "company_stack_snapshot": 1,
    }


def project_decision_room(
    *,
    request: PurchaseRequest,
    decision: DecisionRecord,
    fixtures: DemoFixtureBundle,
    roles: frozenset[str],
    party: str | None,
    intent: PurchaseIntent | None,
    approval: ApprovalRequest | None,
    receipt: Receipt | None,
    superseded_by: DecisionRecord | None,
) -> dict[str, Any]:
    ledger = deepcopy(decision.payload["ledger"])
    options = solution_options(ledger)
    resolved_role = actor_role(roles, party)
    capabilities = actor_capabilities(roles, resolved_role)
    selected = _selected_plan(decision, options, resolved_role)
    stage = "ACTION" if selected is not None else "OPTIONS"
    is_current = superseded_by is None
    available_actions: list[dict[str, Any]] = []
    if is_current and selected is None and UIActionCapability.SELECT_PLAN.value in capabilities:
        available_actions.append(
            {
                "id": "SELECT_PLAN",
                "label": "Select action plan",
                "method": "POST",
                "href": f"/v1/decisions/{decision.id}/plan-selections",
                "requires_confirmation": True,
                "expires_at": None,
            }
        )
    evaluation_payload = {
        key: value
        for key, value in ledger.items()
        if key not in {"decision_id", "decision_hash", "created_at"}
    }
    evaluation_hash = str(
        decision.payload.get("evaluation_payload_hash")
        or ledger.get("evaluation", {}).get("evaluation_payload_hash")
        or content_hash(evaluation_payload)
    )
    evaluated_universe = ledger.get("evaluated_universe", {})
    ledger_rank_stability = ledger.get("rank_stability", {})
    frozen_versions = ledger.get("evaluation", {}).get("frozen_versions", {})
    created_at = decision.created_at.astimezone(UTC).isoformat()
    stage_history = [
        {
            "stage": name,
            "status": (
                "CURRENT"
                if name == stage
                else "COMPLETED"
                if name in {"NEED", "COMPANY_FIT", "OPTIONS"} and stage == "ACTION"
                else "COMPLETED"
                if name in {"NEED", "COMPANY_FIT"}
                else "NOT_STARTED"
            ),
            "checkpoint_id": f"cp_{name.lower()}_v{decision.version}",
            "completed_at": created_at if name in {"NEED", "COMPANY_FIT"} else None,
            "href": (
                f"/decisions/{request.id}/versions/{decision.version}/"
                f"{name.lower().replace('_', '-')}"
            ),
        }
        for name in ("NEED", "COMPANY_FIT", "OPTIONS", "ACTION", "RESULT")
    ]
    charged = selected is not None and selected["action_type"] in {
        "BUY",
        "REPLACE",
        "RENEW",
        "RESIZE",
    }
    approval_projection = None
    payment_projection = None
    fulfillment_projection = None
    if selected is not None:
        approval_projection = {
            "required": charged,
            "status": (
                intent.approval_status
                if intent is not None
                else "NOT_REQUESTED"
                if charged
                else "NOT_REQUIRED"
            ),
            "requirement_set_id": "aprs_consultco_v1" if charged else None,
            "owner_roles": (
                ["DECISION_MAKER", "POLICY_REVIEWER", "BUDGET_OWNER"] if charged else []
            ),
            "completed_count": len(approval.approved_roles) if approval is not None else 0,
            "required_count": len(approval.required_roles)
            if approval is not None
            else (4 if charged else 0),
            "rejected_by_role": None,
            "expires_at": approval.expires_at.isoformat() if approval is not None else None,
            "href": f"/v1/decisions/{decision.id}/approval" if charged else None,
        }
        if charged:
            payment_projection = {
                "required": True,
                "status": intent.payment_status if intent is not None else "NOT_STARTED",
                "currency": "USD",
                "line_items": [
                    {"type": "MERCHANT_SUBTOTAL", "amount": "87.00"},
                    {
                        "type": "SIRA_TRANSACTION_FEE",
                        "amount": "2.00",
                        "schedule_version": "buyer_txn_demo_v1",
                    },
                ],
                "landed_total": "89.00",
                "purchase_intent_id": intent.id if intent is not None else None,
                "last_checkpoint_at": None,
                "href": (
                    f"/v1/purchase-intents/{intent.id}/status" if intent is not None else None
                ),
            }
            fulfillment_projection = {
                "required": True,
                "status": intent.fulfillment_status if intent is not None else "NOT_STARTED",
                "expected_item_count": 2,
                "verified_item_count": 2
                if intent and intent.fulfillment_status == "VERIFIED"
                else 0,
                "partial_item_count": 0,
                "owner_role": None,
                "last_checkpoint_at": None,
                "href": (
                    f"/v1/purchase-intents/{intent.id}/status" if intent is not None else None
                ),
            }
        else:
            payment_projection = {
                "required": False,
                "status": "NOT_REQUIRED",
                "currency": None,
                "line_items": [],
                "landed_total": None,
                "purchase_intent_id": None,
                "last_checkpoint_at": None,
                "href": None,
            }
            fulfillment_projection = {
                "required": False,
                "status": "NOT_REQUIRED",
                "expected_item_count": 0,
                "verified_item_count": 0,
                "partial_item_count": 0,
                "owner_role": None,
                "last_checkpoint_at": None,
                "href": None,
            }
    receipt_projection = (
        deepcopy(receipt.payload) if receipt is not None and intent is not None else None
    )
    return {
        "request": {
            "id": request.id,
            "intent": request.intent,
            "status": request.status,
            "decision_version": decision.version,
            "decision_state": "CURRENT" if is_current else "SUPERSEDED",
            "superseded_by": superseded_by.id if superseded_by is not None else None,
            "evaluation_mode": request.payload.get("evaluation_mode", DEMO_FIXTURE_LABEL),
            "scenario_id": request.payload.get("scenario_id", DEMO_SCENARIO_ID),
            "fixture_label": request.payload.get("fixture_label", DEMO_FIXTURE_LABEL),
        },
        "workflow": {
            "current_stage": stage,
            "actor": {"role": resolved_role.value, "capabilities": capabilities},
            "available_actions": available_actions,
            "blocking_tasks": [],
            "active_operation": None,
            "stage_history": stage_history,
            "version_links": {
                "current": f"/decisions/{request.id}/versions/{decision.version}/{stage.lower()}",
                "previous": (
                    f"/decisions/{request.id}/versions/{decision.version - 1}/{stage.lower()}"
                    if decision.version > 1
                    else None
                ),
                "superseded_by": (
                    f"/decisions/{request.id}/versions/{superseded_by.version}/{stage.lower()}"
                    if superseded_by is not None
                    else None
                ),
            },
        },
        "evaluation": {
            "id": f"eval_{decision.id}",
            "payload_hash": evaluation_hash,
            "decision_hash": decision.decision_hash,
            "pipeline_version": frozen_versions.get("pipeline", "decision_graph_v1"),
            "engine_version": frozen_versions.get("engine", "engine_v1"),
        },
        "company_context": _company_context(fixtures, capabilities),
        "coverage": {
            "raw_record_count": evaluated_universe.get("raw_record_count", 4),
            "product_evidence_option_count": evaluated_universe.get(
                "product_evidence_option_count", 4
            ),
            "canonical_product_count": evaluated_universe.get("canonical_product_count", 4),
            "duplicate_count": evaluated_universe.get("duplicate_count", 0),
            "generated_solution_plan_count": evaluated_universe.get(
                "generated_solution_plan_count", len(options)
            ),
            "evaluated_solution_plan_count": evaluated_universe.get(
                "evaluated_solution_plan_count", len(options)
            ),
            "excluded_count": evaluated_universe.get("excluded_count", 0),
            "statement": evaluated_universe.get(
                "coverage_statement",
                "Best supported action among four products and six current-stack/contract actions",
            ),
        },
        "decision_outcome": ledger.get("decision_outcome", "SELECTED_SOLUTION_PLAN"),
        "rank_stability": {
            "status": ledger_rank_stability.get("status", "STABLE"),
            "summary": ledger_rank_stability.get(
                "summary",
                "The recommended action stays first across the supported uncertainty ranges",
            ),
            "evidence_frontier": ledger_rank_stability.get("evidence_frontier", []),
        },
        "solution_options": options,
        "selected_action_plan": selected,
        "stack_change": (
            {
                "id": "sp_demo_v1",
                "status": "PROPOSED",
                "summary": "Replace the incumbent and retain required dependencies",
                "added": ["product_fixture_d"],
                "removed": [],
                "staged_for_removal": ["instance_incumbent"],
                "retained": ["slack", "google_workspace"],
                "dependency_changed": ["meeting_capture"],
                "href": "/v1/stack-patches/patch_consultco_fixture_d",
            }
            if selected is not None
            else None
        ),
        "approval": approval_projection,
        "payment": payment_projection,
        "fulfillment": fulfillment_projection,
        "result_artifacts": [],
        "receipt": receipt_projection,
    }


def selection_payload(
    *,
    source: DecisionRecord,
    solution_plan_id: str,
    selected_by_role: ActorRole,
    selection_id: str,
    selected_at: datetime | None = None,
) -> dict[str, Any]:
    timestamp = (selected_at or datetime.now(UTC)).astimezone(UTC).isoformat()
    return {
        "selection_id": selection_id,
        "source_decision_id": source.id,
        "source_decision_version": source.version,
        "source_decision_hash": source.decision_hash,
        "solution_plan_id": solution_plan_id,
        "selected_by_role": selected_by_role.value,
        "selected_at": timestamp,
    }
