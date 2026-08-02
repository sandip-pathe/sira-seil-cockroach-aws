"""Explicit development-only merchant and entitlement fixture."""

from __future__ import annotations

from integrations.common import AdapterDescriptor
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


class DevelopmentFixtureMerchantAdapter:
    """Deterministic local behavior that cannot claim production confirmation."""

    __slots__ = ("_descriptor", "_outcome")

    def __init__(self, outcome: MerchantOutcome = MerchantOutcome.APPROVED) -> None:
        self._outcome = outcome
        self._descriptor = AdapterDescriptor.development_fixture("merchant_fixture")

    @property
    def descriptor(self) -> AdapterDescriptor:
        return self._descriptor

    async def checkout_with_ephemeral_card(
        self,
        request: MerchantCheckoutRequest,
        *,
        card_token: str,
        dynamic_cvv: str,
        expiry_month: str,
        expiry_year: str,
    ) -> MerchantCheckoutOutcome:
        # Explicitly discard the ephemeral values; they never become fixture state.
        del card_token, dynamic_cvv, expiry_month, expiry_year
        order_id = (
            f"fixture_{request.prava_order_id}"
            if self._outcome is MerchantOutcome.APPROVED
            else None
        )
        return MerchantCheckoutOutcome(
            outcome=self._outcome,
            merchant_order_id=order_id,
            authorization_code=None,
            response_code=None,
            adapter=self.descriptor,
            provider_confirmed=False,
        )

    async def reconcile_order(self, request: MerchantCheckoutRequest) -> MerchantCheckoutOutcome:
        return MerchantCheckoutOutcome(
            outcome=self._outcome,
            merchant_order_id=(
                f"fixture_{request.prava_order_id}"
                if self._outcome is MerchantOutcome.APPROVED
                else None
            ),
            authorization_code=None,
            response_code=None,
            adapter=self.descriptor,
            provider_confirmed=False,
        )

    async def verify_entitlements(
        self,
        request: EntitlementVerificationRequest,
    ) -> EntitlementVerificationResult:
        return EntitlementVerificationResult(
            status=EntitlementVerificationStatus.VERIFIED,
            observed_quantity=request.minimum_quantity,
            external_entitlement_ids=(f"fixture_ent_{request.merchant_order_id}",),
            access_probe_verified=False,
            adapter=self.descriptor,
            provider_confirmed=False,
        )

    async def request_refund(self, request: MerchantRefundRequest) -> MerchantRefundResult:
        return MerchantRefundResult(
            status=RefundOutcomeStatus.PENDING,
            provider_refund_id=None,
            refunded_amount="0.00",
            currency=request.currency,
            entitlements_revoked=False,
            adapter=self.descriptor,
            provider_confirmed=False,
        )

    async def reconcile_refund(self, request: MerchantRefundRequest) -> MerchantRefundResult:
        return await self.request_refund(request)

    async def aclose(self) -> None:
        return None
