"""Mocked contract tests for real provider adapters; no external calls are made."""

from __future__ import annotations

import json
from dataclasses import asdict, fields

import httpx
import pytest
import respx
from sira_worker.activities import CheckoutActivities
from sira_worker.contracts import (
    CheckoutActivityResult,
    IsolatedCheckoutActivityInput,
    PurchaseCheckoutWorkflowInput,
    PurchaseCheckoutWorkflowResult,
    ReconcileActivityInput,
    assert_all_contract_schemas_are_credential_free,
    assert_credential_free_contract,
)
from temporalio.exceptions import ApplicationError

from integrations.common import AdapterMode
from integrations.errors import ProviderError, ProviderErrorCode
from integrations.merchants import (
    ControlledMerchantRestAdapter,
    DevelopmentFixtureMerchantAdapter,
    EntitlementVerificationRequest,
    EntitlementVerificationStatus,
    MerchantCheckoutRequest,
    MerchantOutcome,
    MerchantRefundRequest,
    RefundOutcomeStatus,
)
from integrations.prava import (
    DevelopmentFixturePravaAdapter,
    PravaMerchantDetails,
    PravaPaymentStatus,
    PravaProductDetails,
    PravaSessionRequest,
)
from integrations.prava.rest import PravaHostedRestAdapter
from integrations.senso import (
    DevelopmentFixtureSensoAdapter,
    SensoBrowseRequest,
    SensoContentVersionRequest,
    SensoEvidenceHit,
    SensoFolderRole,
    SensoFolderScope,
    SensoKeyIdentityBinding,
    SensoRestAdapter,
    SensoSearchRequest,
)

SENSO_BASE = "https://apiv2.senso.ai/api/v1"
SENSO_SCOPE = SensoFolderScope(
    key_id="key_query_only",
    folder_node_id="folder_allowed",
    purpose="buyer_query",
)
SENSO_OUTSIDE_FOLDER_ID = "folder_outside"
PRAVA_BASE = "https://sandbox.api.prava.space"
MERCHANT_API_BASE = "https://merchant-api.example"
SENSITIVE_CARD_TOKEN = "4111111111111111"
SENSITIVE_CVV = "987"
_OMITTED = object()


def _prava_adapter() -> PravaHostedRestAdapter:
    return PravaHostedRestAdapter(
        secret_key="prava-test-secret",  # pragma: allowlist secret
        merchant_hosts=frozenset({"merchant.example"}),
        callback_hosts=frozenset({"app.example"}),
    )


def _merchant_adapter() -> ControlledMerchantRestAdapter:
    return ControlledMerchantRestAdapter(
        base_url=MERCHANT_API_BASE,
        api_key="merchant-test-secret",  # pragma: allowlist secret
        allowed_hosts=frozenset({"merchant-api.example"}),
    )


def _merchant_request() -> MerchantCheckoutRequest:
    return MerchantCheckoutRequest(
        purchase_intent_id="pi_demo",
        prava_order_id="ord_demo",
        idempotency_key="checkout_pi_demo_v1",
        merchant_url="https://merchant.example",
        amount="89.00",
        currency="USD",
    )


def _awaiting_result(
    *, merchant_url: str | object | None = "https://merchant.example"
) -> dict[str, object]:
    line_item: dict[str, object] = {
        "txn_ref_id": "tli_demo",
        "merchant_name": "Demo Merchant",
        "total_amount": "89.00",
        "status": "awaiting_result",
        "token": SENSITIVE_CARD_TOKEN,
        "dynamic_cvv": SENSITIVE_CVV,
        "expiry_month": "12",
        "expiry_year": "2030",
        "products": [],
    }
    if merchant_url is not _OMITTED:
        line_item["merchant_url"] = merchant_url
    return {
        "session_id": "ses_demo",
        "order_id": "ord_demo",
        "status": "awaiting_result",
        "transactions": [
            {
                "txn_id": "txn_demo",
                "status": "awaiting_result",
                "line_items": [line_item],
            }
        ],
    }


