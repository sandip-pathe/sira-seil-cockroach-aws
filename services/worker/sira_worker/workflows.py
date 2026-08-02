"""Deterministic Temporal purchase workflow using credential-free contracts only."""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from sira_worker.contracts import (
        CheckoutActivityResult,
        FulfillmentActivityResult,
        PurchaseCheckoutWorkflowInput,
        PurchaseCheckoutWorkflowResult,
        ReconcileActivityInput,
        SafeMerchantOutcome,
        VerifyFulfillmentActivityInput,
        WorkflowFailureActivityInput,
        assert_credential_free_contract,
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
