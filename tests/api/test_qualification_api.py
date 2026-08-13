from __future__ import annotations

import httpx
import pytest


def _mission_body() -> dict[str, object]:
    return {
        "buyer_context": {
            "company": "Northstar Labs",
            "budget": "25000",
            "incumbent": "Manual research",
        },
        "requirement_brief": {
            "category": "meeting intelligence",
            "goal": "Select an EU-hosted meeting intelligence platform for sales.",
            "seller_visible_requirements": {
                "hosting_region": "EU",
                "seat_count": 40,
            },
            "criteria": [
                {
                    "id": "eu_hosting",
                    "label": "EU hosting",
                    "requirement": "Customer data remains in the EU.",
                    "priority": "MUST",
                }
            ],
        },
        "procurement_policy": {
            "human_approval": True,
            "maximum_annual_cost": "25000",
        },
    }


@pytest.mark.asyncio
async def test_qualification_mission_contract_and_idempotency(
    api_client: httpx.AsyncClient,
) -> None:
    headers = {"Idempotency-Key": "qualification-create-1"}
    first = await api_client.post(
        "/v1/qualification/missions", headers=headers, json=_mission_body()
    )
    replay = await api_client.post(
        "/v1/qualification/missions", headers=headers, json=_mission_body()
    )

    assert first.status_code == replay.status_code == 201
    assert replay.json()["resource_id"] == first.json()["resource_id"]
    assert replay.json()["replayed"] is True
    assert first.headers["location"].endswith(first.json()["resource_id"])

    mission = await api_client.get(first.headers["location"])
    assert mission.status_code == 200
    payload = mission.json()
    assert payload["mission"]["state"] == "READY"
    assert payload["mission"]["buyer_context"]["company"] == "Northstar Labs"
    assert payload["attempts"] == []
    assert payload["decision"] is None
    assert payload["integrity"]["verdict"] == "PENDING"

    integrity = await api_client.get(f"{first.headers['location']}/integrity")
    assert integrity.status_code == 200
    assert integrity.json()["checks"][0]["name"] == "mission_input_hashes"

    openapi = (await api_client.get("/openapi.json")).json()
    assert "/v1/qualification/engagements/{engagement_id}/introduction" in openapi[
        "paths"
    ]
    parameters = openapi["paths"][
        "/v1/qualification/decisions/{decision_id}/approval"
    ]["post"]["parameters"]
    assert any(
        parameter["name"] == "If-Match"
        and parameter["in"] == "header"
        and parameter["required"] is True
        for parameter in parameters
    )


@pytest.mark.asyncio
async def test_qualification_contract_rejects_float_and_seller_mission_access(
    api_client: httpx.AsyncClient,
) -> None:
    body = _mission_body()
    buyer_context = body["buyer_context"]
    assert isinstance(buyer_context, dict)
    buyer_context["budget"] = 25000.5
    invalid = await api_client.post(
        "/v1/qualification/missions",
        headers={"Idempotency-Key": "qualification-invalid-1"},
        json=body,
    )
    assert invalid.status_code == 422

    seller = await api_client.post(
        "/v1/qualification/missions",
        headers={
            "Idempotency-Key": "qualification-seller-1",
            "X-Actor-Party": "SELLER",
            "X-Actor-Roles": "seller_editor,can_submit_request",
        },
        json=_mission_body(),
    )
    assert seller.status_code == 403
    assert seller.json()["error"]["code"] == "SELLER_ROUTE_FORBIDDEN"