def _mock_senso_activation(
    *,
    grants: list[dict[str, str]] | None = None,
    denied_status: int = 403,
) -> tuple[respx.Route, respx.Route, respx.Route]:
    configured_grants = (
        [{"node_id": SENSO_SCOPE.folder_node_id, "role": SensoFolderRole.VIEWER.value}]
        if grants is None
        else grants
    )
    grant_route = respx.get(f"{SENSO_BASE}/org/api-keys/{SENSO_SCOPE.key_id}/kb-permissions").mock(
        return_value=httpx.Response(200, json=configured_grants)
    )
    allowed_route = respx.get(
        f"{SENSO_BASE}/org/kb/nodes/{SENSO_SCOPE.folder_node_id}/children"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "nodes": [
                    {
                        "kb_node_id": "content_policy",
                        "name": "Identity policy",
                        "type": "document",
                    }
                ]
            },
        )
    )
    denied_route = respx.get(f"{SENSO_BASE}/org/kb/nodes/{SENSO_OUTSIDE_FOLDER_ID}/children").mock(
        return_value=httpx.Response(
            denied_status,
            json={"nodes": []} if 200 <= denied_status < 300 else {"error": "denied"},
        )
    )
    return grant_route, allowed_route, denied_route


@respx.mock
@pytest.mark.asyncio
async def test_senso_activation_and_scoped_operations_use_documented_contracts() -> None:
    grant_route, allowed_route, denied_route = _mock_senso_activation()
    search_route = respx.post(f"{SENSO_BASE}/org/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "answer": "The policy requires SSO.",
                "results": [
                    {
                        "content_id": "content_policy",
                        "title": "Identity policy",
                        "chunk_text": "All production SaaS must support SSO.",
                        "score": 0.97,
                        "version": 3,
                    }
                ],
                "total_results": 1,
                "processing_time_ms": 12,
            },
        )
    )
    content_route = respx.get(
        f"{SENSO_BASE}/org/kb/nodes/content_policy/content",
        params={"version": "3"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "title": "Identity policy",
                "text": "All production SaaS must support SSO.",
                "version": 3,
                "checksum": "sha256:policy-v3",
            },
        )
    )
    adapter = await SensoRestAdapter.activate(
        api_key="senso-test-secret",  # pragma: allowlist secret
        scope=SENSO_SCOPE,
        outside_folder_node_id=SENSO_OUTSIDE_FOLDER_ID,
    )
    try:
        result = await adapter.search(
            SensoSearchRequest(query="identity requirements", scope=SENSO_SCOPE)
        )
        browse_result = await adapter.browse(
            SensoBrowseRequest(
                folder_node_id=SENSO_SCOPE.folder_node_id,
                scope=SENSO_SCOPE,
            )
        )
        content_result = await adapter.get_content_version(
            SensoContentVersionRequest(
                node_id="content_policy",
                version=3,
                scope=SENSO_SCOPE,
            )
        )
    finally:
        await adapter.aclose()

    assert grant_route.called
    assert allowed_route.call_count == 2
    assert denied_route.called
    assert search_route.called
    assert content_route.called
    for activation_route in (grant_route, allowed_route, denied_route):
        assert activation_route.calls[0].request.headers["X-API-Key"] == "senso-test-secret"
    sent = json.loads(search_route.calls[0].request.content)
    assert sent == {"query": "identity requirements", "max_results": 5}
    assert search_route.calls[0].request.headers["X-API-Key"] == "senso-test-secret"
    assert adapter.scope == SENSO_SCOPE
    assert adapter.verification.direct_grants[0].role is SensoFolderRole.VIEWER
    assert adapter.verification.allowed_folder_browse_verified is True
    assert adapter.verification.cross_folder_denial_verified is True
    assert adapter.verification.key_identity_binding is SensoKeyIdentityBinding.NOT_DOCUMENTED
    assert result.hits[0].source_version == 3
    assert result.scope == SENSO_SCOPE
    assert result.truth_verified is False
    assert result.adapter.mode is AdapterMode.PRODUCTION
    assert browse_result.scope == SENSO_SCOPE
    assert browse_result.nodes[0].node_id == "content_policy"
    assert content_result.scope == SENSO_SCOPE
    assert content_result.version == 3
    assert "senso-test-secret" not in repr(adapter)


