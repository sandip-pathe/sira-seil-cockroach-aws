"""Worker-process ports whose implementations may hold provider clients in memory."""

from __future__ import annotations

from typing import Protocol

from sira_worker.contracts import (
    CheckoutActivityResult,
    FulfillmentActivityResult,
    IsolatedCheckoutActivityInput,
    ReconcileActivityInput,
    VerifyFulfillmentActivityInput,
    WorkflowFailureActivityInput,
)


class CheckoutActivityCoordinator(Protocol):
    """Loads canonical state and calls integrations inside the worker process only."""

    async def execute_isolated_checkout(
        self,
        request: IsolatedCheckoutActivityInput,
    ) -> CheckoutActivityResult: ...

    async def reconcile_checkout(
        self,
        request: ReconcileActivityInput,
    ) -> CheckoutActivityResult: ...

    async def verify_fulfillment(
        self,
        request: VerifyFulfillmentActivityInput,
    ) -> FulfillmentActivityResult: ...

    async def fail_checkout_workflow(
        self,
        request: WorkflowFailureActivityInput,
    ) -> None: ...
