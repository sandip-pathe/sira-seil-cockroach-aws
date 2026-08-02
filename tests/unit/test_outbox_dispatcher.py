from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from sira_worker.contracts import PurchaseCheckoutWorkflowInput
from sira_worker.outbox import CheckoutOutboxDispatcher
from sqlalchemy import select
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from persistence.database import Database, DatabaseSettings
from persistence.models import Base, Organization, OutboxEvent, WorkflowRun

ORGANIZATION_ID = "org_consultco"
INTENT_ID = "pi_dispatch_test"
WORKFLOW_ID = f"wf_checkout_{INTENT_ID}"


class FakeTemporal:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure
        self.calls: list[tuple[object, PurchaseCheckoutWorkflowInput, dict[str, Any]]] = []

    async def start_workflow(
        self,
        workflow: object,
        request: PurchaseCheckoutWorkflowInput,
        **kwargs: Any,
    ) -> object:
        self.calls.append((workflow, request, kwargs))
        if self.failure is not None:
            raise self.failure
        return object()


@pytest_asyncio.fixture
async def outbox_database() -> AsyncIterator[Database]:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield database
    finally:
        await database.close()


async def seed_checkout_event(database: Database, *, workflow_status: str = "PENDING") -> None:
    async with database.sessions() as session, session.begin():
        session.add(Organization(id=ORGANIZATION_ID, name="Dispatcher test"))
    async with database.transaction(ORGANIZATION_ID) as session:
        session.add(
            WorkflowRun(
                id=WORKFLOW_ID,
                organization_id=ORGANIZATION_ID,
                aggregate_type="purchase_intent",
                aggregate_id=INTENT_ID,
                operation="purchase_checkout",
                status=workflow_status,
                result_reference=f"/v1/purchase-intents/{INTENT_ID}/status",
                safe_error_code=None,
                event_log=[],
            )
        )
        session.add(
            OutboxEvent(
                id="out_dispatch_test",
                organization_id=ORGANIZATION_ID,
                aggregate_type="purchase_intent",
                aggregate_id=INTENT_ID,
                event_type="purchase_checkout.requested",
                event_key="purchase-checkout-requested:pays_dispatch_test",
                payload={
                    "workflow_id": WORKFLOW_ID,
                    "purchase_intent_id": INTENT_ID,
                    "intent_hash": "sha256:" + "1" * 64,
                    "payment_session_id": "pays_dispatch_test",
                    "prava_session_id": "ses_dispatch_test",
                },
                published_at=None,
            )
        )


def dispatcher(database: Database, temporal: FakeTemporal) -> CheckoutOutboxDispatcher:
    return CheckoutOutboxDispatcher(
        database=database,
        temporal=temporal,  # type: ignore[arg-type]
        task_queue="checkout-test",
        merchant_adapter_id="merchant_test",
        organization_ids=(ORGANIZATION_ID,),
    )


@pytest.mark.asyncio
async def test_dispatcher_starts_exact_credential_free_workflow_and_acknowledges(
    outbox_database: Database,
) -> None:
    await seed_checkout_event(outbox_database)
    temporal = FakeTemporal()

    delivered = await dispatcher(outbox_database, temporal).dispatch_once(ORGANIZATION_ID)

    assert delivered is True
    assert len(temporal.calls) == 1
    _workflow, request, kwargs = temporal.calls[0]
    assert request == PurchaseCheckoutWorkflowInput(
        organization_id=ORGANIZATION_ID,
        purchase_intent_id=INTENT_ID,
        intent_hash="sha256:" + "1" * 64,
        prava_session_id="ses_dispatch_test",
        merchant_adapter_id="merchant_test",
        idempotency_key=WORKFLOW_ID,
    )
    assert kwargs == {
        "id": WORKFLOW_ID,
        "task_queue": "checkout-test",
        "id_reuse_policy": WorkflowIDReusePolicy.REJECT_DUPLICATE,
    }
    async with outbox_database.transaction(ORGANIZATION_ID) as session:
        event = (await session.execute(select(OutboxEvent))).scalar_one()
        workflow = (await session.execute(select(WorkflowRun))).scalar_one()
        assert event.published_at is not None
        assert workflow.status == "RUNNING"


@pytest.mark.asyncio
async def test_dispatcher_leaves_event_pending_when_temporal_is_unavailable(
    outbox_database: Database,
) -> None:
    await seed_checkout_event(outbox_database)
    temporal = FakeTemporal(RuntimeError("temporal unavailable"))

    with pytest.raises(RuntimeError, match="temporal unavailable"):
        await dispatcher(outbox_database, temporal).dispatch_once(ORGANIZATION_ID)

    async with outbox_database.transaction(ORGANIZATION_ID) as session:
        event = (await session.execute(select(OutboxEvent))).scalar_one()
        workflow = (await session.execute(select(WorkflowRun))).scalar_one()
        assert event.published_at is None
        assert workflow.status == "PENDING"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("initial_status", "expected_status"),
    [("PENDING", "RUNNING"), ("COMPLETED", "COMPLETED"), ("FAILED", "FAILED")],
)
async def test_restart_acknowledges_already_started_without_regressing_terminal_state(
    outbox_database: Database,
    initial_status: str,
    expected_status: str,
) -> None:
    await seed_checkout_event(outbox_database, workflow_status=initial_status)
    temporal = FakeTemporal(WorkflowAlreadyStartedError(WORKFLOW_ID, "sira.purchase_checkout"))

    delivered = await dispatcher(outbox_database, temporal).dispatch_once(ORGANIZATION_ID)

    assert delivered is True
    async with outbox_database.transaction(ORGANIZATION_ID) as session:
        event = (await session.execute(select(OutboxEvent))).scalar_one()
        workflow = (await session.execute(select(WorkflowRun))).scalar_one()
        assert event.published_at is not None
        assert workflow.status == expected_status