def test_senso_production_adapter_has_no_direct_unverified_constructor() -> None:
    with pytest.raises(TypeError, match="scoped activation"):
        SensoRestAdapter(api_key="senso-test-secret")  # pragma: allowlist secret


@respx.mock
@pytest.mark.asyncio
@pytest.mark.parametrize("denied_status", [403, 404])
async def test_senso_activation_accepts_documented_cross_folder_denial(
    denied_status: int,
) -> None:
    _mock_senso_activation(denied_status=denied_status)
    adapter = await SensoRestAdapter.activate(
        api_key="senso-test-secret",  # pragma: allowlist secret
        scope=SENSO_SCOPE,
        outside_folder_node_id=SENSO_OUTSIDE_FOLDER_ID,
    )
    await adapter.aclose()


@respx.mock
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "grants",
    [
        [],
        [{"node_id": SENSO_SCOPE.folder_node_id, "role": "editor"}],
        [
            {"node_id": SENSO_SCOPE.folder_node_id, "role": "viewer"},
            {"node_id": "folder_extra", "role": "viewer"},
        ],
    ],
)
async def test_senso_activation_rejects_any_grant_other_than_one_exact_viewer(
    grants: list[dict[str, str]],
) -> None:
    grant_route, allowed_route, denied_route = _mock_senso_activation(grants=grants)

    with pytest.raises(ProviderError) as captured:
        await SensoRestAdapter.activate(
            api_key="senso-test-secret",  # pragma: allowlist secret
            scope=SENSO_SCOPE,
            outside_folder_node_id=SENSO_OUTSIDE_FOLDER_ID,
        )

    assert captured.value.code is ProviderErrorCode.CONFIGURATION_INVALID
    assert grant_route.called
    assert allowed_route.called is False
    assert denied_route.called is False


@respx.mock
@pytest.mark.asyncio
async def test_senso_activation_rejects_a_successful_outside_folder_probe() -> None:
    grant_route, allowed_route, denied_route = _mock_senso_activation(denied_status=200)

    with pytest.raises(ProviderError) as captured:
        await SensoRestAdapter.activate(
            api_key="senso-test-secret",  # pragma: allowlist secret
            scope=SENSO_SCOPE,
            outside_folder_node_id=SENSO_OUTSIDE_FOLDER_ID,
        )

    assert captured.value.code is ProviderErrorCode.ACCESS_DENIED
    assert grant_route.called
    assert allowed_route.called
    assert denied_route.called


@respx.mock
@pytest.mark.asyncio
async def test_senso_scope_mismatch_is_rejected_before_any_operation_network_call() -> None:
    _, allowed_route, _ = _mock_senso_activation()
    search_route = respx.post(f"{SENSO_BASE}/org/search").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    content_route = respx.get(f"{SENSO_BASE}/org/kb/nodes/content_policy/content").mock(
        return_value=httpx.Response(200, json={})
    )
    adapter = await SensoRestAdapter.activate(
        api_key="senso-test-secret",  # pragma: allowlist secret
        scope=SENSO_SCOPE,
        outside_folder_node_id=SENSO_OUTSIDE_FOLDER_ID,
    )
    mismatched_scope = SensoFolderScope(
        key_id=SENSO_SCOPE.key_id,
        folder_node_id=SENSO_SCOPE.folder_node_id,
        purpose="different_purpose",
    )
    allowed_browse_calls_after_activation = allowed_route.call_count
    try:
        requests = (
            adapter.search(SensoSearchRequest(query="policy", scope=mismatched_scope)),
            adapter.browse(
                SensoBrowseRequest(
                    folder_node_id=SENSO_SCOPE.folder_node_id,
                    scope=mismatched_scope,
                )
            ),
            adapter.get_content_version(
                SensoContentVersionRequest(
                    node_id="content_policy",
                    version=3,
                    scope=mismatched_scope,
                )
            ),
        )
        for request in requests:
            with pytest.raises(ProviderError) as captured:
                await request
            assert captured.value.code is ProviderErrorCode.ACCESS_DENIED
    finally:
        await adapter.aclose()

    assert search_route.called is False
    assert content_route.called is False
    assert allowed_route.call_count == allowed_browse_calls_after_activation


