from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sira_api.config import ApiSettings
from sira_api.fixtures import DemoFixtureBundle
from sira_api.main import create_app
from sira_api.marketplace import SellerPrincipalBinding, StaticSellerOrganizationDirectory
from tests.support.cognitive_runtime import ScriptedCognitiveRuntime

from persistence.database import Database, DatabaseSettings
from persistence.models import Base

BUYER_TEST_AUTHORITIES = ",".join(
    (
        "requester",
        "can_submit_request",
        "can_view_context",
        "can_select_recommendation",
        "can_manage_procurement_gate",
        "can_approve_purchase",
        "can_execute_purchase",
    )
)


@pytest.fixture(autouse=True)
def isolate_provider_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep private laptop `.env` values from changing deterministic API tests."""

    monkeypatch.setenv("SIRA_CATALOG_DATABASE_URL", "")
    monkeypatch.setenv("GUEST_SESSION_ENABLED", "false")


@pytest_asyncio.fixture
async def api_application() -> AsyncIterator[FastAPI]:
    """Exercise the real repositories with an explicitly noncanonical SQLite test DB."""

    database_url = "sqlite+aiosqlite:///:memory:"
    database = Database(DatabaseSettings(database_url=database_url))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    application = create_app(
        settings=ApiSettings(app_env="test", database_url=database_url),
        database=database,
        cognitive_runtime=ScriptedCognitiveRuntime(
            decision_factory=lambda manifest: {
                "kind": "respond",
                "message": f"Test response for: {manifest.current_message}",
            }
        ),
    )
    async with application.router.lifespan_context(application):
        fixtures = DemoFixtureBundle.load()
        seller_directory = StaticSellerOrganizationDirectory(
            tuple(
                SellerPrincipalBinding(
                    candidate_id=candidate_id,
                    product_id=str(pack["product_id"]),
                    seller_actor_id=str(pack["seller_id"]),
                    seller_organization_id=f"org_{pack['seller_id']}",
                    merchant_name=str(pack["identity"]["seller_name"]),
                    merchant_url=str(fixtures.live_quote["merchant"]["url"]),
                )
                for candidate_id, pack in sorted(fixtures.packs.items())
            )
        )
        application.state.workflow_service.fixtures = fixtures
        application.state.workflow_service.seller_directory = seller_directory
        application.state.workflow_service._quote_clock = lambda: datetime.fromisoformat(
            str(fixtures.expected_purchase_intent["locked_at"]).replace("Z", "+00:00")
        )
        application.state.exchange_service.seller_directory = seller_directory
        yield application


@pytest_asyncio.fixture
async def api_client(api_application: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api_application),
        base_url="http://test",
        headers={
            "X-Organization-Id": "org_consultco",
            "X-Actor-Roles": BUYER_TEST_AUTHORITIES,
            "X-Actor-Party": "BUYER",
            "X-Step-Up-Verified": "true",
        },
    ) as client:
        await api_application.state.workflow_service.reset_demo("org_consultco")
        yield client
