from __future__ import annotations

import httpx
from sira_api.config import ApiSettings
from sira_api.main import create_app
from tests.support.cognitive_runtime import ScriptedCognitiveRuntime

from persistence.database import Database, DatabaseSettings
from persistence.models import Base, Organization


async def test_new_development_guest_gets_isolated_demo_and_seller_projection() -> None:
    database_url = "sqlite+aiosqlite:///:memory:"
    database = Database(DatabaseSettings(database_url=database_url))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.transaction("org_seller_fixture_d") as session:
        session.add(Organization(id="org_seller_fixture_d", name="Luma Labs", version=1))
    application = create_app(
        settings=ApiSettings(
            app_env="test",
            database_url=database_url,
            guest_session_enabled=True,
            development_fixture_mode=True,
            demo_reset_enabled=True,
        ),
        database=database,
        cognitive_runtime=ScriptedCognitiveRuntime(
            decisions=[{"kind": "respond", "message": "Unused test response."}]
        ),
    )
    try:
        async with application.router.lifespan_context(application):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application),
                base_url="http://test",
            ) as client:
                capabilities = await client.get(
                    "/v1/capabilities", headers={"X-Workspace-Mode": "sira"}
                )
                assert capabilities.status_code == 200, capabilities.text
                assert "sira_guest" in client.cookies

                index = await client.get(
                    "/v1/decision-requests", headers={"X-Workspace-Mode": "sira"}
                )
                assert index.status_code == 200, index.text
                request_id = index.json()["active"][0]["id"]
                assert request_id.startswith("req_guest_")

                decision = await client.get(
                    f"/v1/decision-requests/{request_id}/decision-view?version=1",
                    headers={"X-Workspace-Mode": "sira"},
                )
                assert decision.status_code == 200, decision.text

                created = await client.post(
                    "/v1/exchange-cases",
                    headers={
                        "X-Workspace-Mode": "sira",
                        "Idempotency-Key": "guest-exchange-create-1",
                    },
                    json={
                        "purchase_request_id": request_id,
                        "candidate_id": "fixture_selected_fit",
                    },
                )
                assert created.status_code == 201, created.text
                payload = created.json()
                assert payload["projection"]["party"] == "BUYER"

                seller = await client.get(
                    f"/v1/exchange-cases/{payload['case_id']}",
                    params={"route": payload["route_capability"]},
                    headers={"X-Workspace-Mode": "seil"},
                )
                assert seller.status_code == 200, seller.text
                assert seller.json()["party"] == "SELLER"
    finally:
        await database.close()