@respx.mock
@pytest.mark.asyncio
async def test_provider_errors_are_stable_and_discard_upstream_secret_text() -> None:
    leaked_value = "provider-body-must-not-escape"
    _mock_senso_activation()
    respx.post(f"{SENSO_BASE}/org/search").mock(
        return_value=httpx.Response(
            401,
            json={"error": {"code": "AUTH_1001", "message": leaked_value}},
        )
    )
    adapter = await SensoRestAdapter.activate(
        api_key="another-test-secret",  # pragma: allowlist secret
        scope=SENSO_SCOPE,
        outside_folder_node_id=SENSO_OUTSIDE_FOLDER_ID,
    )
    try:
        with pytest.raises(ProviderError) as captured:
            await adapter.search(SensoSearchRequest(query="policy", scope=SENSO_SCOPE))
    finally:
        await adapter.aclose()

    error = captured.value
    assert error.code is ProviderErrorCode.AUTHENTICATION_FAILED
    assert error.retryable is False
    assert leaked_value not in str(error)
    assert leaked_value not in repr(error)
    assert "another-test-secret" not in str(error)


@respx.mock
@pytest.mark.asyncio
async def test_transport_error_does_not_retain_secret_bearing_request_context() -> None:
    _mock_senso_activation()
    respx.post(f"{SENSO_BASE}/org/search").mock(side_effect=httpx.ReadTimeout("upstream timeout"))
    adapter = await SensoRestAdapter.activate(
        api_key="context-must-not-retain-this-key",  # pragma: allowlist secret
        scope=SENSO_SCOPE,
        outside_folder_node_id=SENSO_OUTSIDE_FOLDER_ID,
    )
    try:
        with pytest.raises(ProviderError) as captured:
            await adapter.search(SensoSearchRequest(query="policy", scope=SENSO_SCOPE))
    finally:
        await adapter.aclose()

    error = captured.value
    assert error.code is ProviderErrorCode.TIMEOUT
    assert error.__context__ is None
    assert error.__cause__ is None
    assert "context-must-not-retain-this-key" not in repr(error)


@pytest.mark.asyncio
async def test_senso_activation_blocks_ssrf_inputs() -> None:
    with pytest.raises(ProviderError) as insecure:
        await SensoRestAdapter.activate(
            api_key="test-secret",  # pragma: allowlist secret
            scope=SENSO_SCOPE,
            outside_folder_node_id=SENSO_OUTSIDE_FOLDER_ID,
            base_url="http://apiv2.senso.ai/api/v1",
        )
    assert insecure.value.code is ProviderErrorCode.URL_NOT_ALLOWED


def test_https_and_exact_host_allowlists_block_ssrf_inputs() -> None:
    with pytest.raises(ProviderError) as untrusted:
        PravaHostedRestAdapter(
            secret_key="test-secret",  # pragma: allowlist secret
            base_url="https://sandbox.api.prava.space.attacker.example",
            merchant_hosts=frozenset({"merchant.example"}),
            callback_hosts=frozenset({"app.example"}),
        )
    assert untrusted.value.code is ProviderErrorCode.URL_NOT_ALLOWED

    with pytest.raises(ProviderError) as local_ip:
        ControlledMerchantRestAdapter(
            base_url="https://127.0.0.1",
            api_key="test-secret",  # pragma: allowlist secret
            allowed_hosts=frozenset({"127.0.0.1"}),
        )
    assert local_ip.value.code is ProviderErrorCode.URL_NOT_ALLOWED


