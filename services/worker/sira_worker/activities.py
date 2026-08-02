"""Temporal activities wrapping credential-isolated provider coordination."""

from __future__ import annotations

from temporalio import activity
from temporalio.exceptions import ApplicationError

from integrations.errors import ProviderError
from sira_worker.contracts import (
    CheckoutActivityResult,
    IsolatedCheckoutActivityInput,
    ReconcileActivityInput,
    assert_credential_free_contract,
)
from sira_worker.ports import CheckoutActivityCoordinator


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
