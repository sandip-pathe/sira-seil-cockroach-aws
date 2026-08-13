from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from integrations.common import AdapterDescriptor
from integrations.errors import ProviderError, ProviderErrorCode
from integrations.merchants.models import (
    EntitlementVerificationRequest,
    EntitlementVerificationStatus,
    MerchantCheckoutOutcome,
    MerchantCheckoutRequest,
    MerchantOutcome,
    MerchantRefundRequest,
    RefundOutcomeStatus,
)
from integrations.merchants.rest import ControlledMerchantRestAdapter
from integrations.prava.models import (
    PravaMerchantDetails,
    PravaPaymentStatus,
    PravaProductDetails,
    PravaSessionRequest,
)
from integrations.prava.rest import PravaHostedRestAdapter


def _merchant_request() -> MerchantCheckoutRequest:
    return MerchantCheckoutRequest(
        purchase_intent_id="intent-1",
        prava_order_id="prava-order-1",
        idempotency_key="checkout-key-1",
        merchant_url="https://merchant.example/checkout",
        amount="990.00",
        currency="USD",
    )


def _refund_request() -> MerchantRefundRequest:
    return MerchantRefundRequest(
        merchant_order_id="merchant-order-1",
        idempotency_key="refund-key-1",
        amount="990.00",
        currency="USD",
        reason_code="BUYER_REQUESTED",
    )


def _merchant_adapter(handler: Any) -> ControlledMerchantRestAdapter:
    adapter = ControlledMerchantRestAdapter(
        base_url="https://merchant.example",
        api_key="x",
        allowed_hosts=frozenset({"merchant.example"}),
    )
    adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return adapter


