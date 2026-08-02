from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

import httpx
import pytest
from sqlalchemy import select

from persistence.database import Database
from persistence.models import (
    MerchantOrder,
    OutboxEvent,
    PurchaseIntent,
    TransactionTransition,
)


def _idem(value: str) -> dict[str, str]:
    return {"Idempotency-Key": value}


def _database(client: httpx.AsyncClient) -> Database:
    transport = cast(Any, client._transport)
    return cast(Database, transport.app.state.database)


async def _paid_intent(client: httpx.AsyncClient) -> dict[str, Any]:
    created = await client.post(
        "/v1/decisions/dec_consultco_v1/purchase-intents",
        headers=_idem("post-purchase-intent-0001"),
        json={},
    )
    assert created.status_code == 201, created.text
    payload = cast(dict[str, Any], created.json())
    intent_id = str(payload["purchase_intent_id"])
    now = datetime.now(UTC)
    async with _database(client).transaction("org_consultco") as session:
        intent = (
            await session.execute(select(PurchaseIntent).where(PurchaseIntent.id == intent_id))
        ).scalar_one()
        intent.approval_status = "APPROVED"
        intent.payment_status = "PRAVA_COMPLETED"
        intent.fulfillment_status = "VERIFIED"
        intent.created_at = now - timedelta(days=40)
        session.add(
            TransactionTransition(
                id="tr_post_purchase_verified",
                organization_id="org_consultco",
                purchase_intent_id=intent.id,
                from_state="PENDING",
                to_state="VERIFIED",
                attempt_id=None,
                actor_type="worker",
                actor_id="checkout_coordinator",
                reason_code="ENTITLEMENT_VERIFIED",
                event_key="post-purchase-fixture-verified",
                provider_event_ref=None,
                payload_hash="sha256:" + "1" * 64,
                occurred_at=now - timedelta(days=40),
            )
        )
        session.add(
            MerchantOrder(
                id="mord_post_purchase",
                organization_id="org_consultco",
                purchase_intent_id=intent.id,
                merchant_adapter_id="controlled_merchant_fixture",
                idempotency_key="paid-order-post-purchase",
                external_order_id="merchant_order_post_purchase",
                status="APPROVED",
                amount=intent.amount,
                currency=intent.currency,
                safe_payload={"provider_confirmed": False},
                created_at=now,
                updated_at=now,
            )
        )
    return payload


@pytest.mark.asyncio
async def test_refund_request_is_durable_idempotent_and_never_fake_success(
    api_client: httpx.AsyncClient,
) -> None:
    intent = await _paid_intent(api_client)
    intent_id = str(intent["purchase_intent_id"])
    headers = _idem("refund-request-0001")
    body = {
        "kind": "REFUND",
        "requested_amount": intent["amount"],
        "reason_code": "PRODUCT_NOT_ADOPTED",
        "reason": "The deployment did not reach the agreed operating outcome.",
    }

    created = await api_client.post(
        f"/v1/purchase-intents/{intent_id}/reversals",
        headers=headers,
        json=body,
    )

    assert created.status_code == 202, created.text
    assert created.json()["status"] == "REQUESTED"
    assert created.json()["provider_confirmed"] is False
    assert created.json()["provider_action_required"] is True
    replay = await api_client.post(
        f"/v1/purchase-intents/{intent_id}/reversals",
        headers=headers,
        json=body,
    )
    assert replay.json() == created.json()
    duplicate_amount = await api_client.post(
        f"/v1/purchase-intents/{intent_id}/reversals",
        headers=_idem("refund-request-0002"),
        json={**body, "reason": "A second full refund must not be possible."},
    )
    assert duplicate_amount.status_code == 409
    assert duplicate_amount.json()["error"]["code"] == ("REVERSAL_AMOUNT_EXCEEDS_REMAINING")
    status = await api_client.get(f"/v1/purchase-intents/{intent_id}/status")
    assert status.json()["purchase_state"] == "REFUND_PENDING"
    async with _database(api_client).transaction("org_consultco") as session:
        event = (
            await session.execute(
                select(OutboxEvent).where(OutboxEvent.event_type == "purchase_reversal.requested")
            )
        ).scalar_one()
        assert event.payload["amount"] == intent["amount"]
        assert "reason" not in event.payload


@pytest.mark.asyncio
async def test_outcome_checkpoint_uses_frozen_target_and_only_proposes_learning(
    api_client: httpx.AsyncClient,
) -> None:
    intent = await _paid_intent(api_client)
    intent_id = str(intent["purchase_intent_id"])
    body = {
        "metric": "decision_retrieval_time_seconds",
        "observed_value": "150",
        "observed_at": datetime.now(UTC).isoformat(),
        "source_class": "HUMAN_ATTESTATION",
        "source_reference": "customer-success-review-30d",
    }

    recorded = await api_client.post(
        f"/v1/purchase-intents/{intent_id}/outcome-checkpoints",
        headers=_idem("outcome-checkpoint-0001"),
        json=body,
    )

    assert recorded.status_code == 201, recorded.text
    result = recorded.json()
    assert result["target_value"] == "120"
    assert result["target_operator"] == "lte"
    assert result["state"] == "NOT_ACHIEVED"
    assert result["preference_proposal"] == {
        "status": "PROPOSED",
        "action": "REVIEW_OUTCOME_PREFERENCE",
        "metric": "decision_retrieval_time_seconds",
        "ranking_effect": False,
        "silent_policy_update": False,
    }
    assert "customer-success-review-30d" not in recorded.text
    status = await api_client.get(f"/v1/purchase-intents/{intent_id}/status")
    assert status.json()["outcome_state"] == "NOT_ACHIEVED"


@pytest.mark.asyncio
async def test_outcome_metric_cannot_be_substituted_by_browser(
    api_client: httpx.AsyncClient,
) -> None:
    intent = await _paid_intent(api_client)
    response = await api_client.post(
        f"/v1/purchase-intents/{intent['purchase_intent_id']}/outcome-checkpoints",
        headers=_idem("outcome-metric-mismatch"),
        json={
            "metric": "revenue_generated",
            "observed_value": "999999",
            "observed_at": datetime.now(UTC).isoformat(),
            "source_class": "HUMAN_ATTESTATION",
            "source_reference": "untrusted-browser-claim",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "OUTCOME_TARGET_MISMATCH"
