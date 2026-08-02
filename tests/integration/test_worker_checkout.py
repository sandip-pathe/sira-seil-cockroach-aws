from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from jsonschema.validators import validator_for
from referencing import Registry, Resource
from sira_api.fixtures import DemoFixtureBundle, content_hash
from sira_api.service import WorkflowService
from sira_worker.contracts import (
    IsolatedCheckoutActivityInput,
    ReconcileActivityInput,
    RefundActivityInput,
    SafeFulfillmentStatus,
    SafeMerchantOutcome,
    SafeReversalStatus,
    VerifyFulfillmentActivityInput,
)
from sira_worker.coordinator import PersistentCheckoutCoordinator
from sqlalchemy import func, select

from integrations.common import AdapterDescriptor
from integrations.errors import ProviderError, ProviderErrorCode
from integrations.merchants.models import (
    EntitlementVerificationRequest,
    EntitlementVerificationResult,
    EntitlementVerificationStatus,
    MerchantCheckoutOutcome,
    MerchantCheckoutRequest,
    MerchantOutcome,
    MerchantRefundRequest,
    MerchantRefundResult,
    RefundOutcomeStatus,
)
from integrations.merchants.protocols import ControlledMerchantAdapter
from integrations.prava.models import (
    PravaCheckoutResult,
    PravaHostedSession,
    PravaPaymentStatus,
    PravaReportResult,
    PravaSessionRequest,
)
from persistence.database import Database, DatabaseSettings
from persistence.models import (
    ApprovalRequest,
    Base,
    BrowserReturnBinding,
    OutboxEvent,
    PaymentAttempt,
    PaymentSession,
    PurchaseIntent,
    PurchaseReversal,
    StackPatch,
    TransactionTransition,
    WorkflowRun,
)
from persistence.repositories import WorkflowRepository

ROOT = Path(__file__).resolve().parents[2]


def renew_locked_fixture_quote(
    canonical_intent: PurchaseIntent,
    intent_view: dict[str, Any],
    *,
    expires_at: datetime,
) -> None:
    """Rebuild the complete exact-hash snapshot before any approval is requested."""

    normalized_expiry = expires_at.astimezone(UTC)
    payload = dict(canonical_intent.payload)
    payload["quote_expires_at"] = normalized_expiry.isoformat().replace("+00:00", "Z")
    payload.pop("intent_hash", None)
    intent_hash = content_hash(payload)
    payload["intent_hash"] = intent_hash

    canonical_intent.quote_expires_at = normalized_expiry
    canonical_intent.payload = payload
    canonical_intent.intent_hash = intent_hash
    intent_view["quote_expires_at"] = normalized_expiry.isoformat()
    intent_view["intent_hash"] = intent_hash


def assert_frozen_receipt_schema(receipt: dict[str, Any]) -> None:
    schema_root = ROOT / "contracts" / "jsonschema"
    common = json.loads((schema_root / "common.schema.json").read_text(encoding="utf-8"))
    schema = json.loads((schema_root / "receipt.schema.json").read_text(encoding="utf-8"))
    registry = Registry().with_resource(common["$id"], Resource.from_contents(common))
    validator_for(schema)(schema, registry=registry).validate(receipt)


class FakeMerchant:
    descriptor = AdapterDescriptor.production("controlled_merchant")

    async def checkout_with_ephemeral_card(
        self,
        request: MerchantCheckoutRequest,
        *,
        card_token: str,
        dynamic_cvv: str,
        expiry_month: str,
        expiry_year: str,
    ) -> MerchantCheckoutOutcome:
        del request, card_token, dynamic_cvv, expiry_month, expiry_year
        raise AssertionError("the fake Prava coordinator returns the safe merchant result")

    async def reconcile_order(self, request: MerchantCheckoutRequest) -> MerchantCheckoutOutcome:
        del request
        return self.approved_outcome()

    async def verify_entitlements(
        self, request: EntitlementVerificationRequest
    ) -> EntitlementVerificationResult:
        suffix = "workspace" if request.entitlement_type == "workspace_entitlement" else "seats"
        return EntitlementVerificationResult(
            status=EntitlementVerificationStatus.VERIFIED,
            observed_quantity=request.minimum_quantity,
            external_entitlement_ids=(f"external_ent_{suffix}",),
            access_probe_verified=request.require_access_probe,
            adapter=self.descriptor,
            provider_confirmed=True,
        )

    async def aclose(self) -> None:
        return None

    @classmethod
    def approved_outcome(cls) -> MerchantCheckoutOutcome:
        return MerchantCheckoutOutcome(
            outcome=MerchantOutcome.APPROVED,
            merchant_order_id="merchant_order_real_contract",
            authorization_code=None,
            response_code="APPROVED",
            adapter=cls.descriptor,
            provider_confirmed=True,
        )


