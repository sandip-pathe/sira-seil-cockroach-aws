"""Typed controlled-merchant boundary."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from integrations.common import AdapterDescriptor
from integrations.merchants.models import (
    EntitlementVerificationRequest,
    EntitlementVerificationResult,
    MerchantCheckoutOutcome,
    MerchantCheckoutRequest,
)


@runtime_checkable
class ControlledMerchantAdapter(Protocol):
    """Merchant port used only by the isolated Prava checkout operation.

    Card values are keyword-only ephemeral arguments, not models.  Implementations must
    neither persist nor include them in logs, traces, exceptions, or return values.
    """

    @property
    def descriptor(self) -> AdapterDescriptor: ...

    async def checkout_with_ephemeral_card(
        self,
        request: MerchantCheckoutRequest,
        *,
        card_token: str,
        dynamic_cvv: str,
        expiry_month: str,
        expiry_year: str,
    ) -> MerchantCheckoutOutcome: ...

    async def reconcile_order(
        self, request: MerchantCheckoutRequest
    ) -> MerchantCheckoutOutcome: ...

    async def verify_entitlements(
        self,
        request: EntitlementVerificationRequest,
    ) -> EntitlementVerificationResult: ...

    async def aclose(self) -> None: ...
