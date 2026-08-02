from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sira_api.callback_state import BrowserReturnStateSigner
from sira_api.errors import ApiProblem
from sira_api.fixtures import DemoFixtureBundle
from sira_api.service import WorkflowService
from sira_worker.contracts import assert_credential_free_contract
from sqlalchemy import select

from persistence.database import Database, DatabaseSettings
from persistence.models import (
    ApprovalRequest,
    Base,
    BrowserReturnBinding,
    OutboxEvent,
    PaymentSession,
    PurchaseIntent,
    WorkflowRun,
)
from persistence.repositories import WorkflowRepository

RETURN_URL = "https://app.example.test/purchase/return"


@pytest_asyncio.fixture
async def callback_database() -> AsyncIterator[Database]:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield database
    finally:
        await database.close()


async def seed_callback(
    database: Database,
    *,
    expired: bool = False,
    expired_approval: bool = False,
    mismatched_provider: bool = False,
) -> tuple[WorkflowService, str, str]:
    signer = BrowserReturnStateSigner(
        "integration-browser-return-signing-key"  # pragma: allowlist secret
    )
    service = WorkflowService(
        database,
        DemoFixtureBundle.load(),
        browser_return_signer=signer,
        browser_return_ttl_seconds=600,
    )
    await service.reset_demo("org_consultco")
    _, view = await service.lock_purchase_intent(
        organization_id="org_consultco",
        actor_id="usr_cardholder",
        decision_id="dec_consultco_v1",
        idempotency_key="browser-return-lock",
        body={"solution_plan_id": None},
    )
    intent_id = str(view["purchase_intent_id"])
    state = signer.issue()
    provider_session_id = "ses_browser_return_test"
    now = datetime.now(UTC)
    async with database.transaction("org_consultco") as session:
        repository = WorkflowRepository(session, "org_consultco")
        intent = await repository.get_purchase_intent(intent_id, lock=True)
        intent.approval_status = "APPROVED"
        intent.payment_status = "SESSION_CREATED"
        intent.quote_expires_at = now + timedelta(hours=2)
        session.add(
            ApprovalRequest(
                id="apr_browser_return_test",
                organization_id="org_consultco",
                purchase_intent_id=intent_id,
                intent_hash=intent.intent_hash,
                policy_version=1,
                status="APPROVED",
                required_roles=["budget_owner"],
                approved_roles=["budget_owner"],
                expires_at=(
                    now - timedelta(seconds=1) if expired_approval else now + timedelta(hours=1)
                ),
            )
        )
        payment = PaymentSession(
            id="pays_browser_return_test",
            organization_id="org_consultco",
            purchase_intent_id=intent_id,
            provider="PRAVA",
            provider_session_id=provider_session_id,
            provider_order_id="ord_browser_return_test",
            hosted_url="https://checkout.prava.test/session/browser-return",
            expires_at=now + timedelta(hours=1),
            status="SESSION_CREATED",
        )
        session.add(payment)
        session.add(
            BrowserReturnBinding(
                id="brb_browser_return_test",
                organization_id="org_consultco",
                purchase_intent_id=intent_id,
                payment_session_id=payment.id,
                actor_id="usr_cardholder",
                state_hash=signer.digest(state),
                provider_session_hash=(
                    signer.digest("ses_different")
                    if mismatched_provider
                    else signer.digest(provider_session_id)
                ),
                return_url_hash=signer.digest(RETURN_URL),
                expires_at=(now - timedelta(seconds=1) if expired else now + timedelta(minutes=10)),
                consumed_at=None,
            )
        )
    return service, state, intent_id


@pytest.mark.asyncio
async def test_browser_return_persists_only_safe_bindings_and_checkout_outbox(
    callback_database: Database,
) -> None:
    service, state, intent_id = await seed_callback(callback_database)

    response = await service.accept_prava_browser_return(
        organization_id="org_consultco",
        actor_id="usr_cardholder",
        body={"state": state, "return_url": RETURN_URL},
    )

    workflow_id = f"wf_checkout_{intent_id}"
    assert response == {
        "workflow_id": workflow_id,
        "status_url": f"/v1/workflows/{workflow_id}",
        "events_url": f"/v1/workflows/{workflow_id}/events",
    }
    async with callback_database.transaction("org_consultco") as session:
        binding = (await session.execute(select(BrowserReturnBinding))).scalar_one()
        payment = (await session.execute(select(PaymentSession))).scalar_one()
        workflow = (await session.execute(select(WorkflowRun))).scalar_one()
        event = (
            await session.execute(
                select(OutboxEvent).where(OutboxEvent.event_type == "purchase_checkout.requested")
            )
        ).scalar_one()
        assert binding.consumed_at is not None
        assert payment.status == "CARDHOLDER_PENDING"
        assert workflow.status == "PENDING"
        assert event.published_at is None
        assert event.payload["workflow_id"] == workflow_id
        assert event.payload["purchase_intent_id"] == intent_id
        assert_credential_free_contract(event.payload)
        persisted = json.dumps(
            {
                "state_hash": binding.state_hash,
                "return_url_hash": binding.return_url_hash,
                "provider_session_hash": binding.provider_session_hash,
                "event": event.payload,
                "workflow": workflow.event_log,
            },
            sort_keys=True,
        )
        assert state not in persisted
        assert RETURN_URL not in persisted


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("expired", "mismatched_provider", "expected_code"),
    [
        (True, False, "CALLBACK_STATE_EXPIRED"),
        (False, True, "CALLBACK_BINDING_MISMATCH"),
    ],
)
async def test_browser_return_rejects_expiry_and_provider_binding_mismatch(
    callback_database: Database,
    expired: bool,
    mismatched_provider: bool,
    expected_code: str,
) -> None:
    service, state, _intent_id = await seed_callback(
        callback_database,
        expired=expired,
        mismatched_provider=mismatched_provider,
    )

    with pytest.raises(ApiProblem) as captured:
        await service.accept_prava_browser_return(
            organization_id="org_consultco",
            actor_id="usr_cardholder",
            body={"state": state, "return_url": RETURN_URL},
        )

    assert captured.value.code == expected_code
    async with callback_database.transaction("org_consultco") as session:
        binding = (await session.execute(select(BrowserReturnBinding))).scalar_one()
        checkout_events = (
            await session.execute(
                select(OutboxEvent).where(OutboxEvent.event_type == "purchase_checkout.requested")
            )
        ).scalars()
        assert binding.consumed_at is None
        assert list(checkout_events) == []


@pytest.mark.asyncio
async def test_browser_return_expires_stale_exact_hash_approval(
    callback_database: Database,
) -> None:
    service, state, intent_id = await seed_callback(callback_database, expired_approval=True)

    with pytest.raises(ApiProblem) as captured:
        await service.accept_prava_browser_return(
            organization_id="org_consultco",
            actor_id="usr_cardholder",
            body={"state": state, "return_url": RETURN_URL},
        )

    assert captured.value.code == "APPROVAL_EXPIRED"
    async with callback_database.transaction("org_consultco") as session:
        approval = (await session.execute(select(ApprovalRequest))).scalar_one()
        intent = (
            await session.execute(select(PurchaseIntent).where(PurchaseIntent.id == intent_id))
        ).scalar_one()
        checkout_events = (
            await session.execute(
                select(OutboxEvent).where(OutboxEvent.event_type == "purchase_checkout.requested")
            )
        ).scalars()
        assert approval.status == "EXPIRED"
        assert intent.approval_status == "EXPIRED"
        assert list(checkout_events) == []