class FlakyEntitlementMerchant(FakeMerchant):
    def __init__(self) -> None:
        self.fail_verification = True

    async def verify_entitlements(
        self, request: EntitlementVerificationRequest
    ) -> EntitlementVerificationResult:
        if not self.fail_verification:
            return await super().verify_entitlements(request)
        return EntitlementVerificationResult(
            status=EntitlementVerificationStatus.FAILED_RETRYABLE,
            observed_quantity=0,
            external_entitlement_ids=(),
            access_probe_verified=False,
            adapter=self.descriptor,
            provider_confirmed=True,
        )


class RefundMerchant(FakeMerchant):
    def __init__(self) -> None:
        self.request_calls = 0
        self.reconcile_calls = 0

    async def request_refund(self, request: MerchantRefundRequest) -> MerchantRefundResult:
        self.request_calls += 1
        return MerchantRefundResult(
            status=RefundOutcomeStatus.PENDING,
            provider_refund_id="refund_real_contract",
            refunded_amount="0.00",
            currency=request.currency,
            entitlements_revoked=False,
            adapter=self.descriptor,
            provider_confirmed=True,
        )

    async def reconcile_refund(self, request: MerchantRefundRequest) -> MerchantRefundResult:
        self.reconcile_calls += 1
        return MerchantRefundResult(
            status=RefundOutcomeStatus.REFUNDED,
            provider_refund_id="refund_real_contract",
            refunded_amount=request.amount,
            currency=request.currency,
            entitlements_revoked=True,
            adapter=self.descriptor,
            provider_confirmed=True,
        )


class FakePrava:
    descriptor = AdapterDescriptor.production("prava")

    def __init__(self) -> None:
        self.execute_calls = 0

    async def create_session(self, request: PravaSessionRequest) -> PravaHostedSession:
        del request
        raise AssertionError("session creation is covered through the API adapter test")

    async def execute_isolated_checkout(
        self,
        *,
        session_id: str,
        request: MerchantCheckoutRequest,
        merchant: ControlledMerchantAdapter,
    ) -> PravaCheckoutResult:
        del request, merchant
        self.execute_calls += 1
        return PravaCheckoutResult(
            session_id=session_id,
            prava_order_id="prava_order_real_contract",
            transaction_reference="txn_real_contract",
            merchant=FakeMerchant.approved_outcome(),
            provider_reported=True,
            final_status=PravaPaymentStatus.COMPLETED,
            reconciliation_required=False,
            adapter=self.descriptor,
        )

    async def report_known_outcome(
        self,
        *,
        session_id: str,
        transaction_reference: str,
        outcome: MerchantCheckoutOutcome,
    ) -> PravaReportResult:
        del outcome
        return PravaReportResult(
            session_id=session_id,
            transaction_reference=transaction_reference,
            provider_confirmed=True,
            adapter=self.descriptor,
        )

    async def aclose(self) -> None:
        return None


class FailingPrava(FakePrava):
    async def execute_isolated_checkout(
        self,
        *,
        session_id: str,
        request: MerchantCheckoutRequest,
        merchant: ControlledMerchantAdapter,
    ) -> PravaCheckoutResult:
        del session_id, request, merchant
        self.execute_calls += 1
        raise ProviderError(
            provider="prava",
            operation="execute_isolated_checkout",
            code=ProviderErrorCode.UNAVAILABLE,
            retryable=True,
        ) from None


@pytest_asyncio.fixture
async def checkout_database() -> AsyncIterator[Database]:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield database
    finally:
        await database.close()