@respx.mock
@pytest.mark.asyncio
async def test_prava_create_session_uses_hosted_full_checkout_and_omits_token() -> None:
    route = respx.post(f"{PRAVA_BASE}/v1/sessions").mock(
        return_value=httpx.Response(
            201,
            json={
                "session_id": "ses_demo",
                "session_token": "hosted-session-token",
                "iframe_url": "https://sandbox.collect.prava.space?session=ses_demo",
                "order_id": "ord_demo",
                "expires_at": "2026-08-02T12:15:00Z",
            },
        )
    )
    adapter = _prava_adapter()
    request = PravaSessionRequest(
        user_id="user_demo",
        user_email="buyer@example.com",
        total_amount="89.00",
        currency="USD",
        merchant=PravaMerchantDetails(
            name="Demo Merchant",
            url="https://merchant.example",
            country_code_iso2="US",
        ),
        products=(
            PravaProductDetails(
                description="Meeting intelligence team plan",
                unit_price="89.00",
                quantity=1,
                product_id="winner_team",
            ),
        ),
        callback_url="https://app.example/v1/prava/callback",
    )
    try:
        session = await adapter.create_session(request)
    finally:
        await adapter.aclose()

    sent = json.loads(route.calls[0].request.content)
    assert sent["integration_type"] == "full_checkout"
    assert sent["total_amount"] == "89.00"
    assert sent["currency"] == "USD"
    assert len(sent["purchase_context"]) == 1
    assert session.session_id == "ses_demo"
    assert session.hosted_url.startswith("https://sandbox.collect.prava.space")
    assert "session_token" not in {field.name for field in fields(session)}
    assert "hosted-session-token" not in repr(session)
    assert "prava-test-secret" not in repr(adapter)


@respx.mock
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider_merchant_url",
    ["https://merchant.example", None, _OMITTED],
    ids=["present", "null", "omitted"],
)
async def test_prava_credential_is_consumed_only_inside_isolated_checkout(
    provider_merchant_url: str | object | None,
) -> None:
    payment_route = respx.get(f"{PRAVA_BASE}/v1/sessions/ses_demo/payment-result").mock(
        side_effect=[
            httpx.Response(
                200,
                json=_awaiting_result(merchant_url=provider_merchant_url),
            ),
            httpx.Response(
                200,
                json={
                    "session_id": "ses_demo",
                    "order_id": "ord_demo",
                    "status": "completed",
                    "transactions": [],
                },
            ),
        ]
    )
    merchant_route = respx.post(f"{MERCHANT_API_BASE}/v1/checkout").mock(
        return_value=httpx.Response(
            200,
            json={
                "outcome": "APPROVED",
                "merchant_order_id": "merchant_order_demo",
                "authorization_code": "OK123",
                "response_code": "00",
            },
        )
    )
    report_route = respx.post(f"{PRAVA_BASE}/v1/sessions/ses_demo/report-status").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "confirmed",
                "txn_ref_id": "tli_demo",
                "txn_status": "APPROVED",
                "visa_confirmation": "SUCCESS",
            },
        )
    )
    prava = _prava_adapter()
    merchant = _merchant_adapter()
    try:
        result = await prava.execute_isolated_checkout(
            session_id="ses_demo",
            request=_merchant_request(),
            merchant=merchant,
        )
    finally:
        await prava.aclose()
        await merchant.aclose()

    assert payment_route.call_count == 2
    assert merchant_route.call_count == 1
    assert report_route.call_count == 1
    merchant_payload = json.loads(merchant_route.calls[0].request.content)
    assert merchant_payload["currency"] == "USD"
    assert merchant_payload["payment_method"]["token"] == SENSITIVE_CARD_TOKEN
    assert merchant_payload["payment_method"]["dynamic_cvv"] == SENSITIVE_CVV
    report_payload = json.loads(report_route.calls[0].request.content)
    assert "token" not in report_payload
    assert "dynamic_cvv" not in report_payload
    assert result.merchant.outcome is MerchantOutcome.APPROVED
    assert result.final_status is PravaPaymentStatus.COMPLETED
    assert result.provider_reported is True
    assert result.reconciliation_required is False
    safe_representations = " ".join((repr(result), repr(prava), repr(merchant)))
    assert SENSITIVE_CARD_TOKEN not in safe_representations
    assert SENSITIVE_CVV not in safe_representations


