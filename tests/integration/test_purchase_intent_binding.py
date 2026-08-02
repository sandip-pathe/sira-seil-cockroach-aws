from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sira_api.errors import ApiProblem
from sira_api.fixtures import DemoFixtureBundle
from sira_api.service import WorkflowService

from domain import content_hash
from persistence.database import Database, DatabaseSettings
from persistence.models import Base
from persistence.repositories import WorkflowRepository


@pytest_asyncio.fixture
async def intent_database() -> AsyncIterator[Database]:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield database
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_intent_lock_uses_persisted_plan_terms_not_mutable_fixture(
    intent_database: Database,
) -> None:
    fixtures = DemoFixtureBundle.load()
    service = WorkflowService(intent_database, fixtures)
    await service.reset_demo("org_consultco")

    fixtures.expected_purchase_intent["amount"] = "999999.00"
    fixtures.expected_purchase_intent["merchant"]["merchant_id"] = "wrong_merchant"

    _, intent = await service.lock_purchase_intent(
        organization_id="org_consultco",
        actor_id="usr_requester",
        decision_id="dec_consultco_v1",
        idempotency_key="persisted-plan-terms",
        body={"solution_plan_id": None},
    )

    assert intent["amount"] == "89.00"
    assert intent["merchant"]["merchant_id"] == "merchant_fixture_d"
    assert intent["offer_id"] == "offer_fixture_d_monthly"


@pytest.mark.asyncio
async def test_intent_lock_fails_when_selected_plan_has_no_commercial_snapshot(
    intent_database: Database,
) -> None:
    service = WorkflowService(intent_database, DemoFixtureBundle.load())
    await service.reset_demo("org_consultco")

    async with intent_database.transaction("org_consultco") as session:
        repository = WorkflowRepository(session, "org_consultco")
        plan = await repository.get_selected_solution_plan(
            "dec_consultco_v1", "plan_5a682ec42084ae355a2d"
        )
        plan.payload = {
            key: value for key, value in plan.payload.items() if key != "commercial_terms"
        }
        plan.plan_hash = content_hash(plan.payload)

    with pytest.raises(ApiProblem) as captured:
        await service.lock_purchase_intent(
            organization_id="org_consultco",
            actor_id="usr_requester",
            decision_id="dec_consultco_v1",
            idempotency_key="missing-plan-terms",
            body={"solution_plan_id": None},
        )
    assert captured.value.code == "PLAN_COMMERCIAL_TERMS_INVALID"