async def prepare_approved_checkout(
    database: Database,
) -> tuple[WorkflowService, dict[str, Any]]:
    service = WorkflowService(database, DemoFixtureBundle.load())
    await service.reset_demo("org_consultco")
    _, intent = await service.lock_purchase_intent(
        organization_id="org_consultco",
        actor_id="usr_requester",
        decision_id="dec_consultco_v1",
        idempotency_key="worker-lock-intent",
        body={"solution_plan_id": None},
    )
    # These worker tests use real wall time. Rebuild the complete locked snapshot before
    # approval, just as a fresh live quote would; never mutate a hash-bound column alone.
    async with database.transaction("org_consultco") as session:
        repository = WorkflowRepository(session, "org_consultco")
        canonical_intent = await repository.get_purchase_intent(
            str(intent["purchase_intent_id"]), lock=True
        )
        renew_locked_fixture_quote(
            canonical_intent,
            intent,
            expires_at=datetime.now(UTC) + timedelta(hours=2),
        )
    _, approval = await service.create_approval_request(
        organization_id="org_consultco",
        actor_id="usr_requester",
        intent_id=str(intent["purchase_intent_id"]),
        idempotency_key="worker-start-approval",
        body={},
    )
    for role in [
        "operations_owner",
        "security_privacy_owner",
        "legal_owner",
        "budget_owner",
    ]:
        await service.approve(
            organization_id="org_consultco",
            actor_id=f"usr_{role}",
            actor_roles=frozenset({role}),
            step_up_verified=True,
            approval_id=str(approval["id"]),
            idempotency_key=f"worker-approve-{role}",
            body={"intent_hash": approval["intent_hash"], "actor_role": role},
        )

    async with database.transaction("org_consultco") as session:
        repository = WorkflowRepository(session, "org_consultco")
        canonical_intent = await repository.get_purchase_intent(
            str(intent["purchase_intent_id"]), lock=True
        )
        payment_session = PaymentSession(
            id="pays_worker_contract",
            organization_id="org_consultco",
            purchase_intent_id=str(intent["purchase_intent_id"]),
            provider="PRAVA",
            provider_session_id="prava_session_real_contract",
            provider_order_id="prava_order_real_contract",
            hosted_url="https://checkout.prava.test/session/contract",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            status="SESSION_CREATED",
        )
        session.add(payment_session)
        state = service.browser_return_signer.issue()
        session.add(
            BrowserReturnBinding(
                id="brb_worker_contract",
                organization_id="org_consultco",
                purchase_intent_id=str(intent["purchase_intent_id"]),
                payment_session_id=payment_session.id,
                actor_id="usr_requester",
                state_hash=service.browser_return_signer.digest(state),
                provider_session_hash=service.browser_return_signer.digest(
                    payment_session.provider_session_id
                ),
                return_url_hash=service.browser_return_signer.digest(
                    "https://app.example.test/purchase/return"
                ),
                expires_at=datetime.now(UTC) + timedelta(minutes=10),
                consumed_at=None,
            )
        )
        await repository.transition_purchase_intent(
            intent_id=str(intent["purchase_intent_id"]),
            state_field="payment_status",
            allowed_from={"NOT_STARTED"},
            to_state="SESSION_CREATED",
            event_key="worker-session-created",
            actor_type="provider",
            actor_id="prava",
            reason_code="HOSTED_SESSION_CREATED",
            payload_hash=content_hash({"session": "prava_session_real_contract"}),
        )
    await service.accept_prava_browser_return(
        organization_id="org_consultco",
        actor_id="usr_requester",
        body={
            "state": state,
            "return_url": "https://app.example.test/purchase/return",
        },
    )
    return service, intent


