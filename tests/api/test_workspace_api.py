from __future__ import annotations

import httpx
import pytest


@pytest.mark.asyncio
async def test_workspace_catalog_and_connectors_use_live_routes(
    api_client: httpx.AsyncClient,
) -> None:
    catalog = await api_client.get("/v1/workspace/catalog")
    connectors = await api_client.get("/v1/workspace/connectors")

    assert catalog.status_code == 200
    assert len(catalog.json()) == 4
    assert connectors.status_code == 200
    assert {item["id"] for item in connectors.json()} == {
        "business-context",
        "google-workspace",
    }


@pytest.mark.asyncio
async def test_workspace_chat_enforces_agent_party_identity(
    api_client: httpx.AsyncClient,
) -> None:
    buyer_using_seil = await api_client.post(
        "/v1/workspace/chat",
        json={"mode": "seil", "message": "Inspect my product", "history": []},
    )
    seller_using_sira = await api_client.post(
        "/v1/workspace/chat",
        headers={
            "X-Actor-Id": "seller_fixture_d",
            "X-Actor-Party": "SELLER",
            "X-Actor-Roles": "seller_editor",
        },
        json={"mode": "sira", "message": "Buy a product", "history": []},
    )

    assert buyer_using_seil.status_code == 403
    assert buyer_using_seil.json()["error"]["code"] == "SEIL_IDENTITY_REQUIRED"
    assert seller_using_sira.status_code == 403
    assert seller_using_sira.json()["error"]["code"] == "SIRA_IDENTITY_REQUIRED"


@pytest.mark.asyncio
async def test_seller_can_reach_seil_chat_boundary(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.post(
        "/v1/workspace/chat",
        headers={
            "X-Actor-Id": "seller_fixture_d",
            "X-Actor-Party": "SELLER",
            "X-Actor-Roles": "seller_editor",
        },
        json={"mode": "seil", "message": "Inspect my product", "history": []},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"].startswith("msn_")
    assert body["mission"]["mode"] == "seil"
    assert body["message"]
