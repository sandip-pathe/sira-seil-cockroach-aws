"""Temporal activities wrapping credential-isolated provider coordination."""

from __future__ import annotations

from temporalio import activity
from temporalio.exceptions import ApplicationError

from integrations.errors import ProviderError
from sira_worker.contracts import (
    CheckoutActivityResult,
    FulfillmentActivityResult,
    IsolatedCheckoutActivityInput,
    PravaPaymentStatusResult,
    PravaShoppingWorkflowInput,
    PravaShoppingWorkflowResult,
    ReconcileActivityInput,
    RefundActivityInput,
    RefundActivityResult,
    VerifyFulfillmentActivityInput,
    WorkflowFailureActivityInput,
    assert_credential_free_contract,
)
from sira_worker.ports import CheckoutActivityCoordinator, PravaShoppingCoordinator


class PravaShoppingActivities:
    def __init__(self, coordinator: PravaShoppingCoordinator) -> None:
        self._coordinator = coordinator

    @activity.defn(name="sira.prava_payment_status")
    async def payment_status(self, request: PravaShoppingWorkflowInput) -> PravaPaymentStatusResult:
        assert_credential_free_contract(request)
        try:
            result = await self._coordinator.payment_status(request)
        except Exception:
            raise ApplicationError(
                "Prava payment status unavailable",
                type="PRAVA_STATUS_REDACTED_FAILURE",
                non_retryable=False,
            ) from None
        assert_credential_free_contract(result)
        return result

    @activity.defn(name="sira.prava_shop_checkout")
    async def checkout(self, request: PravaShoppingWorkflowInput) -> PravaShoppingWorkflowResult:
        assert_credential_free_contract(request)
        try:
            result = await self._coordinator.checkout(request)
        except Exception:
            raise ApplicationError(
                "Prava checkout unavailable",
                type="PRAVA_CHECKOUT_REDACTED_FAILURE",
                non_retryable=False,
            ) from None
        assert_credential_free_contract(result)
        return result

    @activity.defn(name="sira.prava_checkout_failed")
    async def fail(self, request: PravaShoppingWorkflowInput) -> None:
        assert_credential_free_contract(request)
        try:
            await self._coordinator.fail(request, "APPROVAL_TIMEOUT")
        except Exception:
            raise ApplicationError(
                "Prava failure checkpoint unavailable",
                type="PRAVA_CHECKPOINT_REDACTED_FAILURE",
                non_retryable=False,
            ) from None


class CheckoutActivities:
    """Activities hold provider clients; workflow state never does."""

    def __init__(self, coordinator: CheckoutActivityCoordinator) -> None:
        self._coordinator = coordinator

    @activity.defn(name="sira.execute_isolated_checkout")
    async def execute_isolated_checkout(
        self,
        request: IsolatedCheckoutActivityInput,
    ) -> CheckoutActivityResult:
        assert_credential_free_contract(request)
        result: CheckoutActivityResult | None = None
        failure_type: str | None = None
        try:
            result = await self._coordinator.execute_isolated_checkout(request)
        except ProviderError as exc:
            failure_type = exc.code.value
        except Exception:
            failure_type = "CHECKOUT_ACTIVITY_REDACTED_FAILURE"
        if failure_type is not None:
            # Raise after leaving the except scope so Temporal cannot serialize an
            # original exception or request object as context. The checkout activity
            # itself is non-retrying; reconciliation decides the next safe action.
            raise ApplicationError(
                "isolated checkout activity failed",
                type=failure_type,
                non_retryable=True,
            ) from None
        if result is None:
            raise ApplicationError(
                "isolated checkout activity returned no result",
                type="CHECKOUT_ACTIVITY_REDACTED_FAILURE",
                non_retryable=True,
            ) from None
        assert_credential_free_contract(result)
        return result

    @activity.defn(name="sira.reconcile_checkout")
    async def reconcile_checkout(
        self,
        request: ReconcileActivityInput,
    ) -> CheckoutActivityResult:
        assert_credential_free_contract(request)
        result: CheckoutActivityResult | None = None
        failure_type: str | None = None
        non_retryable = False
        try:
            result = await self._coordinator.reconcile_checkout(request)
        except ProviderError as exc:
            failure_type = exc.code.value
            non_retryable = not exc.retryable
        except Exception:
            failure_type = "RECONCILIATION_ACTIVITY_REDACTED_FAILURE"
            non_retryable = True
        if failure_type is not None:
            raise ApplicationError(
                "checkout reconciliation activity failed",
                type=failure_type,
                non_retryable=non_retryable,
            ) from None
        if result is None:
            raise ApplicationError(
                "checkout reconciliation activity returned no result",
                type="RECONCILIATION_ACTIVITY_REDACTED_FAILURE",
                non_retryable=True,
            ) from None
        assert_credential_free_contract(result)
        return result

    @activity.defn(name="sira.verify_fulfillment")
    async def verify_fulfillment(
        self,
        request: VerifyFulfillmentActivityInput,
    ) -> FulfillmentActivityResult:
        assert_credential_free_contract(request)
        try:
            result = await self._coordinator.verify_fulfillment(request)
        except ProviderError as exc:
            raise ApplicationError(
                "fulfillment verification failed",
                type=exc.code.value,
                non_retryable=not exc.retryable,
            ) from None
        except Exception:
            raise ApplicationError(
                "fulfillment verification failed",
                type="FULFILLMENT_ACTIVITY_REDACTED_FAILURE",
                non_retryable=False,
            ) from None
        assert_credential_free_contract(result)
        return result

    @activity.defn(name="sira.fail_checkout_workflow")
    async def fail_checkout_workflow(
        self,
        request: WorkflowFailureActivityInput,
    ) -> None:
        assert_credential_free_contract(request)
        try:
            await self._coordinator.fail_checkout_workflow(request)
        except Exception:
            raise ApplicationError(
                "workflow failure checkpoint could not be persisted",
                type="WORKFLOW_FAILURE_CHECKPOINT_REDACTED_FAILURE",
                non_retryable=False,
            ) from None

    @activity.defn(name="sira.execute_refund")
    async def execute_refund(self, request: RefundActivityInput) -> RefundActivityResult:
        return await self._refund_activity(request, reconcile=False)

    @activity.defn(name="sira.reconcile_refund")
    async def reconcile_refund(self, request: RefundActivityInput) -> RefundActivityResult:
        return await self._refund_activity(request, reconcile=True)

    async def _refund_activity(
        self, request: RefundActivityInput, *, reconcile: bool
    ) -> RefundActivityResult:
        assert_credential_free_contract(request)
        result: RefundActivityResult | None = None
        failure_type: str | None = None
        non_retryable = False
        try:
            result = (
                await self._coordinator.reconcile_refund(request)
                if reconcile
                else await self._coordinator.execute_refund(request)
            )
        except ProviderError as exc:
            failure_type = exc.code.value
            non_retryable = not exc.retryable
        except Exception:
            failure_type = "REFUND_ACTIVITY_REDACTED_FAILURE"
            non_retryable = True
        if failure_type is not None:
            raise ApplicationError(
                "refund activity failed",
                type=failure_type,
                non_retryable=non_retryable,
            ) from None
        if result is None:
            raise ApplicationError(
                "refund activity returned no result",
                type="REFUND_ACTIVITY_REDACTED_FAILURE",
                non_retryable=True,
            ) from None
        assert_credential_free_contract(result)
        return result