@pytest.mark.asyncio
async def test_worker_persists_payment_fulfillment_receipt_and_staged_patch(
    checkout_database: Database,
) -> None:
    service, intent = await prepare_approved_checkout(checkout_database)
    intent_id = str(intent["purchase_intent_id"])
    unrelated_payload = DemoFixtureBundle.load().stack_patch()
    unrelated_payload.update(
        {
            "patch_id": "patch_unrelated_newer",
            "solution_plan_id": "sol_unrelated",
            "status": "PROPOSED",
        }
    )
    unrelated_payload["content_hash"] = content_hash(
        {key: value for key, value in unrelated_payload.items() if key != "content_hash"}
    )
    async with checkout_database.transaction("org_consultco") as session:
        canonical_intent = (
            await session.execute(select(PurchaseIntent).where(PurchaseIntent.id == intent_id))
        ).scalar_one()
        assert canonical_intent.quote_version == 1
        assert canonical_intent.stack_patch_id == "patch_consultco_fixture_d"
        session.add(
            StackPatch(
                id="patch_unrelated_newer",
                organization_id="org_consultco",
                base_snapshot_id="stack_consultco_v1",
                base_version=1,
                state="PROPOSED",
                payload=unrelated_payload,
                patch_hash=unrelated_payload["content_hash"],
            )
        )

    coordinator = PersistentCheckoutCoordinator(
        database=checkout_database,
        prava=FakePrava(),
        merchant=FakeMerchant(),
        merchant_adapter_id="merchant_fixture_d",
    )
    result = await coordinator.execute_isolated_checkout(
        IsolatedCheckoutActivityInput(
            organization_id="org_consultco",
            purchase_intent_id=intent["purchase_intent_id"],
            intent_hash=intent["intent_hash"],
            prava_session_id="prava_session_real_contract",
            merchant_adapter_id="merchant_fixture_d",
            idempotency_key="checkout-worker-contract",
        )
    )
    await coordinator.verify_fulfillment(
        VerifyFulfillmentActivityInput(
            organization_id="org_consultco",
            purchase_intent_id=str(intent["purchase_intent_id"]),
            merchant_order_id=str(result.merchant_order_id),
        )
    )

    assert result.merchant_outcome is SafeMerchantOutcome.APPROVED
    assert result.provider_reported is True
    status = await service.purchase_status("org_consultco", intent["purchase_intent_id"])
    assert status["payment_status"] == "PRAVA_COMPLETED"
    assert status["fulfillment_status"] == "VERIFIED"
    assert status["purchase_state"] == "PURCHASE_FULFILLED"
    workflow = await service.workflow(
        "org_consultco", f"wf_checkout_{intent['purchase_intent_id']}"
    )
    assert workflow["status"] == "COMPLETED"
    receipt = await service.get_receipt("org_consultco", intent["purchase_intent_id"])
    assert_frozen_receipt_schema(receipt)
    assert receipt["payment_status"] == "PRAVA_COMPLETED"
    assert receipt["fulfillment_status"] == "VERIFIED"
    assert receipt["quote_version"] == 1
    assert receipt["stack_patch_id"] == "patch_consultco_fixture_d"
    assert receipt["stack_patch_status"] == "STAGED"
    assert receipt["environment"] == "sandbox"
    assert receipt["production_success"] is False
    async with checkout_database.transaction("org_consultco") as session:
        patches = {
            patch.id: patch.state
            for patch in (
                await session.execute(
                    select(StackPatch).where(StackPatch.organization_id == "org_consultco")
                )
            ).scalars()
        }
        payment_session = (
            await session.execute(
                select(PaymentSession).where(PaymentSession.id == "pays_worker_contract")
            )
        ).scalar_one()
    assert patches["patch_consultco_fixture_d"] == "STAGED"
    assert patches["patch_unrelated_newer"] == "PROPOSED"
    assert payment_session.status == "PRAVA_COMPLETED"