@respx.mock
@pytest.mark.asyncio
async def test_uncertain_merchant_dispatch_is_not_reported_or_retried() -> None:
    respx.get(f"{PRAVA_BASE}/v1/sessions/ses_demo/payment-result").mock(
        return_value=httpx.Response(200, json=_awaiting_result())
    )
    merchant_route = respx.post(f"{MERCHANT_API_BASE}/v1/checkout").mock(
        side_effect=httpx.ReadTimeout("merchant response timed out")
    )
    report_route = respx.post(f"{PRAVA_BASE}/v1/sessions/ses_demo/report-status").mock(
        return_value=httpx.Response(500)
    )
    prava = _prava_adapter()
    merchant = _merchant_adapter()
    try:
        result = await prava.execute_isolated_checkout(
            session_id="ses_demo",
            request=_merchant_request(),
            merchant=merchant,
        )
    finally:
        await prava.aclose()
        await merchant.aclose()

    assert merchant_route.call_count == 1
    assert report_route.call_count == 0
    assert result.merchant.outcome is MerchantOutcome.UNKNOWN
    assert result.provider_reported is False
    assert result.reconciliation_required is True
    assert SENSITIVE_CARD_TOKEN not in repr(result)


@respx.mock
@pytest.mark.asyncio
async def test_merchant_server_error_after_dispatch_is_treated_as_uncertain() -> None:
    respx.get(f"{PRAVA_BASE}/v1/sessions/ses_demo/payment-result").mock(
        return_value=httpx.Response(200, json=_awaiting_result())
    )
    merchant_route = respx.post(f"{MERCHANT_API_BASE}/v1/checkout").mock(
        return_value=httpx.Response(503, json={"error": "upstream unavailable"})
    )
    report_route = respx.post(f"{PRAVA_BASE}/v1/sessions/ses_demo/report-status").mock(
        return_value=httpx.Response(500)
    )
    prava = _prava_adapter()
    merchant = _merchant_adapter()
    try:
        result = await prava.execute_isolated_checkout(
            session_id="ses_demo",
            request=_merchant_request(),
            merchant=merchant,
        )
    finally:
        await prava.aclose()
        await merchant.aclose()

    assert merchant_route.call_count == 1
    assert report_route.call_count == 0
    assert result.merchant.outcome is MerchantOutcome.UNKNOWN
    assert result.reconciliation_required is True


@respx.mock
@pytest.mark.asyncio
async def test_controlled_merchant_verifies_expected_entitlement_quantity() -> None:
    route = respx.get(f"{MERCHANT_API_BASE}/v1/orders/merchant_order_demo/entitlements").mock(
        return_value=httpx.Response(
            200,
            json={
                "entitlements": [
                    {
                        "external_entitlement_id": "ent_wrong_product",
                        "type": "workspace_entitlement",
                        "status": "active",
                        "subject_id": "org_demo",
                        "product_id": "different_product",
                        "product_version": "2026.08",
                        "region": "US",
                        "scope": "organization",
                        "quantity": 99,
                        "access_probe_verified": True,
                    },
                    {
                        "external_entitlement_id": "ent_workspace",
                        "type": "workspace_entitlement",
                        "status": "active",
                        "subject_id": "org_demo",
                        "product_id": "winner_team",
                        "product_version": "2026.08",
                        "region": "US",
                        "scope": "organization",
                        "quantity": 1,
                        "access_probe_verified": True,
                    },
                    {
                        "external_entitlement_id": "ent_other",
                        "type": "seat_entitlement",
                        "status": "active",
                        "subject_id": "org_demo",
                        "quantity": 10,
                    },
                ]
            },
        )
    )
    merchant = _merchant_adapter()
    try:
        result = await merchant.verify_entitlements(
            EntitlementVerificationRequest(
                merchant_order_id="merchant_order_demo",
                entitlement_type="workspace_entitlement",
                minimum_quantity=1,
                subject_id="org_demo",
                product_id="winner_team",
                product_version="2026.08",
                region="US",
                scope="organization",
                require_access_probe=True,
            )
        )
    finally:
        await merchant.aclose()

    assert route.called
    assert result.status is EntitlementVerificationStatus.VERIFIED
    assert result.observed_quantity == 1
    assert result.external_entitlement_ids == ("ent_workspace",)
    assert result.access_probe_verified is True
    assert result.provider_confirmed is True


