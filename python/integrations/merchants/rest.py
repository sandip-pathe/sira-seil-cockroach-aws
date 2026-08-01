"""HTTP adapter for a certified controlled merchant/entitlement service."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast
from urllib.parse import quote

import httpx

from integrations.common import AdapterDescriptor
from integrations.errors import (
    ProviderError,
    ProviderErrorCode,
    raise_for_status,
)
from integrations.merchants.models import (
    EntitlementVerificationRequest,
    EntitlementVerificationResult,
    EntitlementVerificationStatus,
    MerchantCheckoutOutcome,
    MerchantCheckoutRequest,
    MerchantOutcome,
)
from integrations.security import HttpsUrlPolicy, validate_identifier

MERCHANT_PROVIDER = "controlled_merchant"
DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=20.0, write=10.0, pool=5.0)


def _object_payload(response: httpx.Response, *, operation: str) -> Mapping[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        raise ProviderError(
            provider=MERCHANT_PROVIDER,
            operation=operation,
            code=ProviderErrorCode.INVALID_RESPONSE,
            retryable=False,
            status_code=response.status_code,
        ) from None
    return cast(Mapping[str, Any], payload)


class ControlledMerchantRestAdapter:
    """Real HTTPS path for checkout, order reconciliation, and entitlement probes.

    This adapter targets a configured merchant integration owned or certified by the
    deployment.  It makes no blanket claim that arbitrary merchants support this API.
    """

    __slots__ = ("_api_key", "_base_url", "_client", "_descriptor")

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        allowed_hosts: frozenset[str],
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    ) -> None:
        if not api_key.strip():
            raise ProviderError(
                provider=MERCHANT_PROVIDER,
                operation="configure",
                code=ProviderErrorCode.CONFIGURATION_INVALID,
                retryable=False,
            ) from None
        policy = HttpsUrlPolicy(provider=MERCHANT_PROVIDER, allowed_hosts=allowed_hosts)
        self._base_url = policy.validate(
            base_url,
            operation="configure",
            allow_query=False,
        ).rstrip("/")
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
        )
        self._descriptor = AdapterDescriptor.production(MERCHANT_PROVIDER)

    @property
    def descriptor(self) -> AdapterDescriptor:
        return self._descriptor

    def __repr__(self) -> str:
        return f"ControlledMerchantRestAdapter(base_url={self._base_url!r}, api_key=<redacted>)"

    async def _request(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        json: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        request_headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }
        if headers:
            request_headers.update(headers)
        transport_code: ProviderErrorCode | None = None
        try:
            response = await self._client.request(
                method,
                f"{self._base_url}{path}",
                headers=request_headers,
                json=json,
            )
        except httpx.TimeoutException:
            transport_code = ProviderErrorCode.TIMEOUT
        except httpx.HTTPError:
            transport_code = ProviderErrorCode.UNAVAILABLE
        if transport_code is not None:
            raise ProviderError(
                provider=MERCHANT_PROVIDER,
                operation=operation,
                code=transport_code,
                retryable=True,
            ) from None
        return response

    def _parse_checkout(
        self,
        response: httpx.Response,
        *,
        operation: str,
    ) -> MerchantCheckoutOutcome:
        if response.status_code == 402:
            return MerchantCheckoutOutcome(
                outcome=MerchantOutcome.DECLINED,
                merchant_order_id=None,
                authorization_code=None,
                response_code=None,
                adapter=self.descriptor,
                provider_confirmed=True,
            )
        raise_for_status(response.status_code, provider=MERCHANT_PROVIDER, operation=operation)
        payload = _object_payload(response, operation=operation)
        outcome_value = payload.get("outcome", payload.get("status"))
        try:
            if not isinstance(outcome_value, str):
                raise ValueError
            outcome = MerchantOutcome(outcome_value.upper())
            order_value = payload.get("merchant_order_id", payload.get("order_id"))
            merchant_order_id = order_value if isinstance(order_value, str) else None
            authorization_value = payload.get("authorization_code")
            authorization_code = (
                authorization_value if isinstance(authorization_value, str) else None
            )
            response_value = payload.get("response_code")
            response_code = response_value if isinstance(response_value, str) else None
            return MerchantCheckoutOutcome(
                outcome=outcome,
                merchant_order_id=merchant_order_id,
                authorization_code=authorization_code,
                response_code=response_code,
                adapter=self.descriptor,
                provider_confirmed=True,
            )
        except (TypeError, ValueError):
            raise ProviderError(
                provider=MERCHANT_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.INVALID_RESPONSE,
                retryable=False,
            ) from None

    async def checkout_with_ephemeral_card(
        self,
        request: MerchantCheckoutRequest,
        *,
        card_token: str,
        dynamic_cvv: str,
        expiry_month: str,
        expiry_year: str,
    ) -> MerchantCheckoutOutcome:
        operation = "checkout"
        if not all((card_token, dynamic_cvv, expiry_month, expiry_year)):
            raise ProviderError(
                provider=MERCHANT_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.INVALID_REQUEST,
                retryable=False,
            ) from None
        dispatch_failed = False
        try:
            response = await self._client.post(
                f"{self._base_url}/v1/checkout",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Accept": "application/json",
                    "Idempotency-Key": request.idempotency_key,
                },
                json={
                    "purchase_intent_id": request.purchase_intent_id,
                    "prava_order_id": request.prava_order_id,
                    "amount": request.amount,
                    "currency": request.currency,
                    "payment_method": {
                        "type": "prava_network_token",
                        "token": card_token,
                        "dynamic_cvv": dynamic_cvv,
                        "expiry_month": expiry_month,
                        "expiry_year": expiry_year,
                    },
                },
            )
        except httpx.HTTPError:
            dispatch_failed = True
        if dispatch_failed:
            # Raise after the except scope ends. This prevents the original request,
            # whose JSON body contains the ephemeral card, from being retained as
            # ``ProviderError.__context__`` by Python.
            raise ProviderError(
                provider=MERCHANT_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.CHECKOUT_UNCERTAIN,
                retryable=False,
            ) from None
        if response.status_code in {408, 409, 425, 429} or response.status_code >= 500:
            # A response that does not definitively reject the charge cannot prove the
            # merchant did not create an order. Reconcile by idempotency key; never
            # retry checkout directly.
            raise ProviderError(
                provider=MERCHANT_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.CHECKOUT_UNCERTAIN,
                retryable=False,
                status_code=response.status_code,
            ) from None
        return self._parse_checkout(response, operation=operation)

    async def reconcile_order(self, request: MerchantCheckoutRequest) -> MerchantCheckoutOutcome:
        operation = "reconcile_order"
        key = quote(request.idempotency_key, safe="")
        response = await self._request(
            "GET",
            f"/v1/orders/by-idempotency-key/{key}",
            operation=operation,
        )
        return self._parse_checkout(response, operation=operation)

    async def verify_entitlements(
        self,
        request: EntitlementVerificationRequest,
    ) -> EntitlementVerificationResult:
        operation = "verify_entitlements"
        order_id = validate_identifier(
            request.merchant_order_id,
            provider=MERCHANT_PROVIDER,
            operation=operation,
        )
        response = await self._request(
            "GET",
            f"/v1/orders/{order_id}/entitlements",
            operation=operation,
        )
        raise_for_status(response.status_code, provider=MERCHANT_PROVIDER, operation=operation)
        payload = _object_payload(response, operation=operation)
        raw_entitlements = payload.get("entitlements")
        if not isinstance(raw_entitlements, list):
            raise ProviderError(
                provider=MERCHANT_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.INVALID_RESPONSE,
                retryable=False,
            ) from None
        identifiers: list[str] = []
        observed_quantity = 0
        access_probe_verified = False
        try:
            for item in raw_entitlements:
                if not isinstance(item, dict):
                    raise TypeError
                entitlement_type = item.get("type")
                status = item.get("status")
                subject_id = item.get("subject_id")
                if entitlement_type != request.entitlement_type or status != "active":
                    continue
                if request.subject_id is not None and subject_id != request.subject_id:
                    continue
                expected_dimensions = {
                    "product_id": request.product_id,
                    "product_version": request.product_version,
                    "region": request.region,
                    "scope": request.scope,
                }
                if any(
                    expected is not None and item.get(name) != expected
                    for name, expected in expected_dimensions.items()
                ):
                    continue
                item_access_verified = item.get("access_probe_verified") is True
                if request.require_access_probe and not item_access_verified:
                    continue
                external_id = item.get("external_entitlement_id", item.get("id"))
                quantity = item.get("quantity", 1)
                if (
                    not isinstance(external_id, str)
                    or not isinstance(quantity, int)
                    or isinstance(quantity, bool)
                    or quantity < 1
                ):
                    raise TypeError
                identifiers.append(external_id)
                observed_quantity += quantity
                access_probe_verified = access_probe_verified or item_access_verified
        except TypeError:
            raise ProviderError(
                provider=MERCHANT_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.INVALID_RESPONSE,
                retryable=False,
            ) from None
        if observed_quantity >= request.minimum_quantity:
            status = EntitlementVerificationStatus.VERIFIED
        elif observed_quantity > 0:
            status = EntitlementVerificationStatus.PARTIAL
        else:
            status = EntitlementVerificationStatus.FAILED_RETRYABLE
        return EntitlementVerificationResult(
            status=status,
            observed_quantity=observed_quantity,
            external_entitlement_ids=tuple(identifiers),
            access_probe_verified=access_probe_verified,
            adapter=self.descriptor,
            provider_confirmed=True,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