@pytest.mark.asyncio
async def test_controlled_merchant_checkout_reconcile_entitlements_and_refunds() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if path == "/v1/checkout":
            payload = json.loads(request.content)
            assert payload["payment_method"]["token"] == "network-token"
            assert request.headers["Idempotency-Key"] == "checkout-key-1"
            return httpx.Response(
                200,
                json={
                    "outcome": "APPROVED",
                    "merchant_order_id": "merchant-order-1",
                    "authorization_code": "auth-1",
                    "response_code": "00",
                },
            )
        if path == "/v1/orders/by-idempotency-key/checkout-key-1":
            return httpx.Response(402, json={"status": "declined"})
        if path == "/v1/orders/merchant-order-1/entitlements":
            return httpx.Response(
                200,
                json={
                    "entitlements": [
                        {
                            "id": "entitlement-1",
                            "type": "SEAT",
                            "status": "active",
                            "quantity": 25,
                            "subject_id": "buyer-1",
                            "product_id": "product-1",
                            "region": "EU",
                            "access_probe_verified": True,
                        },
                        {"id": "ignored", "type": "OTHER", "status": "active"},
                    ]
                },
            )
        if path == "/v1/orders/merchant-order-1/refunds":
            assert request.headers["Idempotency-Key"] == "refund-key-1"
            return httpx.Response(
                200,
                json={
                    "status": "REFUNDED",
                    "refund_id": "refund-1",
                    "refunded_amount": "990.00",
                    "currency": "USD",
                    "entitlements_revoked": True,
                },
            )
        if path == "/v1/refunds/by-idempotency-key/refund-key-1":
            return httpx.Response(
                200,
                json={
                    "status": "PARTIALLY_REFUNDED",
                    "refund_id": "refund-1",
                    "refunded_amount": "400.00",
                    "currency": "USD",
                    "entitlements_revoked": False,
                },
            )
        return httpx.Response(404)

    adapter = _merchant_adapter(handler)
    try:
        checkout = await adapter.checkout_with_ephemeral_card(
            _merchant_request(),
            card_token="network-token",
            dynamic_cvv="123",
            expiry_month="12",
            expiry_year="30",
        )
        assert checkout.outcome is MerchantOutcome.APPROVED
        assert checkout.merchant_order_id == "merchant-order-1"
        reconciled = await adapter.reconcile_order(_merchant_request())
        assert reconciled.outcome is MerchantOutcome.DECLINED

        entitlement = await adapter.verify_entitlements(
            EntitlementVerificationRequest(
                merchant_order_id="merchant-order-1",
                entitlement_type="SEAT",
                minimum_quantity=20,
                subject_id="buyer-1",
                product_id="product-1",
                region="EU",
                require_access_probe=True,
            )
        )
        assert entitlement.status is EntitlementVerificationStatus.VERIFIED
        assert entitlement.observed_quantity == 25
        assert entitlement.access_probe_verified is True

        refunded = await adapter.request_refund(_refund_request())
        reconciled_refund = await adapter.reconcile_refund(_refund_request())
        assert refunded.status is RefundOutcomeStatus.REFUNDED
        assert refunded.entitlements_revoked is True
        assert reconciled_refund.status is RefundOutcomeStatus.PARTIALLY_REFUNDED
        assert "api_key='x'" not in repr(adapter)
        assert all(request.headers["Authorization"] == "Bearer x" for request in calls)
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_controlled_merchant_fails_closed_on_uncertain_or_invalid_responses() -> None:
    def uncertain(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/checkout":
            return httpx.Response(503)
        return httpx.Response(200, json={"entitlements": ["malformed"]})

    adapter = _merchant_adapter(uncertain)
    try:
        with pytest.raises(ProviderError) as checkout_error:
            await adapter.checkout_with_ephemeral_card(
                _merchant_request(),
                card_token="token",
                dynamic_cvv="123",
                expiry_month="12",
                expiry_year="30",
            )
        assert checkout_error.value.code is ProviderErrorCode.CHECKOUT_UNCERTAIN

        with pytest.raises(ProviderError) as request_error:
            await adapter.checkout_with_ephemeral_card(
                _merchant_request(),
                card_token="",
                dynamic_cvv="",
                expiry_month="",
                expiry_year="",
            )
        assert request_error.value.code is ProviderErrorCode.INVALID_REQUEST

        with pytest.raises(ProviderError) as entitlement_error:
            await adapter.verify_entitlements(
                EntitlementVerificationRequest(
                    merchant_order_id="merchant-order-1",
                    entitlement_type="SEAT",
                    minimum_quantity=1,
                )
            )
        assert entitlement_error.value.code is ProviderErrorCode.INVALID_RESPONSE
    finally:
        await adapter.aclose()


class ApprovedMerchant:
    descriptor = AdapterDescriptor.production("controlled_merchant")

    def __init__(self, *, uncertain: bool = False) -> None:
        self.uncertain = uncertain
        self.credentials: tuple[str, str, str, str] | None = None

    async def checkout_with_ephemeral_card(
        self,
        _request: MerchantCheckoutRequest,
        *,
        card_token: str,
        dynamic_cvv: str,
        expiry_month: str,
        expiry_year: str,
    ) -> MerchantCheckoutOutcome:
        self.credentials = (card_token, dynamic_cvv, expiry_month, expiry_year)
        if self.uncertain:
            raise ProviderError(
                provider="controlled_merchant",
                operation="checkout",
                code=ProviderErrorCode.CHECKOUT_UNCERTAIN,
                retryable=False,
            )
        return MerchantCheckoutOutcome(
            outcome=MerchantOutcome.APPROVED,
            merchant_order_id="merchant-order-1",
            authorization_code="auth-1",
            response_code="00",
            adapter=self.descriptor,
            provider_confirmed=True,
        )


def _prava_adapter(handler: Any) -> PravaHostedRestAdapter:
    adapter = PravaHostedRestAdapter(
        secret_key="x",
        base_url="https://api.prava.example",
        api_hosts=frozenset({"api.prava.example"}),
        merchant_hosts=frozenset({"merchant.example"}),
        callback_hosts=frozenset({"app.example"}),
        hosted_checkout_hosts=frozenset({"checkout.prava.example"}),
    )
    adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return adapter


@pytest.mark.asyncio
async def test_prava_session_and_isolated_checkout_complete_without_leaking_credentials() -> None:
    payment_polls = 0
    request_bodies: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal payment_polls
        body = json.loads(request.content) if request.content else {}
        request_bodies.append(body)
        if request.url.path == "/v1/sessions" and request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "session_id": "session-1",
                    "iframe_url": "https://checkout.prava.example/session-1",
                    "order_id": "prava-order-1",
                    "expires_at": (datetime.now(UTC) + timedelta(minutes=15)).isoformat(),
                    "session_token": "must-be-scrubbed",
                },
            )
        if request.url.path == "/v1/sessions/session-1/payment-result":
            payment_polls += 1
            if payment_polls == 1:
                return httpx.Response(
                    200,
                    json={
                        "status": "awaiting_result",
                        "session_id": "session-1",
                        "order_id": "prava-order-1",
                        "transactions": [
                            {
                                "line_items": [
                                    {
                                        "txn_ref_id": "txn-1",
                                        "merchant_url": "https://merchant.example/checkout",
                                        "total_amount": "990.00",
                                        "token": "network-token",
                                        "dynamic_cvv": "123",
                                        "expiry_month": "12",
                                        "expiry_year": "30",
                                    }
                                ]
                            }
                        ],
                    },
                )
            return httpx.Response(200, json={"status": "completed"})
        if request.url.path == "/v1/sessions/session-1/report-status":
            assert body["txn_status"] == "APPROVED"
            return httpx.Response(200, json={"status": "confirmed", "txn_ref_id": "txn-1"})
        return httpx.Response(404)

    adapter = _prava_adapter(handler)
    merchant = ApprovedMerchant()
    try:
        session = await adapter.create_session(
            PravaSessionRequest(
                user_id="buyer-1",
                user_email="buyer@example.test",
                total_amount="990.00",
                currency="USD",
                merchant=PravaMerchantDetails(
                    name="Seller",
                    url="https://merchant.example/checkout",
                    country_code_iso2="US",
                ),
                products=(
                    PravaProductDetails(
                        description="Annual software subscription",
                        unit_price="990.00",
                        product_id="product-1",
                    ),
                ),
                callback_url="https://app.example/payment-return",
            )
        )
        assert session.session_id == "session-1"
        result = await adapter.execute_isolated_checkout(
            session_id=session.session_id,
            request=_merchant_request(),
            merchant=merchant,
        )
        assert result.final_status is PravaPaymentStatus.COMPLETED
        assert result.reconciliation_required is False
        assert merchant.credentials == ("network-token", "123", "12", "30")
        serialized = json.dumps(request_bodies)
        assert "network-token" not in serialized
        assert "secret_key='x'" not in repr(adapter)
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_prava_uncertain_checkout_returns_reconciliation_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/payment-result"):
            return httpx.Response(
                200,
                json={
                    "status": "awaiting_result",
                    "session_id": "session-1",
                    "order_id": "prava-order-1",
                    "transactions": [
                        {
                            "line_items": [
                                {
                                    "txn_ref_id": "txn-1",
                                    "total_amount": "990.00",
                                    "token": "token",
                                    "dynamic_cvv": "123",
                                    "expiry_month": "12",
                                    "expiry_year": "30",
                                }
                            ]
                        }
                    ],
                },
            )
        return httpx.Response(404)

    adapter = _prava_adapter(handler)
    try:
        result = await adapter.execute_isolated_checkout(
            session_id="session-1",
            request=_merchant_request(),
            merchant=ApprovedMerchant(uncertain=True),
        )
        assert result.merchant.outcome is MerchantOutcome.UNKNOWN
        assert result.reconciliation_required is True
        assert result.provider_reported is False
    finally:
        await adapter.aclose()