@respx.mock
@pytest.mark.asyncio
async def test_controlled_merchant_refund_is_idempotent_and_reconciles_exact_terms() -> None:
    create_route = respx.post(f"{MERCHANT_API_BASE}/v1/orders/merchant_order_demo/refunds").mock(
        return_value=httpx.Response(
            202,
            json={
                "status": "PENDING",
                "refund_id": "refund_demo",
                "refunded_amount": "0.00",
                "currency": "USD",
                "entitlements_revoked": False,
            },
        )
    )
    reconcile_route = respx.get(
        f"{MERCHANT_API_BASE}/v1/refunds/by-idempotency-key/refund_demo_v1"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "REFUNDED",
                "refund_id": "refund_demo",
                "refunded_amount": "89.00",
                "currency": "USD",
                "entitlements_revoked": True,
            },
        )
    )
    request = MerchantRefundRequest(
        merchant_order_id="merchant_order_demo",
        idempotency_key="refund_demo_v1",
        amount="89.00",
        currency="USD",
        reason_code="PRODUCT_NOT_ADOPTED",
    )
    merchant = _merchant_adapter()
    try:
        pending = await merchant.request_refund(request)
        completed = await merchant.reconcile_refund(request)
    finally:
        await merchant.aclose()

    assert create_route.calls[0].request.headers["Idempotency-Key"] == "refund_demo_v1"
    assert json.loads(create_route.calls[0].request.content) == {
        "amount": "89.00",
        "currency": "USD",
        "reason_code": "PRODUCT_NOT_ADOPTED",
    }
    assert reconcile_route.called
    assert pending.status is RefundOutcomeStatus.PENDING
    assert completed.status is RefundOutcomeStatus.REFUNDED
    assert completed.refunded_amount == "89.00"
    assert completed.entitlements_revoked is True
    assert completed.provider_confirmed is True


