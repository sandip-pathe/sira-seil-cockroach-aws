from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from sira_api.config import ApiSettings
from sira_api.main import create_app

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

PROVIDER_ENV_KEYS = (
    "PRAVA_BASE_URL",
    "PRAVA_SECRET_KEY",
    "PRAVA_MERCHANT_URL",
    "PRAVA_CALLBACK_URL",
    "PRAVA_USER_EMAIL",
    "PRAVA_MERCHANT_COUNTRY",
    "PRAVA_HOSTED_CHECKOUT_HOSTS",
    "CONTROLLED_MERCHANT_BASE_URL",
    "CONTROLLED_MERCHANT_API_KEY",
    "CONTROLLED_MERCHANT_ID",
)


@pytest.fixture(autouse=True)
def isolate_provider_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep private laptop `.env` values from changing deterministic API tests."""

    for setting in PROVIDER_ENV_KEYS:
        monkeypatch.setenv(setting, "")


@pytest_asyncio.fixture
async def api_client() -> AsyncIterator[httpx.AsyncClient]:
    """Exercise the real repositories with an explicitly noncanonical SQLite test DB."""

    database_url = "sqlite+aiosqlite:///:memory:"
    database = Database(DatabaseSettings(database_url=database_url))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    application = create_app(
        settings=ApiSettings(app_env="test", database_url=database_url),
        database=database,
    )
    async with application.router.lifespan_context(application):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application),
            base_url="http://test",
            headers={
                "X-Actor-Roles": BUYER_TEST_AUTHORITIES,
                "X-Actor-Party": "BUYER",
                "X-Step-Up-Verified": "true",
            },
        ) as client:
            reset = await client.post("/v1/demo/reset")
            assert reset.status_code == 200, reset.text
            yield client