@pytest.mark.asyncio
async def test_refund_reconciles_without_repeating_mutation_and_revokes_entitlement(
    checkout_database: Database,
) -> None:
    service, intent = await prepare_approved_checkout(checkout_database)
    intent_id = str(intent["purchase_intent_id"])
    merchant = RefundMerchant()
    coordinator = PersistentCheckoutCoordinator(
        database=checkout_database,
        prava=FakePrava(),
        merchant=merchant,
        merchant_adapter_id="merchant_fixture_d",
    )
    checkout = await coordinator.execute_isolated_checkout(
        IsolatedCheckoutActivityInput(
            organization_id="org_consultco",
            purchase_intent_id=intent_id,
            intent_hash=str(intent["intent_hash"]),
            prava_session_id="prava_session_real_contract",
            merchant_adapter_id="merchant_fixture_d",
            idempotency_key="checkout-before-refund",
        )
    )
    await coordinator.verify_fulfillment(
        VerifyFulfillmentActivityInput(
            organization_id="org_consultco",
            purchase_intent_id=intent_id,
            merchant_order_id=str(checkout.merchant_order_id),
        )
    )
    _, reversal = await service.request_reversal(
        organization_id="org_consultco",
        actor_id="usr_operations_owner",
        intent_id=intent_id,
        idempotency_key="request-real-refund",
        body={
            "kind": "REFUND",
            "requested_amount": intent["amount"],
            "reason_code": "PRODUCT_NOT_ADOPTED",
            "reason": "The measured operating outcome was not achieved.",
        },
    )
    activity_input = RefundActivityInput(
        organization_id="org_consultco",
        reversal_id=str(reversal["id"]),
        purchase_intent_id=intent_id,
        intent_hash=str(intent["intent_hash"]),
        idempotency_key=f"wf_reversal_{reversal['id']}",
    )

    pending = await coordinator.execute_refund(activity_input)
    completed = await coordinator.reconcile_refund(activity_input)

    assert pending.status is SafeReversalStatus.PROVIDER_PENDING
    assert pending.reconciliation_required is True
    assert completed.status is SafeReversalStatus.REFUNDED
    assert completed.reconciliation_required is False
    assert merchant.request_calls == 1
    assert merchant.reconcile_calls == 1
    status = await service.purchase_status("org_consultco", intent_id)
    assert status["purchase_state"] == "REFUNDED"
    assert status["fulfillment_status"] == "REVOKED"
    async with checkout_database.transaction("org_consultco") as session:
        persisted = (
            await session.execute(
                select(PurchaseReversal).where(PurchaseReversal.id == reversal["id"])
            )
        ).scalar_one()
        assert persisted.provider_confirmed is True
        assert persisted.provider_reference == "refund_real_contract"


@pytest.mark.asyncio
async def test_provider_failure_after_dispatch_enters_reconciliation_and_recovers(
    checkout_database: Database,
) -> None:
    service, intent = await prepare_approved_checkout(checkout_database)
    intent_id = str(intent["purchase_intent_id"])
    prava = FailingPrava()
    coordinator = PersistentCheckoutCoordinator(
        database=checkout_database,
        prava=prava,
        merchant=FakeMerchant(),
        merchant_adapter_id="merchant_fixture_d",
    )
    activity_input = IsolatedCheckoutActivityInput(
        organization_id="org_consultco",
        purchase_intent_id=intent_id,
        intent_hash=str(intent["intent_hash"]),
        prava_session_id="prava_session_real_contract",
        merchant_adapter_id="merchant_fixture_d",
        idempotency_key="checkout-provider-failure",
    )

    uncertain = await coordinator.execute_isolated_checkout(activity_input)

    assert uncertain.merchant_outcome is SafeMerchantOutcome.UNKNOWN
    assert uncertain.reconciliation_required is True
    status = await service.purchase_status("org_consultco", intent_id)
    assert status["payment_status"] == "UNCERTAIN"
    async with checkout_database.transaction("org_consultco") as session:
        attempt = (
            await session.execute(
                select(PaymentAttempt).where(PaymentAttempt.purchase_intent_id == intent_id)
            )
        ).scalar_one()
        assert attempt.closed_at is None
        assert attempt.merchant_outcome == "UNKNOWN"

    recovered = await coordinator.reconcile_checkout(
        ReconcileActivityInput(
            organization_id="org_consultco",
            purchase_intent_id=intent_id,
            intent_hash=str(intent["intent_hash"]),
            prava_session_id="prava_session_real_contract",
            merchant_adapter_id="merchant_fixture_d",
            idempotency_key="checkout-provider-failure",
            transaction_reference=uncertain.transaction_reference,
        )
    )
    await coordinator.verify_fulfillment(
        VerifyFulfillmentActivityInput(
            organization_id="org_consultco",
            purchase_intent_id=intent_id,
            merchant_order_id=str(recovered.merchant_order_id),
        )
    )

    assert recovered.merchant_outcome is SafeMerchantOutcome.APPROVED
    assert recovered.reconciliation_required is False
    status = await service.purchase_status("org_consultco", intent_id)
    assert status["payment_status"] == "PRAVA_COMPLETED"
    assert status["fulfillment_status"] == "VERIFIED"


