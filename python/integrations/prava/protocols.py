"""Typed Prava hosted-checkout port."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from integrations.common import AdapterDescriptor
from integrations.merchants.models import MerchantCheckoutOutcome, MerchantCheckoutRequest
from integrations.merchants.protocols import ControlledMerchantAdapter
from integrations.prava.models import (
    PravaCheckoutResult,
    PravaHostedSession,
    PravaReportResult,
    PravaSessionRequest,
)


@runtime_checkable
class PravaHostedCheckoutProvider(Protocol):
    @property
    def descriptor(self) -> AdapterDescriptor: ...

    async def create_session(self, request: PravaSessionRequest) -> PravaHostedSession: ...

    async def execute_isolated_checkout(
        self,
        *,
        session_id: str,
        request: MerchantCheckoutRequest,
        merchant: ControlledMerchantAdapter,
    ) -> PravaCheckoutResult: ...

    async def report_known_outcome(
        self,
        *,
        session_id: str,
        transaction_reference: str,
        outcome: MerchantCheckoutOutcome,
    ) -> PravaReportResult: ...

    async def aclose(self) -> None: ...
