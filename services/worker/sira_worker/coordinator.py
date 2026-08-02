"""Canonical checkout coordinator used only inside worker activities."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import select

from domain.enums import ReversalStatus
from domain.hashing import content_hash
from domain.state_machines import ReversalTransitionService
from integrations.common import AdapterMode
from integrations.errors import ProviderError, ProviderErrorCode
from integrations.merchants.models import (
    EntitlementVerificationRequest,
    EntitlementVerificationStatus,
    MerchantCheckoutOutcome,
    MerchantCheckoutRequest,
    MerchantOutcome,
    MerchantRefundRequest,
    MerchantRefundResult,
    RefundOutcomeStatus,
)
from integrations.merchants.protocols import (
    ControlledMerchantAdapter,
    ControlledMerchantReversalAdapter,
)
from integrations.prava.models import PravaCheckoutResult, PravaPaymentStatus
from integrations.prava.protocols import PravaHostedCheckoutProvider
from persistence.database import Database
from persistence.models import (
    ApprovalRequest,
    DecisionRecord,
    Entitlement,
    MerchantOrder,
    PaymentAttempt,
    PaymentSession,
    PurchaseIntent,
    PurchaseReversal,
    Receipt,
    StackPatch,
    WorkflowRun,
)
from persistence.repositories import WorkflowRepository, new_id
from sira_worker.contracts import (
    CheckoutActivityResult,
    FulfillmentActivityResult,
    IsolatedCheckoutActivityInput,
    ReconcileActivityInput,
    RefundActivityInput,
    RefundActivityResult,
    SafeFulfillmentStatus,
    SafeMerchantOutcome,
    SafeReversalStatus,
    VerifyFulfillmentActivityInput,
    WorkflowFailureActivityInput,
    assert_credential_free_contract,
)


class PersistentCheckoutCoordinator:
    """Load state, execute one credential operation, and persist only safe outcomes."""

    def __init__(
        self,
        *,
        database: Database,
        prava: PravaHostedCheckoutProvider,
        merchant: ControlledMerchantAdapter,
        reversal_merchant: ControlledMerchantReversalAdapter | None = None,
        merchant_adapter_id: str,
        environment: Literal["sandbox", "production"] = "sandbox",
    ) -> None:
        if not merchant_adapter_id.strip():
            raise ValueError("merchant_adapter_id is required")
        self._database = database
        self._prava = prava
        self._merchant = merchant
        self._reversal_merchant = reversal_merchant or (
            merchant if isinstance(merchant, ControlledMerchantReversalAdapter) else None
        )
        self._merchant_adapter_id = merchant_adapter_id
        self._environment = environment

    async def execute_isolated_checkout(
        self, request: IsolatedCheckoutActivityInput
    ) -> CheckoutActivityResult:
        assert_credential_free_contract(request)
        merchant_request, attempt_id = await self._prepare_attempt(request)
        try:
            result = await self._prava.execute_isolated_checkout(
                session_id=request.prava_session_id,
                request=merchant_request,
                merchant=self._merchant,
            )
        except Exception:
            # Once an attempt is committed, any provider-side exception is an
            # uncertain dispatch. Return a credential-free recovery result so the
            # durable workflow reconciles instead of stranding CHECKOUT_PENDING.
            result = PravaCheckoutResult(
                session_id=request.prava_session_id,
                prava_order_id=merchant_request.prava_order_id,
                transaction_reference=f"reconcile:{attempt_id}",
                merchant=MerchantCheckoutOutcome(
                    outcome=MerchantOutcome.UNKNOWN,
                    merchant_order_id=None,
                    authorization_code=None,
                    response_code=None,
                    adapter=self._merchant.descriptor,
                    provider_confirmed=False,
                ),
                provider_reported=False,
                final_status=PravaPaymentStatus.AWAITING_RESULT,
                reconciliation_required=True,
                adapter=self._prava.descriptor,
            )
        output = await self._persist_checkout_result(
            organization_id=request.organization_id,
            intent_id=request.purchase_intent_id,
            attempt_id=attempt_id,
            idempotency_key=request.idempotency_key,
            result=result,
        )
        if (
            not output.reconciliation_required
            and output.merchant_outcome is not SafeMerchantOutcome.APPROVED
        ):
            await self._finish_workflow_run(
                organization_id=request.organization_id,
                intent_id=request.purchase_intent_id,
                status="COMPLETED",
                safe_error_code=None,
                message=f"Checkout finished with {output.merchant_outcome.value}",
            )
        assert_credential_free_contract(output)
        return output

    async def reconcile_checkout(self, request: ReconcileActivityInput) -> CheckoutActivityResult:
        assert_credential_free_contract(request)
        merchant_request, attempt_id = await self._load_reconciliation_state(request)
        merchant_outcome = await self._merchant.reconcile_order(merchant_request)
        provider_reported = False
        reconciliation_required = merchant_outcome.outcome is MerchantOutcome.UNKNOWN
        final_status = PravaPaymentStatus.AWAITING_RESULT
        if merchant_outcome.outcome is not MerchantOutcome.UNKNOWN:
            report = await self._prava.report_known_outcome(
                session_id=request.prava_session_id,
                transaction_reference=request.transaction_reference,
                outcome=merchant_outcome,
            )
            provider_reported = report.provider_confirmed
            reconciliation_required = not report.provider_confirmed
            final_status = (
                PravaPaymentStatus.COMPLETED
                if merchant_outcome.outcome is MerchantOutcome.APPROVED
                else PravaPaymentStatus.FAILED
            )
        result = PravaCheckoutResult(
            session_id=request.prava_session_id,
            prava_order_id=merchant_request.prava_order_id,
            transaction_reference=request.transaction_reference,
            merchant=merchant_outcome,
            provider_reported=provider_reported,
            final_status=final_status,
            reconciliation_required=reconciliation_required,
            adapter=self._prava.descriptor,
        )
        output = await self._persist_checkout_result(
            organization_id=request.organization_id,
            intent_id=request.purchase_intent_id,
            attempt_id=attempt_id,
            idempotency_key=request.idempotency_key,
            result=result,
        )
        if (
            not output.reconciliation_required
            and output.merchant_outcome is not SafeMerchantOutcome.APPROVED
        ):
            await self._finish_workflow_run(
                organization_id=request.organization_id,
                intent_id=request.purchase_intent_id,
                status="COMPLETED",
                safe_error_code=None,
                message=f"Checkout finished with {output.merchant_outcome.value}",
            )
        assert_credential_free_contract(output)
        return output

    async def execute_refund(self, request: RefundActivityInput) -> RefundActivityResult:
        assert_credential_free_contract(request)
        provider = self._require_reversal_provider()
        merchant_request = await self._load_refund_state(request)
        result: MerchantRefundResult | None = None
        uncertain = False
        try:
            result = await provider.request_refund(merchant_request)
        except ProviderError as exc:
            if not exc.retryable and exc.code is not ProviderErrorCode.REVERSAL_UNCERTAIN:
                raise
            uncertain = True
        if uncertain or result is None:
            result = MerchantRefundResult(
                status=RefundOutcomeStatus.UNKNOWN,
                provider_refund_id=None,
                refunded_amount="0.00",
                currency=merchant_request.currency,
                entitlements_revoked=False,
                adapter=provider.descriptor,
                provider_confirmed=False,
            )
        return await self._persist_refund_result(request, result)

    async def reconcile_refund(self, request: RefundActivityInput) -> RefundActivityResult:
        assert_credential_free_contract(request)
        provider = self._require_reversal_provider()
        merchant_request = await self._load_refund_state(request)
        result = await provider.reconcile_refund(merchant_request)
        return await self._persist_refund_result(request, result)

    async def verify_fulfillment(
        self, request: VerifyFulfillmentActivityInput
    ) -> FulfillmentActivityResult:
        assert_credential_free_contract(request)
        status = await self._verify_fulfillment(
            organization_id=request.organization_id,
            intent_id=request.purchase_intent_id,
            merchant_order_id=request.merchant_order_id,
        )
        if status is SafeFulfillmentStatus.VERIFIED:
            await self._finish_workflow_run(
                organization_id=request.organization_id,
                intent_id=request.purchase_intent_id,
                status="COMPLETED",
                safe_error_code=None,
                message="Payment and fulfillment verified",
            )
            return FulfillmentActivityResult(request.purchase_intent_id, status)
        if status is SafeFulfillmentStatus.FAILED_FINAL:
            await self._finish_workflow_run(
                organization_id=request.organization_id,
                intent_id=request.purchase_intent_id,
                status="FAILED",
                safe_error_code="FULFILLMENT_FAILED_FINAL",
                message="Fulfillment verification failed",
            )
        raise ProviderError(
            provider="controlled_merchant",
            operation="verify_fulfillment",
            code=ProviderErrorCode.INVALID_STATE
            if status is SafeFulfillmentStatus.FAILED_FINAL
            else ProviderErrorCode.UNAVAILABLE,
            retryable=status is not SafeFulfillmentStatus.FAILED_FINAL,
        ) from None

    async def fail_checkout_workflow(self, request: WorkflowFailureActivityInput) -> None:
        assert_credential_free_contract(request)
        await self._finish_workflow_run(
            organization_id=request.organization_id,
            intent_id=request.purchase_intent_id,
            status="FAILED",
            safe_error_code=request.safe_code,
            message="Checkout workflow stopped after safe retry limits",
        )

    async def _prepare_attempt(
        self, request: IsolatedCheckoutActivityInput
    ) -> tuple[MerchantCheckoutRequest, str]:
        if request.merchant_adapter_id != self._merchant_adapter_id:
            raise ProviderError(
                provider="controlled_merchant",
                operation="prepare_checkout",
                code=ProviderErrorCode.CONFIGURATION_INVALID,
                retryable=False,
            ) from None
        expired = False
        merchant_request: MerchantCheckoutRequest | None = None
        attempt_id: str | None = None
        async with self._database.transaction(request.organization_id) as session:
            repository = WorkflowRepository(session, request.organization_id)
            intent = await repository.get_purchase_intent(request.purchase_intent_id, lock=True)
            if intent.intent_hash != request.intent_hash or intent.approval_status != "APPROVED":
                raise ProviderError(
                    provider="prava",
                    operation="prepare_checkout",
                    code=ProviderErrorCode.INVALID_STATE,
                    retryable=False,
                ) from None
            approval = (
                await session.execute(
                    select(ApprovalRequest)
                    .where(
                        ApprovalRequest.organization_id == request.organization_id,
                        ApprovalRequest.purchase_intent_id == intent.id,
                        ApprovalRequest.intent_hash == intent.intent_hash,
                        ApprovalRequest.status == "APPROVED",
                    )
                    .order_by(ApprovalRequest.created_at.desc())
                    .limit(1)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if approval is None:
                raise ProviderError(
                    provider="prava",
                    operation="prepare_checkout",
                    code=ProviderErrorCode.INVALID_STATE,
                    retryable=False,
                ) from None
            if intent.payment_status != "CARDHOLDER_PENDING":
                raise ProviderError(
                    provider="prava",
                    operation="prepare_checkout",
                    code=ProviderErrorCode.INVALID_STATE,
                    retryable=False,
                ) from None
            payment_session = (
                await session.execute(
                    select(PaymentSession).where(
                        PaymentSession.organization_id == request.organization_id,
                        PaymentSession.purchase_intent_id == intent.id,
                        PaymentSession.provider_session_id == request.prava_session_id,
                    )
                )
            ).scalar_one_or_none()
            if payment_session is None:
                raise ProviderError(
                    provider="prava",
                    operation="prepare_checkout",
                    code=ProviderErrorCode.NOT_FOUND,
                    retryable=False,
                ) from None
            if payment_session.status != "CARDHOLDER_PENDING":
                raise ProviderError(
                    provider="prava",
                    operation="prepare_checkout",
                    code=ProviderErrorCode.INVALID_STATE,
                    retryable=False,
                ) from None

            existing = (
                await session.execute(
                    select(PaymentAttempt).where(
                        PaymentAttempt.organization_id == request.organization_id,
                        PaymentAttempt.purchase_intent_id == intent.id,
                        PaymentAttempt.closed_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                raise ProviderError(
                    provider="prava",
                    operation="prepare_checkout",
                    code=ProviderErrorCode.CHECKOUT_UNCERTAIN,
                    retryable=False,
                ) from None

            # This is the last check before the attempt and dispatch transition are
            # created; both canonical deadlines must still be live at this instant.
            now = datetime.now(UTC)
            expiry_reason: str | None = None
            if self._as_utc(intent.quote_expires_at) <= now:
                expiry_reason = "QUOTE_EXPIRED_BEFORE_CHECKOUT"
            elif self._as_utc(approval.expires_at) <= now:
                expiry_reason = "APPROVAL_EXPIRED_BEFORE_CHECKOUT"
            elif self._as_utc(payment_session.expires_at) <= now:
                expiry_reason = "PAYMENT_SESSION_EXPIRED_BEFORE_CHECKOUT"

            if expiry_reason is not None:
                if expiry_reason == "APPROVAL_EXPIRED_BEFORE_CHECKOUT":
                    approval.status = "EXPIRED"
                    intent.approval_status = "EXPIRED"
                payment_session.status = "EXPIRED"
                await repository.transition_purchase_intent(
                    intent_id=intent.id,
                    state_field="payment_status",
                    allowed_from={"CARDHOLDER_PENDING"},
                    to_state="EXPIRED",
                    event_key=f"checkout-expired:{payment_session.id}:{expiry_reason.lower()}",
                    actor_type="worker",
                    actor_id="checkout_coordinator",
                    reason_code=expiry_reason,
                    payload_hash=content_hash(
                        {
                            "payment_session_id": payment_session.id,
                            "approval_expires_at": self._as_utc(
                                approval.expires_at
                            ).isoformat(),
                            "quote_expires_at": self._as_utc(intent.quote_expires_at).isoformat(),
                            "session_expires_at": self._as_utc(
                                payment_session.expires_at
                            ).isoformat(),
                            "reason": expiry_reason,
                        }
                    ),
                )
                expired = True
            else:
                attempt_id = new_id("payatt")
                session.add(
                    PaymentAttempt(
                        id=attempt_id,
                        organization_id=request.organization_id,
                        purchase_intent_id=intent.id,
                        payment_session_id=payment_session.id,
                        merchant_outcome=None,
                        external_order_id=None,
                        closed_at=None,
                    )
                )
                payment_session.status = "CHECKOUT_PENDING"
                await repository.transition_purchase_intent(
                    intent_id=intent.id,
                    state_field="payment_status",
                    allowed_from={"CARDHOLDER_PENDING"},
                    to_state="CHECKOUT_PENDING",
                    event_key=f"checkout-dispatched:{attempt_id}",
                    actor_type="worker",
                    actor_id="checkout_coordinator",
                    reason_code="ISOLATED_CHECKOUT_DISPATCHED",
                    payload_hash=content_hash(
                        {
                            "attempt_id": attempt_id,
                            "provider_session_id": request.prava_session_id,
                            "idempotency_key": request.idempotency_key,
                        }
                    ),
                    attempt_id=attempt_id,
                )
                merchant_request = self._merchant_request(
                    intent, payment_session, request.idempotency_key
                )

        if expired:
            await self._finish_workflow_run(
                organization_id=request.organization_id,
                intent_id=request.purchase_intent_id,
                status="FAILED",
                safe_error_code="CHECKOUT_AUTHORITY_EXPIRED",
                message="Checkout authority expired before dispatch",
            )
            raise ProviderError(
                provider="prava",
                operation="prepare_checkout",
                code=ProviderErrorCode.INVALID_STATE,
                retryable=False,
            ) from None
        if merchant_request is None or attempt_id is None:
            raise RuntimeError("checkout preparation completed without a dispatchable attempt")
        return merchant_request, attempt_id

    async def _finish_workflow_run(
        self,
        *,
        organization_id: str,
        intent_id: str,
        status: Literal["COMPLETED", "FAILED"],
        safe_error_code: str | None,
        message: str,
    ) -> None:
        workflow_id = f"wf_checkout_{intent_id}"
        async with self._database.transaction(organization_id) as session:
            workflow = (
                await session.execute(
                    select(WorkflowRun)
                    .where(
                        WorkflowRun.id == workflow_id,
                        WorkflowRun.organization_id == organization_id,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if workflow is None or workflow.status in {"COMPLETED", "FAILED"}:
                return
            workflow.status = status
            workflow.safe_error_code = safe_error_code
            workflow.event_log = [
                *workflow.event_log,
                {
                    "id": str(len(workflow.event_log) + 1),
                    "status": status,
                    "message": message,
                },
            ]

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _require_reversal_provider(self) -> ControlledMerchantReversalAdapter:
        if self._reversal_merchant is None:
            raise ProviderError(
                provider="controlled_merchant",
                operation="refund",
                code=ProviderErrorCode.CONFIGURATION_INVALID,
                retryable=False,
            ) from None
        return self._reversal_merchant

    async def _load_refund_state(
        self, request: RefundActivityInput
    ) -> MerchantRefundRequest:
        async with self._database.transaction(request.organization_id) as session:
            reversal = (
                await session.execute(
                    select(PurchaseReversal)
                    .where(
                        PurchaseReversal.id == request.reversal_id,
                        PurchaseReversal.organization_id == request.organization_id,
                        PurchaseReversal.purchase_intent_id == request.purchase_intent_id,
                    )
                    .with_for_update()
                )
            ).scalar_one()
            intent = (
                await session.execute(
                    select(PurchaseIntent)
                    .where(
                        PurchaseIntent.id == request.purchase_intent_id,
                        PurchaseIntent.organization_id == request.organization_id,
                    )
                    .with_for_update()
                )
            ).scalar_one()
            if (
                intent.intent_hash != request.intent_hash
                or reversal.intent_hash != request.intent_hash
                or reversal.currency != intent.currency
                or reversal.status
                not in {"REQUESTED", "PROVIDER_PENDING", "PARTIALLY_REFUNDED", "FAILED_RETRYABLE"}
            ):
                raise ProviderError(
                    provider="controlled_merchant",
                    operation="refund",
                    code=ProviderErrorCode.INVALID_STATE,
                    retryable=False,
                ) from None
            return MerchantRefundRequest(
                merchant_order_id=reversal.merchant_order_id,
                idempotency_key=request.idempotency_key,
                amount=f"{reversal.requested_amount:.2f}",
                currency=reversal.currency,
                reason_code=reversal.reason_code,
            )

    async def _persist_refund_result(
        self,
        request: RefundActivityInput,
        result: MerchantRefundResult,
    ) -> RefundActivityResult:
        async with self._database.transaction(request.organization_id) as session:
            repository = WorkflowRepository(session, request.organization_id)
            reversal = (
                await session.execute(
                    select(PurchaseReversal)
                    .where(
                        PurchaseReversal.id == request.reversal_id,
                        PurchaseReversal.organization_id == request.organization_id,
                    )
                    .with_for_update()
                )
            ).scalar_one()
            intent = await repository.get_purchase_intent(
                request.purchase_intent_id, lock=True
            )
            refunded_amount = Decimal(result.refunded_amount)
            if (
                result.currency != reversal.currency
                or refunded_amount > reversal.requested_amount
                or (result.provider_confirmed and result.adapter.mode is not AdapterMode.PRODUCTION)
                or (
                    result.status
                    in {
                        RefundOutcomeStatus.PARTIALLY_REFUNDED,
                        RefundOutcomeStatus.REFUNDED,
                        RefundOutcomeStatus.REJECTED,
                    }
                    and not result.provider_confirmed
                )
            ):
                raise ProviderError(
                    provider="controlled_merchant",
                    operation="refund",
                    code=ProviderErrorCode.INVALID_RESPONSE,
                    retryable=False,
                ) from None
            reconciliation_required = False
            if result.status in {RefundOutcomeStatus.PENDING, RefundOutcomeStatus.UNKNOWN}:
                status = "PROVIDER_PENDING"
                reconciliation_required = True
            elif result.status is RefundOutcomeStatus.PARTIALLY_REFUNDED:
                status = "PARTIALLY_REFUNDED"
                reconciliation_required = True
            elif result.status is RefundOutcomeStatus.REJECTED:
                status = "REJECTED"
            elif (
                refunded_amount == reversal.requested_amount
                and (
                    intent.fulfillment_status != "VERIFIED"
                    or result.entitlements_revoked
                )
            ):
                status = "REFUNDED"
            else:
                status = "COMPENSATION_REQUIRED"
            if reversal.status != status:
                ReversalTransitionService.transition(
                    ReversalStatus(reversal.status), ReversalStatus(status)
                )
                reversal.status = status
            reversal.refunded_amount = refunded_amount
            reversal.provider_reference = result.provider_refund_id
            reversal.provider_confirmed = result.provider_confirmed
            reversal.safe_error_code = (
                "ENTITLEMENT_REVOCATION_REQUIRED"
                if status == "COMPENSATION_REQUIRED"
                else None
            )
            if not reconciliation_required:
                reversal.completed_at = datetime.now(UTC)
            if status == "REFUNDED" and result.entitlements_revoked:
                if intent.fulfillment_status == "VERIFIED":
                    await repository.transition_purchase_intent(
                        intent_id=intent.id,
                        state_field="fulfillment_status",
                        allowed_from={"VERIFIED"},
                        to_state="REVOKED",
                        event_key=f"refund-entitlements-revoked:{reversal.id}",
                        actor_type="worker",
                        actor_id="refund_coordinator",
                        reason_code="REFUND_ENTITLEMENTS_REVOKED",
                        payload_hash=content_hash(
                            {
                                "reversal_id": reversal.id,
                                "provider_reference": result.provider_refund_id,
                            }
                        ),
                    )
            result_hash = content_hash(
                {
                    "reversal_id": reversal.id,
                    "status": status,
                    "refunded_amount": f"{refunded_amount:.2f}",
                    "provider_reference": result.provider_refund_id,
                    "provider_confirmed": result.provider_confirmed,
                    "entitlements_revoked": result.entitlements_revoked,
                }
            )
            await repository.add_outbox(
                aggregate_type="purchase_reversal",
                aggregate_id=reversal.id,
                event_type="purchase_reversal.updated",
                event_key=f"purchase-reversal-updated:{result_hash}",
                payload={
                    "reversal_id": reversal.id,
                    "purchase_intent_id": intent.id,
                    "status": status,
                    "refunded_amount": f"{refunded_amount:.2f}",
                    "currency": reversal.currency,
                    "result_hash": result_hash,
                },
            )
            workflow = (
                await session.execute(
                    select(WorkflowRun)
                    .where(
                        WorkflowRun.organization_id == request.organization_id,
                        WorkflowRun.aggregate_type == "purchase_reversal",
                        WorkflowRun.aggregate_id == reversal.id,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if workflow is not None:
                workflow.status = "RUNNING" if reconciliation_required else "COMPLETED"
                workflow.result_reference = reversal.id
                workflow.safe_error_code = reversal.safe_error_code
                workflow.event_log = [
                    *workflow.event_log,
                    {
                        "id": str(len(workflow.event_log) + 1),
                        "status": workflow.status,
                        "message": "Refund state reconciled",
                    },
                ]
            output = RefundActivityResult(
                reversal_id=reversal.id,
                status=SafeReversalStatus(status),
                refunded_amount=f"{refunded_amount:.2f}",
                currency=reversal.currency,
                provider_reference=result.provider_refund_id,
                entitlements_revoked=result.entitlements_revoked,
                reconciliation_required=reconciliation_required,
            )
            assert_credential_free_contract(output)
            return output

    async def _load_reconciliation_state(
        self, request: ReconcileActivityInput
    ) -> tuple[MerchantCheckoutRequest, str]:
        async with self._database.transaction(request.organization_id) as session:
            repository = WorkflowRepository(session, request.organization_id)
            intent = await repository.get_purchase_intent(request.purchase_intent_id, lock=True)
            if intent.intent_hash != request.intent_hash:
                raise ProviderError(
                    provider="prava",
                    operation="reconcile_checkout",
                    code=ProviderErrorCode.INVALID_STATE,
                    retryable=False,
                ) from None
            payment_session = (
                await session.execute(
                    select(PaymentSession).where(
                        PaymentSession.organization_id == request.organization_id,
                        PaymentSession.purchase_intent_id == intent.id,
                        PaymentSession.provider_session_id == request.prava_session_id,
                    )
                )
            ).scalar_one()
            attempt = (
                await session.execute(
                    select(PaymentAttempt)
                    .where(
                        PaymentAttempt.organization_id == request.organization_id,
                        PaymentAttempt.purchase_intent_id == intent.id,
                    )
                    .order_by(PaymentAttempt.created_at.desc())
                    .limit(1)
                )
            ).scalar_one()
            return self._merchant_request(
                intent, payment_session, request.idempotency_key
            ), attempt.id

    @staticmethod
    def _merchant_request(
        intent: PurchaseIntent,
        payment_session: PaymentSession,
        idempotency_key: str,
    ) -> MerchantCheckoutRequest:
        return MerchantCheckoutRequest(
            purchase_intent_id=intent.id,
            prava_order_id=payment_session.provider_order_id,
            idempotency_key=idempotency_key,
            merchant_url=intent.merchant_url,
            amount=f"{intent.amount:.2f}",
            currency=intent.currency,
        )

    async def _persist_checkout_result(
        self,
        *,
        organization_id: str,
        intent_id: str,
        attempt_id: str,
        idempotency_key: str,
        result: PravaCheckoutResult,
    ) -> CheckoutActivityResult:
        async with self._database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            intent = await repository.get_purchase_intent(intent_id, lock=True)
            attempt = (
                await session.execute(
                    select(PaymentAttempt)
                    .where(
                        PaymentAttempt.id == attempt_id,
                        PaymentAttempt.organization_id == organization_id,
                    )
                    .with_for_update()
                )
            ).scalar_one()
            payment_session = (
                await session.execute(
                    select(PaymentSession)
                    .where(
                        PaymentSession.id == attempt.payment_session_id,
                        PaymentSession.organization_id == organization_id,
                    )
                    .with_for_update()
                )
            ).scalar_one()
            outcome = result.merchant.outcome
            attempt.merchant_outcome = outcome.value
            attempt.external_order_id = result.merchant.merchant_order_id
            if outcome is not MerchantOutcome.UNKNOWN and not result.reconciliation_required:
                attempt.closed_at = datetime.now(UTC)

            if result.merchant.merchant_order_id is not None:
                existing_order = (
                    await session.execute(
                        select(MerchantOrder).where(
                            MerchantOrder.organization_id == organization_id,
                            MerchantOrder.merchant_adapter_id == self._merchant_adapter_id,
                            MerchantOrder.idempotency_key == idempotency_key,
                        )
                    )
                ).scalar_one_or_none()
                if existing_order is None:
                    session.add(
                        MerchantOrder(
                            id=new_id("mord"),
                            organization_id=organization_id,
                            purchase_intent_id=intent_id,
                            merchant_adapter_id=self._merchant_adapter_id,
                            idempotency_key=idempotency_key,
                            external_order_id=result.merchant.merchant_order_id,
                            status=outcome.value,
                            amount=intent.amount,
                            currency=intent.currency,
                            safe_payload={
                                "provider_confirmed": result.merchant.provider_confirmed,
                                "response_code": result.merchant.response_code,
                            },
                        )
                    )

            common = {
                "intent_id": intent_id,
                "state_field": "payment_status",
                "actor_type": "worker",
                "actor_id": "checkout_coordinator",
                "attempt_id": attempt_id,
            }
            safe_hash = content_hash(
                {
                    "outcome": outcome.value,
                    "transaction_reference": result.transaction_reference,
                    "provider_reported": result.provider_reported,
                    "reconciliation_required": result.reconciliation_required,
                }
            )
            if outcome is MerchantOutcome.UNKNOWN:
                payment_session.status = "UNCERTAIN"
                await repository.transition_purchase_intent(
                    **common,
                    allowed_from={"CHECKOUT_PENDING", "UNCERTAIN"},
                    to_state="UNCERTAIN",
                    event_key=f"checkout-uncertain:{attempt_id}",
                    reason_code="MERCHANT_OUTCOME_UNKNOWN",
                    payload_hash=safe_hash,
                    provider_event_ref=(
                        None
                        if result.transaction_reference.startswith("reconcile:")
                        else result.transaction_reference
                    ),
                )
            elif outcome is MerchantOutcome.DECLINED:
                payment_session.status = "DECLINED"
                await repository.transition_purchase_intent(
                    **common,
                    allowed_from={"CHECKOUT_PENDING", "UNCERTAIN"},
                    to_state="DECLINED",
                    event_key=f"checkout-declined:{attempt_id}",
                    reason_code="MERCHANT_DECLINED",
                    payload_hash=safe_hash,
                    provider_event_ref=result.transaction_reference,
                )
            else:
                if intent.payment_status in {"CHECKOUT_PENDING", "UNCERTAIN"}:
                    await repository.transition_purchase_intent(
                        **common,
                        allowed_from={"CHECKOUT_PENDING", "UNCERTAIN"},
                        to_state="MERCHANT_APPROVED",
                        event_key=f"merchant-approved:{attempt_id}",
                        reason_code="MERCHANT_APPROVED",
                        payload_hash=safe_hash,
                    )
                target = "PRAVA_COMPLETED" if result.provider_reported else "REPORTING"
                payment_session.status = target
                await repository.transition_purchase_intent(
                    **common,
                    allowed_from={"MERCHANT_APPROVED", "REPORTING"},
                    to_state=target,
                    event_key=f"prava-report:{attempt_id}:{target.lower()}",
                    reason_code=(
                        "PRAVA_REPORT_CONFIRMED"
                        if result.provider_reported
                        else "PRAVA_REPORT_RECONCILIATION_REQUIRED"
                    ),
                    payload_hash=safe_hash,
                    provider_event_ref=result.transaction_reference,
                )

            return CheckoutActivityResult(
                purchase_intent_id=intent_id,
                prava_session_id=result.session_id,
                prava_order_id=result.prava_order_id,
                transaction_reference=result.transaction_reference,
                merchant_outcome=SafeMerchantOutcome(outcome.value),
                merchant_order_id=result.merchant.merchant_order_id,
                provider_reported=result.provider_reported,
                reconciliation_required=result.reconciliation_required,
            )

    async def _verify_fulfillment(
        self, *, organization_id: str, intent_id: str, merchant_order_id: str
    ) -> SafeFulfillmentStatus:
        async with self._database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            intent = await repository.get_purchase_intent(intent_id, lock=True)
            if intent.fulfillment_status == "VERIFIED":
                return SafeFulfillmentStatus.VERIFIED
            if intent.fulfillment_status == "NOT_STARTED":
                await repository.transition_purchase_intent(
                    intent_id=intent_id,
                    state_field="fulfillment_status",
                    allowed_from={"NOT_STARTED"},
                    to_state="PENDING",
                    event_key=f"fulfillment-started:{merchant_order_id}",
                    actor_type="worker",
                    actor_id="checkout_coordinator",
                    reason_code="ENTITLEMENT_VERIFICATION_STARTED",
                    payload_hash=content_hash({"merchant_order_id": merchant_order_id}),
                )
            expected = deepcopy(intent.expected_fulfillments)

        observations: list[tuple[dict[str, Any], Any]] = []
        for item in expected:
            method = str(item.get("verification_method", ""))
            result = await self._merchant.verify_entitlements(
                EntitlementVerificationRequest(
                    merchant_order_id=merchant_order_id,
                    entitlement_type=str(item["type"]),
                    minimum_quantity=int(item["minimum_quantity"]),
                    subject_id=(
                        organization_id if item.get("subject_type") == "organization" else None
                    ),
                    require_access_probe="access_probe" in method,
                )
            )
            observations.append((item, result))

        all_verified = all(
            result.status is EntitlementVerificationStatus.VERIFIED for _, result in observations
        )
        any_observed = any(result.observed_quantity > 0 for _, result in observations)
        any_final = any(
            result.status is EntitlementVerificationStatus.FAILED_FINAL
            for _, result in observations
        )
        target = (
            "VERIFIED"
            if all_verified
            else "FAILED_FINAL"
            if any_final
            else "PARTIAL"
            if any_observed
            else "FAILED_RETRYABLE"
        )
        async with self._database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            intent = await repository.get_purchase_intent(intent_id, lock=True)
            order = (
                await session.execute(
                    select(MerchantOrder).where(
                        MerchantOrder.organization_id == organization_id,
                        MerchantOrder.purchase_intent_id == intent_id,
                        MerchantOrder.external_order_id == merchant_order_id,
                    )
                )
            ).scalar_one()
            entitlement_ids: list[str] = []
            for item, result in observations:
                for external_id in result.external_entitlement_ids:
                    existing = (
                        await session.execute(
                            select(Entitlement).where(
                                Entitlement.organization_id == organization_id,
                                Entitlement.fulfillment_adapter_id == self._merchant_adapter_id,
                                Entitlement.external_entitlement_id == external_id,
                            )
                        )
                    ).scalar_one_or_none()
                    if existing is None:
                        internal_id = new_id("ent")
                        session.add(
                            Entitlement(
                                id=internal_id,
                                organization_id=organization_id,
                                purchase_intent_id=intent_id,
                                merchant_order_id=order.id,
                                fulfillment_adapter_id=self._merchant_adapter_id,
                                external_entitlement_id=external_id,
                                fulfillment_item_id=str(item["fulfillment_item_id"]),
                                entitlement_type=str(item["type"]),
                                subject_type=str(item["subject_type"]),
                                subject_id=organization_id,
                                quantity=result.observed_quantity,
                                verification_status=result.status.value,
                                safe_payload={
                                    "provider_confirmed": result.provider_confirmed,
                                    "access_probe_verified": result.access_probe_verified,
                                },
                            )
                        )
                        entitlement_ids.append(internal_id)
                    else:
                        entitlement_ids.append(existing.id)
            await repository.transition_purchase_intent(
                intent_id=intent_id,
                state_field="fulfillment_status",
                allowed_from={"PENDING", "PARTIAL", "FAILED_RETRYABLE"},
                to_state=target,
                event_key=f"fulfillment-result:{merchant_order_id}:{target.lower()}",
                actor_type="worker",
                actor_id="checkout_coordinator",
                reason_code=f"ENTITLEMENT_{target}",
                payload_hash=content_hash(
                    {"merchant_order_id": merchant_order_id, "status": target}
                ),
            )
            if target == "VERIFIED":
                await self._create_receipt(
                    session=session,
                    organization_id=organization_id,
                    intent=intent,
                    order=order,
                    entitlement_ids=entitlement_ids,
                )
        return SafeFulfillmentStatus(target)

    async def _create_receipt(
        self,
        *,
        session: Any,
        organization_id: str,
        intent: PurchaseIntent,
        order: MerchantOrder,
        entitlement_ids: list[str],
    ) -> None:
        existing = (
            await session.execute(
                select(Receipt).where(
                    Receipt.organization_id == organization_id,
                    Receipt.purchase_intent_id == intent.id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return
        decision = (
            await session.execute(
                select(DecisionRecord).where(
                    DecisionRecord.organization_id == organization_id,
                    DecisionRecord.id == intent.decision_id,
                )
            )
        ).scalar_one()
        approval = (
            await session.execute(
                select(ApprovalRequest)
                .where(
                    ApprovalRequest.organization_id == organization_id,
                    ApprovalRequest.purchase_intent_id == intent.id,
                    ApprovalRequest.status == "APPROVED",
                )
                .order_by(ApprovalRequest.created_at.desc())
                .limit(1)
            )
        ).scalar_one()
        payment_session = (
            await session.execute(
                select(PaymentSession)
                .where(
                    PaymentSession.organization_id == organization_id,
                    PaymentSession.purchase_intent_id == intent.id,
                )
                .order_by(PaymentSession.created_at.desc())
                .limit(1)
            )
        ).scalar_one()
        patch = (
            await session.execute(
                select(StackPatch).where(
                    StackPatch.organization_id == organization_id,
                    StackPatch.id == intent.stack_patch_id,
                )
            )
        ).scalar_one_or_none()
        if patch is None or patch.state not in {"PROPOSED", "APPROVED", "STAGED"}:
            raise ProviderError(
                provider="stackfile",
                operation="stage_purchase_patch",
                code=ProviderErrorCode.INVALID_STATE,
                retryable=False,
            ) from None
        patch.state = "STAGED"
        patch_payload = {**patch.payload, "status": "STAGED"}
        patch_payload["content_hash"] = content_hash(
            {key: value for key, value in patch_payload.items() if key != "content_hash"}
        )
        patch.payload = patch_payload
        patch.patch_hash = patch_payload["content_hash"]

        merchant_payload = intent.payload.get("merchant")
        if (
            payment_session.provider_order_id is None
            or not isinstance(merchant_payload, dict)
            or not isinstance(merchant_payload.get("country"), str)
        ):
            raise ProviderError(
                provider="prava",
                operation="create_receipt",
                code=ProviderErrorCode.INVALID_STATE,
                retryable=False,
            ) from None
        environment, adapter_label, production_success = self._receipt_provenance()
        receipt_id = new_id("receipt")
        payload = {
            "schema_version": "1.0.0",
            "receipt_id": receipt_id,
            "purchase_id": new_id("purchase"),
            "purchase_intent_id": intent.id,
            "request_id": decision.purchase_request_id,
            "decision_id": decision.id,
            "decision_version": decision.version,
            "decision_hash": decision.decision_hash,
            "selection_id": intent.payload["selection_id"],
            "solution_plan_id": intent.solution_plan_id,
            "pack_id": intent.pack_id,
            "pack_version": intent.pack_version,
            "offer_id": intent.offer_id,
            "offer_version": intent.offer_version,
            "quote_id": intent.quote_id,
            "quote_version": intent.quote_version,
            "approval_request_id": approval.id,
            "approval_intent_hash": approval.intent_hash,
            "prava_session_reference": payment_session.provider_session_id,
            "prava_order_reference": payment_session.provider_order_id,
            "merchant_order_id": order.external_order_id,
            "merchant": {
                "merchant_id": intent.merchant_id,
                "name": intent.merchant_name,
                "url": intent.merchant_url,
                "country": merchant_payload["country"],
            },
            "line_items": deepcopy(intent.payload["line_items"]),
            "merchant_subtotal": str(intent.payload["merchant_subtotal"]),
            "buyer_transaction_fee": str(intent.payload["fee_amount"]),
            "fee_schedule_version": str(intent.payload["fee_schedule_version"]),
            "tax_amount": str(intent.payload["tax_amount"]),
            "amount": f"{intent.amount:.2f}",
            "currency": intent.currency,
            "payment_status": "PRAVA_COMPLETED",
            "fulfillment_status": "VERIFIED",
            "entitlement_ids": sorted(set(entitlement_ids)),
            "stack_patch_id": patch.id,
            "stack_patch_status": "STAGED",
            "issued_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "environment": environment,
            "adapter_label": adapter_label,
            "production_success": production_success,
        }
        receipt_hash = content_hash(payload)
        session.add(
            Receipt(
                id=receipt_id,
                organization_id=organization_id,
                purchase_intent_id=intent.id,
                receipt_hash=receipt_hash,
                payload=payload,
            )
        )

    def _receipt_provenance(self) -> tuple[str, str, bool]:
        descriptors = (self._prava.descriptor, self._merchant.descriptor)
        if any(descriptor.mode is AdapterMode.DEVELOPMENT_FIXTURE for descriptor in descriptors):
            return "fixture", "DEVELOPMENT_FIXTURE_NOT_PRODUCTION", False
        label = "+".join(descriptor.provider for descriptor in descriptors)
        production_success = self._environment == "production" and all(
            descriptor.production_verified for descriptor in descriptors
        )
        return self._environment, label, production_success