@pytest.mark.asyncio
async def test_paid_fulfillment_failure_retries_without_repeating_checkout(
    checkout_database: Database,
) -> None:
    service, intent = await prepare_approved_checkout(checkout_database)
    intent_id = str(intent["purchase_intent_id"])
    merchant = FlakyEntitlementMerchant()
    prava = FakePrava()
    coordinator = PersistentCheckoutCoordinator(
        database=checkout_database,
        prava=prava,
        merchant=merchant,
        merchant_adapter_id="merchant_fixture_d",
    )
    checkout = await coordinator.execute_isolated_checkout(
        IsolatedCheckoutActivityInput(
            organization_id="org_consultco",
            purchase_intent_id=intent_id,
            intent_hash=str(intent["intent_hash"]),
            prava_session_id="prava_session_real_contract",
            merchant_adapter_id="merchant_fixture_d",
            idempotency_key="checkout-flaky-fulfillment",
        )
    )
    fulfillment_input = VerifyFulfillmentActivityInput(
        organization_id="org_consultco",
        purchase_intent_id=intent_id,
        merchant_order_id=str(checkout.merchant_order_id),
    )

    with pytest.raises(ProviderError) as first:
        await coordinator.verify_fulfillment(fulfillment_input)

    assert first.value.retryable is True
    assert prava.execute_calls == 1
    status = await service.purchase_status("org_consultco", intent_id)
    assert status["payment_status"] == "PRAVA_COMPLETED"
    assert status["fulfillment_status"] == "FAILED_RETRYABLE"

    merchant.fail_verification = False
    fulfilled = await coordinator.verify_fulfillment(fulfillment_input)

    assert fulfilled.status is SafeFulfillmentStatus.VERIFIED
    assert prava.execute_calls == 1
    status = await service.purchase_status("org_consultco", intent_id)
    assert status["fulfillment_status"] == "VERIFIED"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("expired_boundary", "expected_reason"),
    [
        ("quote", "QUOTE_EXPIRED_BEFORE_CHECKOUT"),
        ("approval", "APPROVAL_EXPIRED_BEFORE_CHECKOUT"),
        ("session", "PAYMENT_SESSION_EXPIRED_BEFORE_CHECKOUT"),
    ],
)
async def test_worker_rechecks_expiry_before_provider_dispatch(
    checkout_database: Database,
    expired_boundary: str,
    expected_reason: str,
) -> None:
    _, intent = await prepare_approved_checkout(checkout_database)
    intent_id = str(intent["purchase_intent_id"])
    async with checkout_database.transaction("org_consultco") as session:
        canonical_intent = (
            await session.execute(select(PurchaseIntent).where(PurchaseIntent.id == intent_id))
        ).scalar_one()
        payment_session = (
            await session.execute(
                select(PaymentSession).where(PaymentSession.id == "pays_worker_contract")
            )
        ).scalar_one()
        approval = (
            await session.execute(
                select(ApprovalRequest).where(
                    ApprovalRequest.purchase_intent_id == intent_id,
                    ApprovalRequest.status == "APPROVED",
                )
            )
        ).scalar_one()
        if expired_boundary == "quote":
            canonical_intent.quote_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        elif expired_boundary == "approval":
            approval.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        else:
            payment_session.expires_at = datetime.now(UTC) - timedelta(seconds=1)

    prava = FakePrava()
    coordinator = PersistentCheckoutCoordinator(
        database=checkout_database,
        prava=prava,
        merchant=FakeMerchant(),
        merchant_adapter_id="merchant_fixture_d",
    )
    with pytest.raises(ProviderError) as raised:
        await coordinator.execute_isolated_checkout(
            IsolatedCheckoutActivityInput(
                organization_id="org_consultco",
                purchase_intent_id=intent_id,
                intent_hash=str(intent["intent_hash"]),
                prava_session_id="prava_session_real_contract",
                merchant_adapter_id="merchant_fixture_d",
                idempotency_key=f"checkout-expired-{expired_boundary}",
            )
        )
    assert raised.value.code is ProviderErrorCode.INVALID_STATE
    assert prava.execute_calls == 0

    async with checkout_database.transaction("org_consultco") as session:
        canonical_intent = (
            await session.execute(select(PurchaseIntent).where(PurchaseIntent.id == intent_id))
        ).scalar_one()
        payment_session = (
            await session.execute(
                select(PaymentSession).where(PaymentSession.id == "pays_worker_contract")
            )
        ).scalar_one()
        approval = (
            await session.execute(
                select(ApprovalRequest).where(ApprovalRequest.purchase_intent_id == intent_id)
            )
        ).scalar_one()
        attempt_count = (
            await session.execute(
                select(func.count())
                .select_from(PaymentAttempt)
                .where(PaymentAttempt.purchase_intent_id == intent_id)
            )
        ).scalar_one()
        transition = (
            await session.execute(
                select(TransactionTransition).where(
                    TransactionTransition.purchase_intent_id == intent_id,
                    TransactionTransition.to_state == "EXPIRED",
                )
            )
        ).scalar_one()
        assert canonical_intent.payment_status == "EXPIRED"
    assert payment_session.status == "EXPIRED"
    if expired_boundary == "approval":
        assert approval.status == "EXPIRED"
        assert canonical_intent.approval_status == "EXPIRED"
    assert attempt_count == 0
    assert transition.reason_code == expected_reason