@pytest.mark.asyncio
async def test_development_fixtures_are_structurally_non_production() -> None:
    senso = DevelopmentFixtureSensoAdapter(
        scope=SENSO_SCOPE,
        hits=(
            SensoEvidenceHit(
                content_id="fixture_content",
                title="Fixture evidence",
                chunk_text="Deterministic local text",
                score=1.0,
            ),
        ),
    )
    merchant = DevelopmentFixtureMerchantAdapter()
    prava = DevelopmentFixturePravaAdapter()

    senso_result = await senso.search(SensoSearchRequest(query="fixture", scope=SENSO_SCOPE))
    entitlement_result = await merchant.verify_entitlements(
        EntitlementVerificationRequest(
            merchant_order_id="fixture_order",
            entitlement_type="workspace_entitlement",
            minimum_quantity=1,
        )
    )
    checkout_result = await prava.execute_isolated_checkout(
        session_id="fixture_session",
        request=MerchantCheckoutRequest(
            purchase_intent_id="fixture_intent",
            prava_order_id="fixture_order",
            idempotency_key="fixture_key",
            merchant_url="https://fixture.invalid",
            amount="1.00",
            currency="USD",
        ),
        merchant=merchant,
    )
    refund_result = await merchant.request_refund(
        MerchantRefundRequest(
            merchant_order_id="fixture_order",
            idempotency_key="fixture_refund",
            amount="1.00",
            currency="USD",
            reason_code="FIXTURE_ONLY",
        )
    )

    descriptors = (
        senso.descriptor,
        merchant.descriptor,
        prava.descriptor,
        senso_result.adapter,
        entitlement_result.adapter,
        checkout_result.adapter,
        refund_result.adapter,
    )
    assert all(item.mode is AdapterMode.DEVELOPMENT_FIXTURE for item in descriptors)
    assert all(item.production_capable is False for item in descriptors)
    assert all(item.production_verified is False for item in descriptors)
    assert senso.scope == SENSO_SCOPE
    assert refund_result.status is RefundOutcomeStatus.PENDING
    assert refund_result.provider_confirmed is False
    assert senso_result.scope == SENSO_SCOPE
    assert entitlement_result.provider_confirmed is False
    assert checkout_result.provider_reported is False

    mismatched_scope = SensoFolderScope(
        key_id=SENSO_SCOPE.key_id,
        folder_node_id=SENSO_SCOPE.folder_node_id,
        purpose="different_fixture_purpose",
    )
    with pytest.raises(ProviderError) as captured:
        await senso.search(SensoSearchRequest(query="fixture", scope=mismatched_scope))
    assert captured.value.code is ProviderErrorCode.ACCESS_DENIED


def test_temporal_contracts_cannot_hold_prava_credentials() -> None:
    workflow_input = PurchaseCheckoutWorkflowInput(
        organization_id="org_consultco",
        purchase_intent_id="pi_demo",
        intent_hash="sha256:demo",
        prava_session_id="ses_demo",
        merchant_adapter_id="merchant_demo",
        idempotency_key="checkout_pi_demo_v1",
    )
    assert_all_contract_schemas_are_credential_free()
    assert_credential_free_contract(workflow_input)
    serialized = json.dumps(asdict(workflow_input), sort_keys=True)
    forbidden_names = {
        "card",
        "credential",
        "cvv",
        "expiry_month",
        "expiry_year",
        "pan",
        "payment_token",
        "secret",
    }
    assert all(name not in serialized.lower() for name in forbidden_names)

    contract_types = (
        IsolatedCheckoutActivityInput,
        CheckoutActivityResult,
        ReconcileActivityInput,
        PurchaseCheckoutWorkflowInput,
        PurchaseCheckoutWorkflowResult,
    )
    field_names = {
        field.name for contract_type in contract_types for field in fields(contract_type)
    }
    assert all(name not in field_names for name in forbidden_names)


@pytest.mark.asyncio
async def test_temporal_activity_discards_unexpected_secret_bearing_error_context() -> None:
    class ExplodingCoordinator:
        async def execute_isolated_checkout(
            self,
            request: IsolatedCheckoutActivityInput,
        ) -> CheckoutActivityResult:
            del request
            raise RuntimeError(f"unexpected provider failure {SENSITIVE_CARD_TOKEN}")

        async def reconcile_checkout(
            self,
            request: ReconcileActivityInput,
        ) -> CheckoutActivityResult:
            del request
            raise RuntimeError(f"unexpected provider failure {SENSITIVE_CARD_TOKEN}")

    activities = CheckoutActivities(ExplodingCoordinator())
    request = IsolatedCheckoutActivityInput(
        organization_id="org_consultco",
        purchase_intent_id="pi_demo",
        intent_hash="sha256:demo",
        prava_session_id="ses_demo",
        merchant_adapter_id="merchant_demo",
        idempotency_key="checkout_pi_demo_v1",
    )
    with pytest.raises(ApplicationError) as captured:
        await activities.execute_isolated_checkout(request)

    error = captured.value
    assert SENSITIVE_CARD_TOKEN not in str(error)
    assert SENSITIVE_CARD_TOKEN not in repr(error)
    assert error.__context__ is None
    assert error.__cause__ is None
