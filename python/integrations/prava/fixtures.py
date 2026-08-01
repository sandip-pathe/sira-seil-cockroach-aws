"""Explicit, non-production Prava fixture adapter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from integrations.common import AdapterDescriptor
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


class DevelopmentFixturePravaAdapter:
    """Local deterministic flow clearly labelled as non-production."""

    __slots__ = ("_descriptor", "_merchant_descriptor", "_outcome")

    def __init__(self, outcome: MerchantOutcome = MerchantOutcome.APPROVED) -> None:
        self._outcome = outcome
        self._descriptor = AdapterDescriptor.development_fixture("prava_fixture")
        self._merchant_descriptor = AdapterDescriptor.development_fixture("merchant_fixture")

    @property
    def descriptor(self) -> AdapterDescriptor:
        return self._descriptor

    async def create_session(self, request: PravaSessionRequest) -> PravaHostedSession:
        del request
        return PravaHostedSession(
            session_id="fixture_session",
            hosted_url="https://fixture.invalid/prava/fixture_session",
            order_id="fixture_order",
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            adapter=self.descriptor,
        )

    async def execute_isolated_checkout(
        self,
        *,
        session_id: str,
        request: MerchantCheckoutRequest,
        merchant: ControlledMerchantAdapter,
    ) -> PravaCheckoutResult:
        del merchant
        merchant_outcome = MerchantCheckoutOutcome(
            outcome=self._outcome,
            merchant_order_id=(
                f"fixture_{request.prava_order_id}"
                if self._outcome is MerchantOutcome.APPROVED
                else None
            ),
            authorization_code=None,
            response_code=None,
            adapter=self._merchant_descriptor,
            provider_confirmed=False,
        )
        final_status = (
            PravaPaymentStatus.COMPLETED
            if self._outcome is MerchantOutcome.APPROVED
            else PravaPaymentStatus.FAILED
        )
        return PravaCheckoutResult(
            session_id=session_id,
            prava_order_id=request.prava_order_id,
            transaction_reference="fixture_transaction",
            merchant=merchant_outcome,
            provider_reported=False,
            final_status=final_status,
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
            provider_confirmed=False,
            adapter=self.descriptor,
        )

    async def aclose(self) -> None:
        return None
