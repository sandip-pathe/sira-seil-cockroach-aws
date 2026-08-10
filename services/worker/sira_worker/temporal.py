"""Temporal worker construction kept outside domain and provider modules."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from temporalio.client import Client
from temporalio.worker import Worker

from sira_worker.activities import CheckoutActivities, PravaShoppingActivities
from sira_worker.contracts import assert_all_contract_schemas_are_credential_free
from sira_worker.ports import CheckoutActivityCoordinator, PravaShoppingCoordinator
from sira_worker.workflows import (
    PravaShoppingWorkflow,
    PurchaseCheckoutWorkflow,
    PurchaseReversalWorkflow,
)


def build_worker(
    *,
    client: Client,
    task_queue: str,
    coordinator: CheckoutActivityCoordinator | None,
    prava_coordinator: PravaShoppingCoordinator | None = None,
) -> Worker:
    """Build, but do not start, the checkout worker."""

    if not task_queue.strip():
        raise ValueError("task_queue must not be empty")
    assert_all_contract_schemas_are_credential_free()
    workflows: list[type] = []
    registered_activities: list[Callable[..., Any]] = []
    if coordinator is not None:
        activities = CheckoutActivities(coordinator)
        workflows.extend([PurchaseCheckoutWorkflow, PurchaseReversalWorkflow])
        registered_activities.extend(
            [
                activities.execute_isolated_checkout,
                activities.reconcile_checkout,
                activities.verify_fulfillment,
                activities.fail_checkout_workflow,
                activities.execute_refund,
                activities.reconcile_refund,
            ]
        )
    if prava_coordinator is not None:
        prava_activities = PravaShoppingActivities(prava_coordinator)
        workflows.append(PravaShoppingWorkflow)
        registered_activities.extend(
            [
                prava_activities.payment_status,
                prava_activities.checkout,
                prava_activities.fail,
            ]
        )
    return Worker(
        client,
        task_queue=task_queue,
        workflows=workflows,
        activities=registered_activities,
    )


async def connect_temporal(
    target: str,
    *,
    namespace: str = "default",
    api_key: str | None = None,
    tls: bool = False,
) -> Client:
    """Create a Temporal client for self-hosted or Temporal Cloud endpoints."""

    if not target.strip() or not namespace.strip():
        raise ValueError("Temporal target and namespace are required")
    return await Client.connect(
        target,
        namespace=namespace,
        api_key=api_key or None,
        tls=tls,
    )
