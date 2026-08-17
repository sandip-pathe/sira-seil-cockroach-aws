from __future__ import annotations

import httpx
import pytest


def idempotency(value: str) -> dict[str, str]:
    return {"Idempotency-Key": value}


async def lock_intent_and_start_approval(
    client: httpx.AsyncClient,
) -> tuple[dict[str, object], dict[str, object]]:
    intent_response = await client.post(
        "/v1/decisions/dec_consultco_v1/purchase-intents",
        headers=idempotency("handoff-lock-intent"),
        json={},
    )
    assert intent_response.status_code == 201, intent_response.text
    intent = intent_response.json()
    approval_response = await client.post(
        f"/v1/purchase-intents/{intent['purchase_intent_id']}/approval-requests",
        headers=idempotency("handoff-start-approval"),
        json={},
    )
    assert approval_response.status_code == 201, approval_response.text
    return intent, approval_response.json()


async def approve_exact_intent(client: httpx.AsyncClient, approval: dict[str, object]) -> None:
    for index, role in enumerate(
        ("operations_owner", "security_privacy_owner", "legal_owner", "budget_owner")
    ):
        response = await client.post(
            f"/v1/approval-requests/{approval['id']}/approve",
            headers={
                **idempotency(f"handoff-approve-{index}"),
                "X-Actor-Id": f"usr_{role}",
                "X-Actor-Roles": f"{role},can_approve_purchase",
                "X-Step-Up-Verified": "true",
            },
            json={"intent_hash": approval["intent_hash"], "actor_role": role},
        )
        assert response.status_code == 200, response.text
    assert response.json()["status"] == "APPROVED"


@pytest.mark.asyncio
async def test_payment_handoff_requires_exact_approval_and_stops_at_navigation(
    api_client: httpx.AsyncClient,
) -> None:
    intent, approval = await lock_intent_and_start_approval(api_client)
    endpoint = f"/v1/purchase-intents/{intent['purchase_intent_id']}/payment-handoff"

    blocked = await api_client.post(endpoint, headers=idempotency("handoff-before-approval"))
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["error"]["code"] == "APPROVAL_REQUIRED"

    await approve_exact_intent(api_client, approval)
    created = await api_client.post(endpoint, headers=idempotency("handoff-create"))
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["status"] == "READY"
    assert payload["intent_hash"] == approval["intent_hash"]
    assert payload["destination_url"].startswith("https://")
    assert "provider" not in payload
    assert "payment_status" not in payload
    assert "receipt" not in payload

    replay = await api_client.post(endpoint, headers=idempotency("handoff-create"))
    assert replay.status_code == 201
    assert replay.json() == payload

    opened = await api_client.post(
        f"/v1/payment-handoffs/{payload['id']}/open",
        headers=idempotency("handoff-open"),
    )
    assert opened.status_code == 200, opened.text
    assert opened.json()["status"] == "OPENED"
    assert opened.json()["opened_at"] is not None
    assert opened.json()["handoff_hash"] == payload["handoff_hash"]

    second_open = await api_client.post(
        f"/v1/payment-handoffs/{payload['id']}/open",
        headers=idempotency("handoff-open-again"),
    )
    assert second_open.status_code == 409
    assert second_open.json()["error"]["code"] == "HANDOFF_NOT_OPENABLE"
