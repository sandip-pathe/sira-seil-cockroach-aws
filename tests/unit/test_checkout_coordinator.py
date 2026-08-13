from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import pytest
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
)
from sira_worker.coordinator import PersistentCheckoutCoordinator

from integrations.common import AdapterDescriptor
from integrations.errors import ProviderError, ProviderErrorCode
from integrations.merchants.models import (
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
from integrations.prava.models import PravaCheckoutResult, PravaPaymentStatus, PravaReportResult
from integrations.prava.protocols import PravaHostedCheckoutProvider
from persistence.database import Database


DESCRIPTOR = AdapterDescriptor.production("test-provider")


def _merchant_request() -> MerchantCheckoutRequest:
    return MerchantCheckoutRequest(
        purchase_intent_id="intent-1",
        prava_order_id="order-1",
        idempotency_key="checkout-1",
        merchant_url="https://merchant.example/checkout",
        amount="990.00",
        currency="USD",
    )


def _checkout_input() -> IsolatedCheckoutActivityInput:
    return IsolatedCheckoutActivityInput(
        organization_id="org-buyer",
        purchase_intent_id="intent-1",
        intent_hash="sha256:" + "a" * 64,
        prava_session_id="session-1",
        merchant_adapter_id="merchant-v1",
        idempotency_key="checkout-1",
    )


def _reconcile_input() -> ReconcileActivityInput:
    source = _checkout_input()
    return ReconcileActivityInput(
        organization_id=source.organization_id,
        purchase_intent_id=source.purchase_intent_id,
        intent_hash=source.intent_hash,
        prava_session_id=source.prava_session_id,
        merchant_adapter_id=source.merchant_adapter_id,
        idempotency_key=source.idempotency_key,
        transaction_reference="txn-1",
    )


def _refund_input() -> RefundActivityInput:
    return RefundActivityInput(
        organization_id="org-buyer",
        reversal_id="reversal-1",
        purchase_intent_id="intent-1",
        intent_hash="sha256:" + "a" * 64,
        idempotency_key="refund-1",
    )


@dataclass
class FakeMerchant:
    outcome: MerchantOutcome = MerchantOutcome.APPROVED
    descriptor: AdapterDescriptor = DESCRIPTOR

    async def reconcile_order(self, _request: MerchantCheckoutRequest) -> MerchantCheckoutOutcome:
        return MerchantCheckoutOutcome(
            outcome=self.outcome,
            merchant_order_id="merchant-order-1"
            if self.outcome is MerchantOutcome.APPROVED
            else None,
            authorization_code="auth-1" if self.outcome is MerchantOutcome.APPROVED else None,
            response_code="00" if self.outcome is MerchantOutcome.APPROVED else None,
            adapter=self.descriptor,
            provider_confirmed=self.outcome is not MerchantOutcome.UNKNOWN,
        )


@dataclass
class FakePrava:
    checkout_error: bool = False
    report_confirmed: bool = True
    descriptor: AdapterDescriptor = DESCRIPTOR

    async def execute_isolated_checkout(self, **_kwargs: Any) -> PravaCheckoutResult:
        if self.checkout_error:
            raise RuntimeError("provider connection lost")
        return PravaCheckoutResult(
            session_id="session-1",
            prava_order_id="order-1",
            transaction_reference="txn-1",
            merchant=MerchantCheckoutOutcome(
                outcome=MerchantOutcome.APPROVED,
                merchant_order_id="merchant-order-1",
                authorization_code="auth-1",
                response_code="00",
                adapter=DESCRIPTOR,
                provider_confirmed=True,
            ),
            provider_reported=True,
            final_status=PravaPaymentStatus.COMPLETED,
            reconciliation_required=False,
            adapter=self.descriptor,
        )

    async def report_known_outcome(self, **kwargs: Any) -> PravaReportResult:
        return PravaReportResult(
            session_id=kwargs["session_id"],
            transaction_reference=kwargs["transaction_reference"],
            provider_confirmed=self.report_confirmed,
            adapter=self.descriptor,
        )


@dataclass
class FakeReversal:
    result: MerchantRefundResult
    error: ProviderError | None = None
    descriptor: AdapterDescriptor = DESCRIPTOR

    async def request_refund(self, _request: MerchantRefundRequest) -> MerchantRefundResult:
        if self.error is not None:
            raise self.error
        return self.result

    async def reconcile_refund(self, _request: MerchantRefundRequest) -> MerchantRefundResult:
        return self.result


def _coordinator(
    *,
    merchant: FakeMerchant | None = None,
    prava: FakePrava | None = None,
    reversal: FakeReversal | None = None,
) -> PersistentCheckoutCoordinator:
    return PersistentCheckoutCoordinator(
        database=cast(Database, object()),
        prava=cast(PravaHostedCheckoutProvider, prava or FakePrava()),
        merchant=cast(ControlledMerchantAdapter, merchant or FakeMerchant()),
        reversal_merchant=cast(ControlledMerchantReversalAdapter, reversal) if reversal else None,
        merchant_adapter_id="merchant-v1",
    )


def test_coordinator_requires_named_merchant_adapter() -> None:
    with pytest.raises(ValueError, match="merchant_adapter_id"):
        PersistentCheckoutCoordinator(
            database=cast(Database, object()),
            prava=cast(PravaHostedCheckoutProvider, FakePrava()),
            merchant=cast(ControlledMerchantAdapter, FakeMerchant()),
            merchant_adapter_id=" ",
        )


@pytest.mark.asyncio
async def test_checkout_success_and_uncertain_dispatch_are_persisted_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: list[PravaCheckoutResult] = []

    async def prepare(
        _self: PersistentCheckoutCoordinator, _request: IsolatedCheckoutActivityInput
    ) -> tuple[MerchantCheckoutRequest, str]:
        return _merchant_request(), "attempt-1"

    async def persist(
        _self: PersistentCheckoutCoordinator, *, result: PravaCheckoutResult, **_kwargs: Any
    ) -> CheckoutActivityResult:
        persisted.append(result)
        return CheckoutActivityResult(
            purchase_intent_id="intent-1",
            prava_session_id="session-1",
            prava_order_id="order-1",
            transaction_reference=result.transaction_reference,
            merchant_outcome=SafeMerchantOutcome(result.merchant.outcome.value),
            merchant_order_id=result.merchant.merchant_order_id,
            provider_reported=result.provider_reported,
            reconciliation_required=result.reconciliation_required,
        )

    monkeypatch.setattr(PersistentCheckoutCoordinator, "_prepare_attempt", prepare)
    monkeypatch.setattr(PersistentCheckoutCoordinator, "_persist_checkout_result", persist)

    success = await _coordinator().execute_isolated_checkout(_checkout_input())
    uncertain = await _coordinator(prava=FakePrava(checkout_error=True)).execute_isolated_checkout(
        _checkout_input()
    )
    assert success.merchant_outcome is SafeMerchantOutcome.APPROVED
    assert uncertain.merchant_outcome is SafeMerchantOutcome.UNKNOWN
    assert uncertain.reconciliation_required is True
    assert persisted[-1].transaction_reference == "reconcile:attempt-1"


@pytest.mark.asyncio
async def test_reconcile_reports_known_outcomes_and_finishes_declines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    finished: list[dict[str, Any]] = []

    async def load(
        _self: PersistentCheckoutCoordinator, _request: ReconcileActivityInput
    ) -> tuple[MerchantCheckoutRequest, str]:
        return _merchant_request(), "attempt-1"

    async def persist(
        _self: PersistentCheckoutCoordinator, *, result: PravaCheckoutResult, **_kwargs: Any
    ) -> CheckoutActivityResult:
        return CheckoutActivityResult(
            "intent-1",
            "session-1",
            "order-1",
            "txn-1",
            SafeMerchantOutcome(result.merchant.outcome.value),
            result.merchant.merchant_order_id,
            result.provider_reported,
            result.reconciliation_required,
        )

    async def finish(_self: PersistentCheckoutCoordinator, **kwargs: Any) -> None:
        finished.append(kwargs)

    monkeypatch.setattr(PersistentCheckoutCoordinator, "_load_reconciliation_state", load)
    monkeypatch.setattr(PersistentCheckoutCoordinator, "_persist_checkout_result", persist)
    monkeypatch.setattr(PersistentCheckoutCoordinator, "_finish_workflow_run", finish)

    declined = await _coordinator(
        merchant=FakeMerchant(MerchantOutcome.DECLINED)
    ).reconcile_checkout(_reconcile_input())
    unknown = await _coordinator(merchant=FakeMerchant(MerchantOutcome.UNKNOWN)).reconcile_checkout(
        _reconcile_input()
    )
    assert declined.merchant_outcome is SafeMerchantOutcome.DECLINED
    assert declined.reconciliation_required is False
    assert unknown.reconciliation_required is True
    assert finished[0]["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_refund_execution_and_reconciliation_handle_uncertain_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = MerchantRefundRequest(
        merchant_order_id="merchant-order-1",
        idempotency_key="refund-1",
        amount="990.00",
        currency="USD",
        reason_code="BUYER_REQUESTED",
    )
    confirmed = MerchantRefundResult(
        status=RefundOutcomeStatus.REFUNDED,
        provider_refund_id="provider-refund-1",
        refunded_amount="990.00",
        currency="USD",
        entitlements_revoked=True,
        adapter=DESCRIPTOR,
        provider_confirmed=True,
    )
    persisted: list[MerchantRefundResult] = []

    async def load(
        _self: PersistentCheckoutCoordinator, _input: RefundActivityInput
    ) -> MerchantRefundRequest:
        return request

    async def persist(
        _self: PersistentCheckoutCoordinator,
        _input: RefundActivityInput,
        result: MerchantRefundResult,
    ) -> RefundActivityResult:
        persisted.append(result)
        return RefundActivityResult(
            "reversal-1",
            SafeReversalStatus.REFUNDED
            if result.status is RefundOutcomeStatus.REFUNDED
            else SafeReversalStatus.PROVIDER_PENDING,
            result.refunded_amount,
            result.currency,
            result.provider_refund_id,
            result.entitlements_revoked,
            result.status is RefundOutcomeStatus.UNKNOWN,
        )

    monkeypatch.setattr(PersistentCheckoutCoordinator, "_load_refund_state", load)
    monkeypatch.setattr(PersistentCheckoutCoordinator, "_persist_refund_result", persist)
    uncertain_error = ProviderError(
        provider="merchant",
        operation="refund",
        code=ProviderErrorCode.REVERSAL_UNCERTAIN,
        retryable=False,
    )
    uncertain = _coordinator(reversal=FakeReversal(result=confirmed, error=uncertain_error))
    pending = await uncertain.execute_refund(_refund_input())
    reconciled = await _coordinator(reversal=FakeReversal(result=confirmed)).reconcile_refund(
        _refund_input()
    )
    assert pending.status is SafeReversalStatus.PROVIDER_PENDING
    assert reconciled.status is SafeReversalStatus.REFUNDED
    assert persisted[0].status is RefundOutcomeStatus.UNKNOWN


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected_code", "retryable"),
    [
        (SafeFulfillmentStatus.FAILED_RETRYABLE, ProviderErrorCode.UNAVAILABLE, True),
        (SafeFulfillmentStatus.FAILED_FINAL, ProviderErrorCode.INVALID_STATE, False),
    ],
)
async def test_fulfillment_failures_are_classified(
    monkeypatch: pytest.MonkeyPatch,
    status: SafeFulfillmentStatus,
    expected_code: ProviderErrorCode,
    retryable: bool,
) -> None:
    finished: list[dict[str, Any]] = []

    async def verify(_self: PersistentCheckoutCoordinator, **_kwargs: Any) -> SafeFulfillmentStatus:
        return status

    async def finish(_self: PersistentCheckoutCoordinator, **kwargs: Any) -> None:
        finished.append(kwargs)

    monkeypatch.setattr(PersistentCheckoutCoordinator, "_verify_fulfillment", verify)
    monkeypatch.setattr(PersistentCheckoutCoordinator, "_finish_workflow_run", finish)
    with pytest.raises(ProviderError) as error:
        await _coordinator().verify_fulfillment(
            VerifyFulfillmentActivityInput("org-buyer", "intent-1", "merchant-order-1")
        )
    assert error.value.code is expected_code
    assert error.value.retryable is retryable
    assert bool(finished) is (status is SafeFulfillmentStatus.FAILED_FINAL)


@pytest.mark.asyncio
async def test_verified_fulfillment_and_terminal_failure_finish_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    finished: list[dict[str, Any]] = []

    async def verify(_self: PersistentCheckoutCoordinator, **_kwargs: Any) -> SafeFulfillmentStatus:
        return SafeFulfillmentStatus.VERIFIED

    async def finish(_self: PersistentCheckoutCoordinator, **kwargs: Any) -> None:
        finished.append(kwargs)

    monkeypatch.setattr(PersistentCheckoutCoordinator, "_verify_fulfillment", verify)
    monkeypatch.setattr(PersistentCheckoutCoordinator, "_finish_workflow_run", finish)
    verified: FulfillmentActivityResult = await _coordinator().verify_fulfillment(
        VerifyFulfillmentActivityInput("org-buyer", "intent-1", "merchant-order-1")
    )
    await _coordinator().fail_checkout_workflow(
        WorkflowFailureActivityInput("org-buyer", "intent-1", "RETRY_LIMIT")
    )
    assert verified.status is SafeFulfillmentStatus.VERIFIED
    assert [item["status"] for item in finished] == ["COMPLETED", "FAILED"]
