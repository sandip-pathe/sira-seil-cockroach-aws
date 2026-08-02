"""Restart-safe PostgreSQL outbox delivery into deterministic Temporal workflows."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from persistence.database import Database
from persistence.models import OutboxEvent, WorkflowRun
from sira_worker.contracts import (
    PurchaseCheckoutWorkflowInput,
    PurchaseReversalWorkflowInput,
    assert_credential_free_contract,
)
from sira_worker.workflows import PurchaseCheckoutWorkflow, PurchaseReversalWorkflow

CHECKOUT_EVENT_TYPE = "purchase_checkout.requested"
REVERSAL_EVENT_TYPE = "purchase_reversal.requested"


class CheckoutOutboxDispatcher:
    """Deliver unpublished checkout events exactly once at the Temporal workflow boundary."""

    def __init__(
        self,
        *,
        database: Database,
        temporal: Client,
        task_queue: str,
        merchant_adapter_id: str,
        organization_ids: tuple[str, ...],
        poll_interval_seconds: float = 1.0,
    ) -> None:
        if not task_queue.strip() or not merchant_adapter_id.strip() or not organization_ids:
            raise ValueError("dispatcher configuration is incomplete")
        if any(not value.strip() or value.strip() != value for value in organization_ids):
            raise ValueError("dispatcher organization IDs must be explicit normalized values")
        if poll_interval_seconds <= 0:
            raise ValueError("dispatcher poll interval must be positive")
        self._database = database
        self._temporal = temporal
        self._task_queue = task_queue
        self._merchant_adapter_id = merchant_adapter_id
        self._organization_ids = organization_ids
        self._poll_interval_seconds = poll_interval_seconds

    async def run(self) -> None:
        while True:
            delivered = False
            failed = False
            for organization_id in self._organization_ids:
                try:
                    while await self.dispatch_once(organization_id):
                        delivered = True
                except Exception:
                    # The event remains unpublished. Never surface provider/request data in
                    # an exception log; a later poll or process restart retries delivery.
                    failed = True
            if failed or not delivered:
                await asyncio.sleep(self._poll_interval_seconds)

    async def dispatch_once(self, organization_id: str) -> bool:
        event_id: str
        event_type: str
        payload: dict[str, Any]
        async with self._database.transaction(organization_id) as session:
            event = (
                await session.execute(
                    select(OutboxEvent)
                    .where(
                        OutboxEvent.organization_id == organization_id,
                        OutboxEvent.event_type.in_([CHECKOUT_EVENT_TYPE, REVERSAL_EVENT_TYPE]),
                        OutboxEvent.published_at.is_(None),
                    )
                    .order_by(OutboxEvent.occurred_at, OutboxEvent.id)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if event is None:
                return False
            event_id = event.id
            event_type = event.event_type
            payload = deepcopy(event.payload)

        try:
            if event_type == CHECKOUT_EVENT_TYPE:
                workflow_id, checkout_request = self._workflow_request(organization_id, payload)
                reversal_request = None
            else:
                workflow_id, reversal_request = self._reversal_workflow_request(
                    organization_id, payload
                )
                checkout_request = None
        except ValueError:
            await self._quarantine_invalid_event(organization_id, event_id)
            return True
        try:
            if checkout_request is not None:
                await self._temporal.start_workflow(
                    PurchaseCheckoutWorkflow.run,
                    checkout_request,
                    id=workflow_id,
                    task_queue=self._task_queue,
                    id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                )
            else:
                assert reversal_request is not None
                await self._temporal.start_workflow(
                    PurchaseReversalWorkflow.run,
                    reversal_request,
                    id=workflow_id,
                    task_queue=self._task_queue,
                    id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                )
        except WorkflowAlreadyStartedError:
            # A crash can happen after Temporal accepts the start and before PostgreSQL
            # records publication. The deterministic ID makes that retry an acknowledgement.
            pass

        async with self._database.transaction(organization_id) as session:
            event = (
                await session.execute(
                    select(OutboxEvent)
                    .where(
                        OutboxEvent.id == event_id,
                        OutboxEvent.organization_id == organization_id,
                    )
                    .with_for_update()
                )
            ).scalar_one()
            if event.published_at is not None:
                return True
            workflow = (
                await session.execute(
                    select(WorkflowRun)
                    .where(
                        WorkflowRun.id == workflow_id,
                        WorkflowRun.organization_id == organization_id,
                    )
                    .with_for_update()
                )
            ).scalar_one()
            event.published_at = datetime.now(UTC)
            if workflow.status == "PENDING":
                workflow.status = "RUNNING"
                workflow.event_log = [
                    *workflow.event_log,
                    {
                        "id": str(len(workflow.event_log) + 1),
                        "status": "RUNNING",
                        "message": (
                            "Checkout workflow accepted"
                            if event_type == CHECKOUT_EVENT_TYPE
                            else "Refund workflow accepted"
                        ),
                    },
                ]
        return True

    async def _quarantine_invalid_event(self, organization_id: str, event_id: str) -> None:
        async with self._database.transaction(organization_id) as session:
            event = (
                await session.execute(
                    select(OutboxEvent)
                    .where(
                        OutboxEvent.id == event_id,
                        OutboxEvent.organization_id == organization_id,
                    )
                    .with_for_update()
                )
            ).scalar_one()
            if event.published_at is not None:
                return
            event.published_at = datetime.now(UTC)
            workflow = (
                await session.execute(
                    select(WorkflowRun)
                    .where(
                        WorkflowRun.organization_id == organization_id,
                        WorkflowRun.aggregate_type == event.aggregate_type,
                        WorkflowRun.aggregate_id == event.aggregate_id,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if workflow is not None and workflow.status not in {"COMPLETED", "FAILED"}:
                workflow.status = "FAILED"
                workflow.safe_error_code = "OUTBOX_CONTRACT_INVALID"
                workflow.event_log = [
                    *workflow.event_log,
                    {
                        "id": str(len(workflow.event_log) + 1),
                        "status": "FAILED",
                        "message": "Checkout dispatch contract was rejected",
                    },
                ]

    def _workflow_request(
        self, organization_id: str, payload: dict[str, Any]
    ) -> tuple[str, PurchaseCheckoutWorkflowInput]:
        required = {
            "workflow_id",
            "purchase_intent_id",
            "intent_hash",
            "payment_session_id",
            "prava_session_id",
        }
        if set(payload) != required or not all(
            isinstance(payload[name], str) and payload[name] for name in required
        ):
            raise ValueError("checkout outbox payload does not match the safe contract")
        purchase_intent_id = str(payload["purchase_intent_id"])
        workflow_id = str(payload["workflow_id"])
        if workflow_id != f"wf_checkout_{purchase_intent_id}":
            raise ValueError("checkout workflow identity is not deterministic")
        request = PurchaseCheckoutWorkflowInput(
            organization_id=organization_id,
            purchase_intent_id=purchase_intent_id,
            intent_hash=str(payload["intent_hash"]),
            prava_session_id=str(payload["prava_session_id"]),
            merchant_adapter_id=self._merchant_adapter_id,
            idempotency_key=workflow_id,
        )
        assert_credential_free_contract(payload)
        assert_credential_free_contract(request)
        return workflow_id, request

    def _reversal_workflow_request(
        self, organization_id: str, payload: dict[str, Any]
    ) -> tuple[str, PurchaseReversalWorkflowInput]:
        required = {
            "workflow_id",
            "reversal_id",
            "purchase_intent_id",
            "intent_hash",
            "merchant_order_id",
            "amount",
            "currency",
            "kind",
            "reason_code",
        }
        if set(payload) != required or not all(
            isinstance(payload[name], str) and payload[name] for name in required
        ):
            raise ValueError("reversal outbox payload does not match the safe contract")
        reversal_id = str(payload["reversal_id"])
        workflow_id = str(payload["workflow_id"])
        if workflow_id != f"wf_reversal_{reversal_id}":
            raise ValueError("reversal workflow identity is not deterministic")
        request = PurchaseReversalWorkflowInput(
            organization_id=organization_id,
            reversal_id=reversal_id,
            purchase_intent_id=str(payload["purchase_intent_id"]),
            intent_hash=str(payload["intent_hash"]),
            idempotency_key=workflow_id,
        )
        assert_credential_free_contract(payload)
        assert_credential_free_contract(request)
        return workflow_id, request
