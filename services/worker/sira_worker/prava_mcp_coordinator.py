"""Prava MCP activities; OAuth material exists only inside worker activities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from integrations.prava.mcp import ConnectorCipher, PravaMcpClient, PravaMcpOAuthClient
from persistence.database import Database
from persistence.models import PravaMcpConnection, PravaShoppingRun, WorkflowRun
from sira_worker.contracts import (
    PravaPaymentStatusResult,
    PravaShoppingWorkflowInput,
    PravaShoppingWorkflowResult,
)


def _status(payload: dict[str, object]) -> str:
    for key in ("status", "payment_status", "state"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value.upper()
    raise ValueError("Prava status response is incomplete")


class PersistentPravaMcpCoordinator:
    def __init__(self, *, database: Database, root_secret: str) -> None:
        self._database = database
        self._cipher = ConnectorCipher(root_secret)

    async def payment_status(
        self, request: PravaShoppingWorkflowInput
    ) -> PravaPaymentStatusResult:
        payload = await self._call(
            request.organization_id,
            "get_payment_status",
            {"session_id": request.payment_session_id},
        )
        status = _status(payload)
        await self._checkpoint(request, status=status)
        return PravaPaymentStatusResult(
            shopping_run_id=request.shopping_run_id,
            status=status,
        )

    async def checkout(
        self, request: PravaShoppingWorkflowInput
    ) -> PravaShoppingWorkflowResult:
        payload = await self._call(
            request.organization_id,
            "shop_checkout",
            {
                "checkout_session_id": request.checkout_session_id,
                "payment_session_id": request.payment_session_id,
            },
        )
        status = _status(payload)
        order_value = payload.get("order_id", payload.get("merchant_order_id"))
        order_id = order_value if isinstance(order_value, str) and order_value else None
        await self._checkpoint(request, status=status, order_id=order_id, complete=True)
        return PravaShoppingWorkflowResult(
            shopping_run_id=request.shopping_run_id,
            status=status,
            order_id=order_id,
        )

    async def fail(self, request: PravaShoppingWorkflowInput, status: str) -> None:
        await self._checkpoint(request, status=status)

    async def _call(
        self, organization_id: str, name: str, arguments: dict[str, object]
    ) -> dict[str, object]:
        token = await self._access_token(organization_id)
        client = PravaMcpClient(access_token=token)
        try:
            return await client.call_tool(name, arguments)
        finally:
            await client.aclose()

    async def _access_token(self, organization_id: str) -> str:
        async with self._database.transaction(organization_id) as session:
            connection = (
                await session.execute(
                    select(PravaMcpConnection)
                    .where(
                        PravaMcpConnection.organization_id == organization_id,
                        PravaMcpConnection.status == "CONNECTED",
                    )
                    .with_for_update()
                )
            ).scalar_one()
            sealed = self._cipher.decrypt_json(connection.encrypted_tokens)
            access = sealed.get("access_token")
            refresh = sealed.get("refresh_token")
            if not isinstance(access, str) or not isinstance(refresh, str):
                raise ValueError("Prava connection must be renewed")
            expires_at = connection.access_expires_at
            if expires_at is not None and expires_at > datetime.now(UTC) + timedelta(seconds=60):
                return access
            client_id = connection.client_id

        oauth = PravaMcpOAuthClient()
        try:
            tokens = await oauth.refresh(client_id=client_id, refresh_token=refresh)
        finally:
            await oauth.aclose()
        async with self._database.transaction(organization_id) as session:
            connection = (
                await session.execute(
                    select(PravaMcpConnection)
                    .where(PravaMcpConnection.organization_id == organization_id)
                    .with_for_update()
                )
            ).scalar_one()
            connection.encrypted_tokens = self._cipher.encrypt_json(tokens.sealed_payload())
            connection.scopes = list(tokens.scopes)
            connection.access_expires_at = tokens.expires_at
        return tokens.access_token

    async def _checkpoint(
        self,
        request: PravaShoppingWorkflowInput,
        *,
        status: str,
        order_id: str | None = None,
        complete: bool = False,
    ) -> None:
        workflow_id = f"wf_prava_shop_{request.shopping_run_id}"
        async with self._database.transaction(request.organization_id) as session:
            run = (
                await session.execute(
                    select(PravaShoppingRun)
                    .where(
                        PravaShoppingRun.organization_id == request.organization_id,
                        PravaShoppingRun.id == request.shopping_run_id,
                    )
                    .with_for_update()
                )
            ).scalar_one()
            run.status = "COMPLETED" if complete else status
            if order_id:
                run.order_id = order_id
            workflow = (
                await session.execute(
                    select(WorkflowRun)
                    .where(
                        WorkflowRun.organization_id == request.organization_id,
                        WorkflowRun.id == workflow_id,
                    )
                    .with_for_update()
                )
            ).scalar_one()
            terminal_failure = status in {
                "FAILED",
                "DECLINED",
                "CANCELLED",
                "EXPIRED",
                "APPROVAL_TIMEOUT",
            }
            if complete:
                workflow.status = "COMPLETED"
                workflow.result_reference = order_id or workflow.result_reference
            elif terminal_failure:
                workflow.status = "FAILED"
                workflow.safe_error_code = f"PRAVA_{status}"
            workflow.event_log = [
                *workflow.event_log,
                {
                    "id": str(len(workflow.event_log) + 1),
                    "status": (
                        "COMPLETED" if complete else ("FAILED" if terminal_failure else "RUNNING")
                    ),
                    "message": (
                        "Prava order placed"
                        if complete
                        else (
                            "Prava approval did not complete"
                            if terminal_failure
                            else "Waiting for Prava approval"
                        )
                    ),
                },
            ]
