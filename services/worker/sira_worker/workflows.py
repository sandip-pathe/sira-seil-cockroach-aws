"""Deterministic Temporal purchase workflow using credential-free contracts only."""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from sira_worker.contracts import (
        CheckoutActivityResult,
        FulfillmentActivityResult,
        PravaPaymentStatusResult,
        PravaShoppingWorkflowInput,
        PravaShoppingWorkflowResult,
        PurchaseCheckoutWorkflowInput,
        PurchaseCheckoutWorkflowResult,
        PurchaseReversalWorkflowInput,
        PurchaseReversalWorkflowResult,
        ReconcileActivityInput,
        RefundActivityResult,
        SafeMerchantOutcome,
        VerifyFulfillmentActivityInput,
        WorkflowFailureActivityInput,
        assert_credential_free_contract,
    )

_RECONCILIATION_DELAYS_SECONDS = (0, 15, 60, 300, 900)


@workflow.defn(name="sira.prava_shop_checkout")
class PravaShoppingWorkflow:
    """Wait for Prava-hosted approval and place the quoted order without card data."""

    @workflow.run
    async def run(
        self, request: PravaShoppingWorkflowInput
    ) -> PravaShoppingWorkflowResult:
        assert_credential_free_contract(request)
        for attempt in range(60):
            status = await workflow.execute_activity(
                "sira.prava_payment_status",
                request,
                result_type=PravaPaymentStatusResult,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            normalized = status.status.upper()
            if normalized in {"COMPLETED", "APPROVED", "PAID", "SUCCESS"}:
                return await workflow.execute_activity(
                    "sira.prava_shop_checkout",
                    request,
                    result_type=PravaShoppingWorkflowResult,
                    start_to_close_timeout=timedelta(seconds=90),
                    retry_policy=RetryPolicy(maximum_attempts=3),
                )
            if normalized in {"FAILED", "DECLINED", "CANCELLED", "EXPIRED"}:
                return PravaShoppingWorkflowResult(
                    shopping_run_id=request.shopping_run_id,
                    status=normalized,
                    order_id=None,
                )
            if attempt < 59:
                await workflow.sleep(timedelta(seconds=10))
        await workflow.execute_activity(
            "sira.prava_checkout_failed",
            request,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        return PravaShoppingWorkflowResult(
            shopping_run_id=request.shopping_run_id,
            status="APPROVAL_TIMEOUT",
            order_id=None,
        )


@workflow.defn(name="sira.purchase_checkout")
class PurchaseCheckoutWorkflow:
    """Coordinate checkout without ever materializing a payment credential in history."""

    @workflow.run
    async def run(
        self,
        request: PurchaseCheckoutWorkflowInput,
    ) -> PurchaseCheckoutWorkflowResult:
        assert_credential_free_contract(request)
        # The credential operation is deliberately non-retrying.  An unknown dispatch
        # must reconcile by idempotency key before any new checkout can be considered.
        checkout = await workflow.execute_activity(
            "sira.execute_isolated_checkout",
            request.activity_input(),
            result_type=CheckoutActivityResult,
            start_to_close_timeout=timedelta(seconds=90),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        assert_credential_free_contract(checkout)
        if checkout.reconciliation_required:
            reconciliation_input = ReconcileActivityInput(
                organization_id=request.organization_id,
                purchase_intent_id=request.purchase_intent_id,
                intent_hash=request.intent_hash,
                prava_session_id=request.prava_session_id,
                merchant_adapter_id=request.merchant_adapter_id,
                idempotency_key=request.idempotency_key,
                transaction_reference=checkout.transaction_reference,
            )
            for delay_seconds in _RECONCILIATION_DELAYS_SECONDS:
                if delay_seconds:
                    await workflow.sleep(timedelta(seconds=delay_seconds))
                checkout = await workflow.execute_activity(
                    "sira.reconcile_checkout",
                    reconciliation_input,
                    result_type=CheckoutActivityResult,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=2),
                        backoff_coefficient=2.0,
                        maximum_interval=timedelta(seconds=30),
                        maximum_attempts=5,
                    ),
                )
                assert_credential_free_contract(checkout)
                if not checkout.reconciliation_required:
                    break
            if checkout.reconciliation_required:
                await workflow.execute_activity(
                    "sira.fail_checkout_workflow",
                    WorkflowFailureActivityInput(
                        organization_id=request.organization_id,
                        purchase_intent_id=request.purchase_intent_id,
                        safe_code="CHECKOUT_RECONCILIATION_INCOMPLETE",
                    ),
                    start_to_close_timeout=timedelta(seconds=15),
                    retry_policy=RetryPolicy(maximum_attempts=3),
                )
        if (
            checkout.merchant_outcome is SafeMerchantOutcome.APPROVED
            and checkout.provider_reported
            and not checkout.reconciliation_required
            and checkout.merchant_order_id is not None
        ):
            try:
                fulfillment = await workflow.execute_activity(
                    "sira.verify_fulfillment",
                    VerifyFulfillmentActivityInput(
                        organization_id=request.organization_id,
                        purchase_intent_id=request.purchase_intent_id,
                        merchant_order_id=checkout.merchant_order_id,
                    ),
                    result_type=FulfillmentActivityResult,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=2),
                        backoff_coefficient=2.0,
                        maximum_interval=timedelta(seconds=30),
                        maximum_attempts=5,
                    ),
                )
                assert_credential_free_contract(fulfillment)
            except Exception:
                await workflow.execute_activity(
                    "sira.fail_checkout_workflow",
                    WorkflowFailureActivityInput(
                        organization_id=request.organization_id,
                        purchase_intent_id=request.purchase_intent_id,
                        safe_code="FULFILLMENT_RETRY_EXHAUSTED",
                    ),
                    start_to_close_timeout=timedelta(seconds=15),
                    retry_policy=RetryPolicy(maximum_attempts=3),
                )
                raise
        return PurchaseCheckoutWorkflowResult(
            purchase_intent_id=request.purchase_intent_id,
            merchant_outcome=checkout.merchant_outcome,
            merchant_order_id=checkout.merchant_order_id,
            provider_reported=checkout.provider_reported,
            reconciliation_required=checkout.reconciliation_required,
        )


@workflow.defn(name="sira.purchase_reversal")
class PurchaseReversalWorkflow:
    """Request one idempotent refund, then reconcile without replaying the mutation."""

    @workflow.run
    async def run(
        self,
        request: PurchaseReversalWorkflowInput,
    ) -> PurchaseReversalWorkflowResult:
        assert_credential_free_contract(request)
        activity_input = request.activity_input()
        result = await workflow.execute_activity(
            "sira.execute_refund",
            activity_input,
            result_type=RefundActivityResult,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        assert_credential_free_contract(result)
        if result.reconciliation_required:
            for delay_seconds in _RECONCILIATION_DELAYS_SECONDS:
                if delay_seconds:
                    await workflow.sleep(timedelta(seconds=delay_seconds))
                result = await workflow.execute_activity(
                    "sira.reconcile_refund",
                    activity_input,
                    result_type=RefundActivityResult,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=2),
                        backoff_coefficient=2.0,
                        maximum_interval=timedelta(seconds=30),
                        maximum_attempts=5,
                    ),
                )
                assert_credential_free_contract(result)
                if not result.reconciliation_required:
                    break
        return PurchaseReversalWorkflowResult(
            reversal_id=result.reversal_id,
            status=result.status,
            refunded_amount=result.refunded_amount,
            currency=result.currency,
            provider_reference=result.provider_reference,
            entitlements_revoked=result.entitlements_revoked,
            reconciliation_required=result.reconciliation_required,
        )
