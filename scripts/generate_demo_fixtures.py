"""Regenerate hash-linked deterministic demo artifacts from the Decision Graph."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
sys.path.insert(0, str(ROOT / "services" / "api"))

from sira_api.decision_room_projection import project_decision_room  # noqa: E402
from sira_api.fixtures import DemoFixtureBundle  # noqa: E402
from sira_api.graph_ledger import (  # noqa: E402
    DecisionLedgerMetadata,
    build_decision_ledger,
)

from decision_engine import evaluate_decision_graph, load_demo_decision_graph_input  # noqa: E402
from domain.hashing import content_hash  # noqa: E402
from persistence.models import DecisionRecord, PurchaseRequest  # noqa: E402

DEMO = ROOT / "fixtures" / "demo"


def _load(name: str) -> dict[str, Any]:
    value = json.loads((DEMO / name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{name} must contain a JSON object")
    return value


def _write(name: str, value: dict[str, Any]) -> None:
    (DEMO / name).write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    graph_input = load_demo_decision_graph_input(DEMO)
    graph_input = replace(
        graph_input,
        versions=replace(graph_input.versions, request_version="pb_consultco_v1:v1"),
    )
    decision = evaluate_decision_graph(
        graph_input,
        evaluation_id="eval_dec_consultco_v1",
        generated_at=datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
    )
    component_names = {
        path.stem: str(_load(f"packs/{path.name}")["identity"]["product_name"])
        for path in sorted((DEMO / "packs").glob("*.json"))
    }
    ledger = build_decision_ledger(
        decision,
        graph_input,
        DecisionLedgerMetadata(
            decision_id="dec_consultco_v1",
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
        component_names=component_names,
    )
    _write("expected_decision_ledger.json", ledger)
    selected_plan_id = str(ledger["selected_solution_plan_id"])

    fixture_bundle = DemoFixtureBundle.load()
    fixture_time = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
    request = PurchaseRequest(
        id="req_demo",
        organization_id="org_consultco",
        intent="Find meeting intelligence for ten consultants",
        status="DECISION_READY",
        visibility="SELECTIVE",
        version=1,
        payload={"fixture_label": "DEVELOPMENT_FIXTURE_NON_PRODUCTION"},
        request_hash=content_hash({"request_id": "req_demo", "version": 1}),
        created_at=fixture_time,
        updated_at=fixture_time,
    )
    decision_record = DecisionRecord(
        id="dec_consultco_v1",
        organization_id="org_consultco",
        purchase_request_id="req_demo",
        purchase_brief_id="pb_consultco_v1",
        version=1,
        supersedes_id=None,
        decision_hash=ledger["decision_hash"],
        selected_solution_plan_id=selected_plan_id,
        payload={"ledger": ledger},
        created_at=fixture_time,
        updated_at=fixture_time,
    )
    decision_view = project_decision_room(
        request=request,
        decision=decision_record,
        fixtures=fixture_bundle,
        roles=frozenset({"can_view_context", "can_select_recommendation"}),
        party="BUYER",
        intent=None,
        approval=None,
        handoff=None,
        superseded_by=None,
    )
    _write("expected_decision_view.json", decision_view)

    stack_patch = _load("expected_stack_patch.json")
    stack_patch["solution_plan_id"] = selected_plan_id
    stack_patch["content_hash"] = content_hash(stack_patch, excluded_fields=("content_hash",))
    _write("expected_stack_patch.json", stack_patch)

    purchase_intent = _load("expected_purchase_intent.json")
    purchase_intent.update(
        {
            "decision_hash": ledger["decision_hash"],
            "solution_plan_id": selected_plan_id,
            "stack_patch_id": stack_patch["patch_id"],
        }
    )
    purchase_intent["intent_hash"] = content_hash(purchase_intent, excluded_fields=("intent_hash",))
    _write("expected_purchase_intent.json", purchase_intent)

    approval = _load("expected_approval.json")
    approval["intent_hash"] = purchase_intent["intent_hash"]
    approval["exact_summary"] = {
        "decision_version": purchase_intent["decision_version"],
        "decision_hash": ledger["decision_hash"],
        "selection_id": purchase_intent["selection_id"],
        "solution_plan_id": selected_plan_id,
        "merchant_id": purchase_intent["merchant"]["merchant_id"],
        "line_items": purchase_intent["line_items"],
        "merchant_subtotal": purchase_intent["merchant_subtotal"],
        "buyer_transaction_fee": purchase_intent["fee_amount"],
        "fee_schedule_version": purchase_intent["fee_schedule_version"],
        "tax_amount": purchase_intent["tax_amount"],
        "landed_total": purchase_intent["landed_total"],
        "currency": purchase_intent["currency"],
        "quote_id": purchase_intent["quote_id"],
        "quote_version": purchase_intent["quote_version"],
        "pack_id": purchase_intent["pack_id"],
        "pack_version": purchase_intent["pack_version"],
        "offer_id": purchase_intent["offer_id"],
        "offer_version": purchase_intent["offer_version"],
        "expected_fulfillment_ids": [
            item["fulfillment_item_id"] for item in purchase_intent["expected_fulfillments"]
        ],
    }
    for stage in approval["stages"]:
        stage["approved_intent_hash"] = purchase_intent["intent_hash"]
    _write("expected_approval.json", approval)

    engagement = _load("expected_selective_engagement.json")
    engagement.pop("request_id", None)
    engagement.pop("candidate_id", None)
    engagement.update(
        {
            "decision_request_id": "req_demo",
            "decision_version": 1,
            "solution_plan_id": selected_plan_id,
            "action": "ASK_VENDOR",
            "requirement_brief_version": 1,
        }
    )
    _write("expected_selective_engagement.json", engagement)
    sys.stdout.write("Regenerated graph-linked demo fixtures\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
