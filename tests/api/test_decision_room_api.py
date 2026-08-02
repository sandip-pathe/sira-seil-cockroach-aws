from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from jsonschema.validators import validator_for  # type: ignore[import-untyped]
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "contracts" / "jsonschema"


def frozen_validator(schema_name: str) -> Any:
    schemas: dict[str, dict[str, Any]] = {}
    for path in sorted(SCHEMAS.glob("*.json")):
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(loaded, dict)
        schemas[path.name] = loaded
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas.values()
    )
    schema = schemas[schema_name]
    return validator_for(schema)(schema, registry=registry)


def idempotency(value: str) -> dict[str, str]:
    return {"Idempotency-Key": value}


@pytest.mark.asyncio
async def test_decision_ledger_uses_the_frozen_graph_contract(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get("/v1/decisions/dec_consultco_v1")
    assert response.status_code == 200, response.text
    ledger = response.json()
    frozen_validator("decision-ledger.schema.json").validate(ledger)
    assert ledger["evaluated_universe"]["generated_solution_plan_count"] == 10
    assert len(ledger["solution_plans"]) == 10
    assert (
        ledger["selected_solution_plan_id"] == ledger["evaluation"]["ranked_solution_plan_ids"][0]
    )


@pytest.mark.asyncio
async def test_decision_room_is_action_neutral_and_role_filtered(
    api_client: httpx.AsyncClient,
) -> None:
    index = await api_client.get("/v1/decision-requests")
    assert index.status_code == 200, index.text
    assert [item["id"] for item in index.json()["active"]] == ["req_demo"]

    response = await api_client.get("/v1/decision-requests/req_demo/decision-view")
    assert response.status_code == 200, response.text
    view = response.json()
    frozen_validator("decision-view.schema.json").validate(view)
    assert "candidates" not in view
    assert view["workflow"]["current_stage"] == "OPTIONS"
    assert view["coverage"]["product_evidence_option_count"] == 4
    assert view["coverage"]["generated_solution_plan_count"] == 10
    assert view["rank_stability"]["status"] == "STABLE"
    assert len(view["solution_options"]) == 10
    assert view["solution_options"][0]["action_type"] == "REPLACE"
    assert view["solution_options"][0]["components"][0]["product_evidence_id"] == (
        "fixture_selected_fit"
    )
    assert {item["action_type"] for item in view["solution_options"]} == {
        "REPLACE",
        "RENEW",
        "RESIZE",
        "CONFIGURE_EXISTING",
        "REUSE_EXISTING",
        "CANCEL",
        "NO_ACTION",
    }
    selected = view["solution_options"][0]
    assert set(selected["preference_score"]["conservative"]) == {
        "numerator",
        "denominator",
        "display",
    }
    assert selected["total_cost"]["base"] == {"amount": "89.00", "currency": "USD"}
    assert view["selected_action_plan"] is None

    requester = await api_client.get(
        "/v1/decision-requests/req_demo/decision-view",
        headers={"X-Actor-Roles": "can_view_context", "X-Actor-Party": "BUYER"},
    )
    assert requester.status_code == 200, requester.text
    requester_view = requester.json()
    frozen_validator("decision-view.schema.json").validate(requester_view)
    assert requester_view["workflow"]["actor"]["role"] == "REQUESTER"
    assert requester_view["company_context"]["facts_used"] == []
    assert requester_view["company_context"]["hidden_fact_count"] > 0
    assert requester_view["workflow"]["available_actions"] == []


@pytest.mark.asyncio
async def test_seller_contract_requires_seller_identity_and_returns_public_fields(
    api_client: httpx.AsyncClient,
) -> None:
    buyer_denied = await api_client.get("/v1/seller/products/search?q=fixture")
    assert buyer_denied.status_code == 403, buyer_denied.text
    assert buyer_denied.json()["error"]["code"] == "SELLER_IDENTITY_REQUIRED"

    seller_view = await api_client.get(
        "/v1/seller/products/search?q=fixture",
        headers={
            "X-Actor-Id": "seller_fixture_d",
            "X-Actor-Party": "SELLER",
            "X-Actor-Roles": "seller_editor,can_view_context",
        },
    )
    assert seller_view.status_code == 200, seller_view.text
    assert {row["id"] for row in seller_view.json()["results"]} == {
        "product_fixture_d",
        "product_fixture_unclaimed",
    }
    assert "no production seller integration is implied" in seller_view.text.casefold()
    assert "buyer_passport" not in seller_view.text.casefold()


@pytest.mark.asyncio
async def test_plan_selection_and_action_run_bind_the_exact_decision(
    api_client: httpx.AsyncClient,
) -> None:
    before = (await api_client.get("/v1/decision-requests/req_demo/decision-view")).json()
    selected_option = before["solution_options"][0]
    selection_body = {
        "solution_plan_id": selected_option["id"],
        "decision_version": before["request"]["decision_version"],
        "decision_hash": before["evaluation"]["decision_hash"],
    }
    selected = await api_client.post(
        "/v1/decisions/dec_consultco_v1/plan-selections",
        headers=idempotency("select-plan-v2-0001"),
        json=selection_body,
    )
    assert selected.status_code == 201, selected.text
    selected_body = selected.json()
    assert selected_body["decision_version"] == 2
    assert selected_body["solution_plan_id"] == selected_option["id"]

    replay = await api_client.post(
        "/v1/decisions/dec_consultco_v1/plan-selections",
        headers=idempotency("select-plan-v2-0001"),
        json=selection_body,
    )
    assert replay.status_code == 201, replay.text
    assert replay.json() == selected_body

    stale = await api_client.post(
        "/v1/decisions/dec_consultco_v1/plan-selections",
        headers=idempotency("select-plan-v2-stale-0001"),
        json=selection_body,
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["error"]["code"] == "DECISION_SUPERSEDED"

    current = (await api_client.get("/v1/decision-requests/req_demo/decision-view")).json()
    frozen_validator("decision-view.schema.json").validate(current)
    assert current["request"]["decision_version"] == 2
    assert current["workflow"]["current_stage"] == "ACTION"
    assert current["selected_action_plan"]["id"] == selected_option["id"]
    assert current["payment"]["line_items"] == [
        {"type": "MERCHANT_SUBTOTAL", "amount": "87.00"},
        {
            "type": "SIRA_TRANSACTION_FEE",
            "amount": "2.00",
            "schedule_version": "buyer_txn_demo_v1",
        },
    ]

    run = await api_client.post(
        f"/v1/decisions/{selected_body['selected_decision_id']}/action-runs",
        headers=idempotency("action-run-v2-0001"),
        json={
            "solution_plan_id": selected_body["solution_plan_id"],
            "decision_version": selected_body["decision_version"],
            "decision_hash": selected_body["decision_hash"],
        },
    )
    assert run.status_code == 202, run.text
    run_body = run.json()
    assert set(run_body) == {
        "schema_version",
        "action_run_id",
        "workflow_id",
        "decision_id",
        "decision_version",
        "decision_hash",
        "selection_id",
        "solution_plan_id",
        "action_type",
        "status",
        "current_step_id",
        "last_successful_checkpoint_id",
        "owner_role",
        "blocking_task",
        "recovery_action",
        "execution_steps",
        "payment",
        "fulfillment",
        "result_artifacts",
        "created_at",
        "updated_at",
        "completed_at",
    }
    assert run_body["schema_version"] == "1.0.0"
    assert run_body["status"] == "WAITING_FOR_HUMAN"
    assert run_body["decision_version"] == selected_body["decision_version"]
    assert run_body["decision_hash"] == selected_body["decision_hash"]
    frozen_validator("action-run.schema.json").validate(run_body)
    restored = await api_client.get(f"/v1/action-runs/{run_body['action_run_id']}")
    assert restored.status_code == 200, restored.text
    assert restored.json() == run.json()


@pytest.mark.asyncio
async def test_zero_charge_selection_has_no_payment_or_fee(
    api_client: httpx.AsyncClient,
) -> None:
    before = (await api_client.get("/v1/decision-requests/req_demo/decision-view")).json()
    zero_charge_option = next(
        item for item in before["solution_options"] if item["action_type"] == "CONFIGURE_EXISTING"
    )
    selected = await api_client.post(
        "/v1/decisions/dec_consultco_v1/plan-selections",
        headers=idempotency("select-zero-charge-v2-0001"),
        json={
            "solution_plan_id": zero_charge_option["id"],
            "decision_version": before["request"]["decision_version"],
            "decision_hash": before["evaluation"]["decision_hash"],
        },
    )
    assert selected.status_code == 201, selected.text
    current = (await api_client.get("/v1/decision-requests/req_demo/decision-view")).json()
    frozen_validator("decision-view.schema.json").validate(current)
    assert current["selected_action_plan"]["action_type"] == "CONFIGURE_EXISTING"
    assert current["approval"]["status"] == "NOT_REQUIRED"
    assert current["payment"] == {
        "required": False,
        "status": "NOT_REQUIRED",
        "currency": None,
        "line_items": [],
        "landed_total": None,
        "purchase_intent_id": None,
        "last_checkpoint_at": None,
        "href": None,
    }
    assert current["fulfillment"] == {
        "required": False,
        "status": "NOT_REQUIRED",
        "expected_item_count": 0,
        "verified_item_count": 0,
        "partial_item_count": 0,
        "owner_role": None,
        "last_checkpoint_at": None,
        "href": None,
    }
