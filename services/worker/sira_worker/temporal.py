"""Temporal worker construction kept outside domain and provider modules."""

from __future__ import annotations

from temporalio.client import Client
from temporalio.worker import Worker

from sira_worker.activities import CheckoutActivities
from sira_worker.contracts import assert_all_contract_schemas_are_credential_free
from sira_worker.ports import CheckoutActivityCoordinator
from sira_worker.workflows import PurchaseCheckoutWorkflow


def build_worker(
    *,
    client: Client,
    task_queue: str,
    coordinator: CheckoutActivityCoordinator,
) -> Worker:
    """Build, but do not start, the checkout worker."""

    if not task_queue.strip():
        raise ValueError("task_queue must not be empty")
    assert_all_contract_schemas_are_credential_free()
    activities = CheckoutActivities(coordinator)
    return Worker(
        client,
        task_queue=task_queue,
        workflows=[PurchaseCheckoutWorkflow],
        activities=[
            activities.execute_isolated_checkout,
            activities.reconcile_checkout,
        ],
    )


async def connect_temporal(target: str, *, namespace: str = "default") -> Client:
    """Create a Temporal client using only non-secret connection identifiers."""

    if not target.strip() or not namespace.strip():
        raise ValueError("Temporal target and namespace are required")
    return await Client.connect(target, namespace=namespace)
