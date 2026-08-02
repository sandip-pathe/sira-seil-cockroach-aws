"""Prava hosted REST integration with an isolated one-time credential operation."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, NoReturn, cast

import httpx

from integrations.common import AdapterDescriptor, AdapterMode
from integrations.errors import (
    ProviderError,
    ProviderErrorCode,
    raise_for_status,
)
from integrations.merchants.models import (
    MerchantCheckoutOutcome,
    MerchantCheckoutRequest,
    MerchantOutcome,
)
from integrations.merchants.protocols import ControlledMerchantAdapter
from integrations.prava.models import (
    PravaCheckoutResult,
    PravaHostedSession,
    PravaPaymentStatus,
    PravaReportResult,
    PravaSessionRequest,
)
from integrations.security import HttpsUrlPolicy, validate_identifier

PRAVA_PROVIDER = "prava"
DEFAULT_PRAVA_BASE_URL = "https://sandbox.api.prava.space"
DEFAULT_PRAVA_API_HOSTS = frozenset({"sandbox.api.prava.space", "api.prava.space"})
DEFAULT_PRAVA_CHECKOUT_HOSTS = frozenset(
    {
        "checkout.prava.space",
        "collect.prava.space",
        "sandbox.checkout.prava.space",
        "sandbox.collect.prava.space",
    }
)
DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0)
_SECRET_FIELDS = frozenset({"token", "dynamic_cvv", "expiry_month", "expiry_year"})


def _object_payload(response: httpx.Response, *, operation: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        raise ProviderError(
            provider=PRAVA_PROVIDER,
            operation=operation,
            code=ProviderErrorCode.INVALID_RESPONSE,
            retryable=False,
            status_code=response.status_code,
        ) from None
    return cast(dict[str, Any], payload)


def _scrub_credentials(value: object) -> None:
    """Remove credential values from a mutable provider payload in place."""

    if isinstance(value, dict):
        for key in tuple(value):
            if key in _SECRET_FIELDS:
                value[key] = None
            else:
                _scrub_credentials(value[key])
    elif isinstance(value, list):
        for item in value:
            _scrub_credentials(item)


def _parse_timestamp(value: object, *, operation: str) -> datetime:
    if not isinstance(value, str):
        raise ProviderError(
            provider=PRAVA_PROVIDER,
            operation=operation,
            code=ProviderErrorCode.INVALID_RESPONSE,
            retryable=False,
        ) from None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ProviderError(
            provider=PRAVA_PROVIDER,
            operation=operation,
            code=ProviderErrorCode.INVALID_RESPONSE,
            retryable=False,
        ) from None


class _EphemeralPaymentCredential:
    """Single-use, non-serializable credential local to one checkout stack frame."""

    __slots__ = ("__cvv", "__month", "__token", "__used", "__year")

    def __init__(self, token: str, cvv: str, month: str, year: str) -> None:
        self.__token: str | None = token
        self.__cvv: str | None = cvv
        self.__month: str | None = month
        self.__year: str | None = year
        self.__used = False

    def __repr__(self) -> str:
        return "_EphemeralPaymentCredential(<redacted>)"

    def __str__(self) -> str:
        return "<redacted-payment-credential>"

    def __reduce__(self) -> NoReturn:
        raise TypeError("payment credentials are not serializable")

    async def consume(
        self,
        checkout: Callable[..., Awaitable[MerchantCheckoutOutcome]],
        request: MerchantCheckoutRequest,
    ) -> MerchantCheckoutOutcome:
        if self.__used:
            raise ProviderError(
                provider=PRAVA_PROVIDER,
                operation="isolated_checkout",
                code=ProviderErrorCode.INVALID_STATE,
                retryable=False,
            ) from None
        token, cvv, month, year = self.__token, self.__cvv, self.__month, self.__year
        if not all((token, cvv, month, year)):
            raise ProviderError(
                provider=PRAVA_PROVIDER,
                operation="isolated_checkout",
                code=ProviderErrorCode.INVALID_RESPONSE,
                retryable=False,
            ) from None
        self.__used = True
        self.__token = self.__cvv = self.__month = self.__year = None
        try:
            return await checkout(
                request,
                card_token=cast(str, token),
                dynamic_cvv=cast(str, cvv),
                expiry_month=cast(str, month),
                expiry_year=cast(str, year),
            )
        finally:
            token = cvv = month = year = None


class PravaHostedRestAdapter:
    """Real Prava REST adapter for one hosted, merchant-specific checkout.

    There is intentionally no public method that returns or even polls a payment
    credential.  ``execute_isolated_checkout`` is the sole credential boundary: it
    polls, validates, consumes, scrubs, and returns only a safe outcome.
    """

    __slots__ = (
        "_base_url",
        "_callback_policy",
        "_client",
        "_descriptor",
        "_hosted_policy",
        "_merchant_policy",
        "_secret_key",
    )

    def __init__(
        self,
        *,
        secret_key: str,
        merchant_hosts: frozenset[str],
        callback_hosts: frozenset[str],
        base_url: str = DEFAULT_PRAVA_BASE_URL,
        api_hosts: frozenset[str] = DEFAULT_PRAVA_API_HOSTS,
        hosted_checkout_hosts: frozenset[str] = DEFAULT_PRAVA_CHECKOUT_HOSTS,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    ) -> None:
        if not secret_key.strip():
            raise ProviderError(
                provider=PRAVA_PROVIDER,
                operation="configure",
                code=ProviderErrorCode.CONFIGURATION_INVALID,
                retryable=False,
            ) from None
        api_policy = HttpsUrlPolicy(provider=PRAVA_PROVIDER, allowed_hosts=api_hosts)
        self._base_url = api_policy.validate(
            base_url,
            operation="configure",
            allow_query=False,
        ).rstrip("/")
        self._secret_key = secret_key
        self._merchant_policy = HttpsUrlPolicy(
            provider=PRAVA_PROVIDER,
            allowed_hosts=merchant_hosts,
        )
        self._callback_policy = HttpsUrlPolicy(
            provider=PRAVA_PROVIDER,
            allowed_hosts=callback_hosts,
        )
        self._hosted_policy = HttpsUrlPolicy(
            provider=PRAVA_PROVIDER,
            allowed_hosts=hosted_checkout_hosts,
        )
        self._client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
        )
        self._descriptor = AdapterDescriptor.production(PRAVA_PROVIDER)

    @property
    def descriptor(self) -> AdapterDescriptor:
        return self._descriptor

    def __repr__(self) -> str:
        return f"PravaHostedRestAdapter(base_url={self._base_url!r}, secret_key=<redacted>)"

    async def _request(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        json: Mapping[str, object] | None = None,
    ) -> httpx.Response:
        transport_code: ProviderErrorCode | None = None
        try:
            response = await self._client.request(
                method,
                f"{self._base_url}{path}",
                headers={
                    "Authorization": f"Bearer {self._secret_key}",
                    "Accept": "application/json",
                },
                json=json,
            )
        except httpx.TimeoutException:
            transport_code = ProviderErrorCode.TIMEOUT
        except httpx.HTTPError:
            transport_code = ProviderErrorCode.UNAVAILABLE
        if transport_code is not None:
            raise ProviderError(
                provider=PRAVA_PROVIDER,
                operation=operation,
                code=transport_code,
                retryable=True,
            ) from None
        raise_for_status(response.status_code, provider=PRAVA_PROVIDER, operation=operation)
        return response

    async def create_session(self, request: PravaSessionRequest) -> PravaHostedSession:
        operation = "create_session"
        merchant_url = self._merchant_policy.validate(
            request.merchant.url,
            operation=operation,
            allow_query=False,
        )
        callback_url = self._callback_policy.validate(
            request.callback_url,
            operation=operation,
        )
        products: list[dict[str, object]] = []
        for product in request.products:
            item: dict[str, object] = {
                "description": product.description,
                "unit_price": product.unit_price,
                "quantity": product.quantity,
            }
            if product.product_id is not None:
                item["product_id"] = product.product_id
            products.append(item)
        response = await self._request(
            "POST",
            "/v1/sessions",
            operation=operation,
            json={
                "user_id": request.user_id,
                "user_email": request.user_email,
                "total_amount": request.total_amount,
                "currency": request.currency,
                "integration_type": "full_checkout",
                "callback_url": callback_url,
                "purchase_context": [
                    {
                        "merchant_details": {
                            "name": request.merchant.name,
                            "url": merchant_url,
                            "country_code_iso2": request.merchant.country_code_iso2,
                        },
                        "product_details": products,
                    }
                ],
            },
        )
        payload = _object_payload(response, operation=operation)
        try:
            session_id = payload["session_id"]
            hosted_url_value = payload.get("iframe_url")
            order_id = payload["order_id"]
            if (
                not isinstance(session_id, str)
                or not isinstance(hosted_url_value, str)
                or not isinstance(order_id, str)
            ):
                raise TypeError
            hosted_url = self._hosted_policy.validate(hosted_url_value, operation=operation)
            return PravaHostedSession(
                session_id=session_id,
                hosted_url=hosted_url,
                order_id=order_id,
                expires_at=_parse_timestamp(payload.get("expires_at"), operation=operation),
                adapter=self.descriptor,
            )
        except (KeyError, TypeError):
            raise ProviderError(
                provider=PRAVA_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.INVALID_RESPONSE,
                retryable=False,
            ) from None
        finally:
            # Session tokens are not needed by the backend after the hosted URL is built.
            payload["session_token"] = None

    async def _poll_payment_result(self, session_id: str) -> dict[str, Any]:
        operation = "isolated_checkout"
        safe_session_id = validate_identifier(
            session_id,
            provider=PRAVA_PROVIDER,
            operation=operation,
        )
        response = await self._request(
            "GET",
            f"/v1/sessions/{safe_session_id}/payment-result",
            operation=operation,
        )
        return _object_payload(response, operation=operation)

    def _extract_credential(
        self,
        payload: dict[str, Any],
        *,
        session_id: str,
        request: MerchantCheckoutRequest,
    ) -> tuple[str, _EphemeralPaymentCredential]:
        operation = "isolated_checkout"
        status_value = payload.get("status")
        if not isinstance(status_value, str):
            raise ProviderError(
                provider=PRAVA_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.INVALID_RESPONSE,
                retryable=False,
            ) from None
        try:
            status = PravaPaymentStatus(status_value)
        except (TypeError, ValueError):
            raise ProviderError(
                provider=PRAVA_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.INVALID_RESPONSE,
                retryable=False,
            ) from None
        if status is PravaPaymentStatus.PENDING:
            raise ProviderError(
                provider=PRAVA_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.PENDING,
                retryable=True,
            ) from None
        if status is not PravaPaymentStatus.AWAITING_RESULT:
            raise ProviderError(
                provider=PRAVA_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.INVALID_STATE,
                retryable=False,
            ) from None
        # Prava's documented payment-result response does not repeat currency.
        # Currency is bound when the session is created and remains on the
        # canonical Purchase Intent/merchant request; exact session and order
        # checks here prevent a credential from being substituted across them.
        if (
            payload.get("session_id") != session_id
            or payload.get("order_id") != request.prava_order_id
        ):
            raise ProviderError(
                provider=PRAVA_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.INVALID_RESPONSE,
                retryable=False,
            ) from None
        transactions = payload.get("transactions")
        if not isinstance(transactions, list):
            transactions = []
        line_items: list[dict[str, Any]] = []
        for transaction in transactions:
            if not isinstance(transaction, dict):
                continue
            raw_lines = transaction.get("line_items")
            if isinstance(raw_lines, list):
                line_items.extend(item for item in raw_lines if isinstance(item, dict))
        if len(line_items) != 1:
            raise ProviderError(
                provider=PRAVA_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.INVALID_RESPONSE,
                retryable=False,
            ) from None
        item = line_items[0]
        transaction_reference = item.get("txn_ref_id")
        merchant_url_value = item.get("merchant_url")
        amount_value = item.get("total_amount")
        if (
            not isinstance(transaction_reference, str)
            or not isinstance(amount_value, str)
            or (merchant_url_value is not None and not isinstance(merchant_url_value, str))
        ):
            raise ProviderError(
                provider=PRAVA_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.INVALID_RESPONSE,
                retryable=False,
            ) from None
        expected_url = self._merchant_policy.validate(
            request.merchant_url,
            operation=operation,
            allow_query=False,
        )
        merchant_url_matches = True
        if merchant_url_value is not None:
            actual_url = self._merchant_policy.validate(
                merchant_url_value,
                operation=operation,
                allow_query=False,
            )
            merchant_url_matches = actual_url == expected_url
        try:
            amount_matches = Decimal(amount_value) == Decimal(request.amount)
        except InvalidOperation:
            amount_matches = False
        if not merchant_url_matches or not amount_matches:
            raise ProviderError(
                provider=PRAVA_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.INVALID_RESPONSE,
                retryable=False,
            ) from None
        token = item.pop("token", None)
        cvv = item.pop("dynamic_cvv", None)
        month = item.pop("expiry_month", None)
        year = item.pop("expiry_year", None)
        if not all(isinstance(value, str) and value for value in (token, cvv, month, year)):
            raise ProviderError(
                provider=PRAVA_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.INVALID_RESPONSE,
                retryable=False,
            ) from None
        return transaction_reference, _EphemeralPaymentCredential(
            cast(str, token),
            cast(str, cvv),
            cast(str, month),
            cast(str, year),
        )

    async def _report(
        self,
        *,
        session_id: str,
        transaction_reference: str,
        outcome: MerchantCheckoutOutcome,
    ) -> PravaReportResult:
        operation = "report_status"
        safe_session_id = validate_identifier(
            session_id,
            provider=PRAVA_PROVIDER,
            operation=operation,
        )
        safe_reference = validate_identifier(
            transaction_reference,
            provider=PRAVA_PROVIDER,
            operation=operation,
        )
        if outcome.outcome is MerchantOutcome.UNKNOWN:
            raise ProviderError(
                provider=PRAVA_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.INVALID_STATE,
                retryable=False,
            ) from None
        body: dict[str, object] = {
            "txn_ref_id": safe_reference,
            "txn_status": outcome.outcome.value,
            "txn_type": "PURCHASE",
        }
        if outcome.authorization_code is not None:
            body["authorization_code"] = outcome.authorization_code
        if outcome.response_code is not None:
            body["response_code"] = outcome.response_code
        response = await self._request(
            "POST",
            f"/v1/sessions/{safe_session_id}/report-status",
            operation=operation,
            json=body,
        )
        payload = _object_payload(response, operation=operation)
        if payload.get("status") != "confirmed" or payload.get("txn_ref_id") != safe_reference:
            raise ProviderError(
                provider=PRAVA_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.INVALID_RESPONSE,
                retryable=False,
            ) from None
        return PravaReportResult(
            session_id=safe_session_id,
            transaction_reference=safe_reference,
            provider_confirmed=True,
            adapter=self.descriptor,
        )

    async def report_known_outcome(
        self,
        *,
        session_id: str,
        transaction_reference: str,
        outcome: MerchantCheckoutOutcome,
    ) -> PravaReportResult:
        return await self._report(
            session_id=session_id,
            transaction_reference=transaction_reference,
            outcome=outcome,
        )

    async def execute_isolated_checkout(
        self,
        *,
        session_id: str,
        request: MerchantCheckoutRequest,
        merchant: ControlledMerchantAdapter,
    ) -> PravaCheckoutResult:
        operation = "isolated_checkout"
        if merchant.descriptor.mode is not AdapterMode.PRODUCTION:
            raise ProviderError(
                provider=PRAVA_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.FIXTURE_ONLY,
                retryable=False,
            ) from None
        payload = await self._poll_payment_result(session_id)
        try:
            transaction_reference, credential = self._extract_credential(
                payload,
                session_id=session_id,
                request=request,
            )
        finally:
            _scrub_credentials(payload)
        try:
            merchant_outcome = await credential.consume(
                merchant.checkout_with_ephemeral_card,
                request,
            )
        except ProviderError as exc:
            if exc.code is not ProviderErrorCode.CHECKOUT_UNCERTAIN:
                raise
            merchant_outcome = MerchantCheckoutOutcome(
                outcome=MerchantOutcome.UNKNOWN,
                merchant_order_id=None,
                authorization_code=None,
                response_code=None,
                adapter=merchant.descriptor,
                provider_confirmed=False,
            )
        if merchant_outcome.outcome is MerchantOutcome.UNKNOWN:
            return PravaCheckoutResult(
                session_id=session_id,
                prava_order_id=request.prava_order_id,
                transaction_reference=transaction_reference,
                merchant=merchant_outcome,
                provider_reported=False,
                final_status=PravaPaymentStatus.AWAITING_RESULT,
                reconciliation_required=True,
                adapter=self.descriptor,
            )
        try:
            await self._report(
                session_id=session_id,
                transaction_reference=transaction_reference,
                outcome=merchant_outcome,
            )
        except ProviderError:
            return PravaCheckoutResult(
                session_id=session_id,
                prava_order_id=request.prava_order_id,
                transaction_reference=transaction_reference,
                merchant=merchant_outcome,
                provider_reported=False,
                final_status=PravaPaymentStatus.AWAITING_RESULT,
                reconciliation_required=True,
                adapter=self.descriptor,
            )
        final_payload = await self._poll_payment_result(session_id)
        final_status_value = final_payload.get("status")
        if not isinstance(final_status_value, str):
            _scrub_credentials(final_payload)
            raise ProviderError(
                provider=PRAVA_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.INVALID_RESPONSE,
                retryable=False,
            ) from None
        try:
            final_status = PravaPaymentStatus(final_status_value)
        except (TypeError, ValueError):
            raise ProviderError(
                provider=PRAVA_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.INVALID_RESPONSE,
                retryable=False,
            ) from None
        finally:
            _scrub_credentials(final_payload)
        expected_final = (
            PravaPaymentStatus.COMPLETED
            if merchant_outcome.outcome is MerchantOutcome.APPROVED
            else PravaPaymentStatus.FAILED
        )
        if final_status is not expected_final:
            return PravaCheckoutResult(
                session_id=session_id,
                prava_order_id=request.prava_order_id,
                transaction_reference=transaction_reference,
                merchant=merchant_outcome,
                provider_reported=True,
                final_status=final_status,
                reconciliation_required=True,
                adapter=self.descriptor,
            )
        return PravaCheckoutResult(
            session_id=session_id,
            prava_order_id=request.prava_order_id,
            transaction_reference=transaction_reference,
            merchant=merchant_outcome,
            provider_reported=True,
            final_status=final_status,
            reconciliation_required=False,
            adapter=self.descriptor,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