@pytest.mark.asyncio
async def test_revocation_cancels_queued_checkout_before_provider_dispatch(
    checkout_database: Database,
) -> None:
    service, intent = await prepare_approved_checkout(checkout_database)
    intent_id = str(intent["purchase_intent_id"])
    async with checkout_database.transaction("org_consultco") as session:
        approval = (
            await session.execute(
                select(ApprovalRequest).where(
                    ApprovalRequest.purchase_intent_id == intent_id,
                    ApprovalRequest.status == "APPROVED",
                )
            )
        ).scalar_one()
        approval_id = approval.id
        intent_hash = approval.intent_hash

    _, revoked = await service.revoke_approval(
        organization_id="org_consultco",
        actor_id="usr_operations_owner",
        actor_roles=frozenset({"operations_owner"}),
        step_up_verified=True,
        approval_id=approval_id,
        idempotency_key="worker-revoke-before-dispatch",
        body={
            "intent_hash": intent_hash,
            "actor_role": "operations_owner",
            "reason": "The approved purchase authority was withdrawn",
        },
    )
    assert revoked["status"] == "REVOKED"

    prava = FakePrava()
    coordinator = PersistentCheckoutCoordinator(
        database=checkout_database,
        prava=prava,
        merchant=FakeMerchant(),
        merchant_adapter_id="merchant_fixture_d",
    )
    with pytest.raises(ProviderError) as raised:
        await coordinator.execute_isolated_checkout(
            IsolatedCheckoutActivityInput(
                organization_id="org_consultco",
                purchase_intent_id=intent_id,
                intent_hash=intent_hash,
                prava_session_id="prava_session_real_contract",
                merchant_adapter_id="merchant_fixture_d",
                idempotency_key="checkout-after-revocation",
            )
        )
    assert raised.value.code is ProviderErrorCode.INVALID_STATE
    assert prava.execute_calls == 0

    async with checkout_database.transaction("org_consultco") as session:
        canonical_intent = (
            await session.execute(select(PurchaseIntent).where(PurchaseIntent.id == intent_id))
        ).scalar_one()
        payment_session = (
            await session.execute(
                select(PaymentSession).where(PaymentSession.id == "pays_worker_contract")
            )
        ).scalar_one()
        checkout_event = (
            await session.execute(
                select(OutboxEvent).where(
                    OutboxEvent.aggregate_id == intent_id,
                    OutboxEvent.event_type == "purchase_checkout.requested",
                )
            )
        ).scalar_one()
        workflow = (
            await session.execute(
                select(WorkflowRun).where(WorkflowRun.id == f"wf_checkout_{intent_id}")
            )
        ).scalar_one()
        assert canonical_intent.approval_status == "REVOKED"
        assert payment_session.status == "REVOKED"
        assert checkout_event.published_at is not None
        assert workflow.status == "FAILED"
        assert workflow.safe_error_code == "APPROVAL_REVOKED"
