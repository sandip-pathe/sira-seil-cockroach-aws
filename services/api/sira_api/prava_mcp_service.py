"""Organization-scoped Prava MCP OAuth lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import urlsplit

from sqlalchemy import select

from integrations.prava.mcp import (
    ConnectorCipher,
    PkceAuthorization,
    PravaMcpClient,
    PravaMcpOAuthClient,
)
from persistence.database import Database
from persistence.models import (
    OutboxEvent,
    PravaMcpAuthorization,
    PravaMcpConnection,
    PravaShoppingRun,
    WorkflowRun,
)
from persistence.repositories import new_id

from .callback_state import BrowserReturnStateSigner
from .errors import ApiProblem


class PravaMcpConnectionService:
    def __init__(
        self,
        database: Database,
        *,
        root_secret: str,
        public_base_url: str,
        web_base_url: str,
    ) -> None:
        self.database = database
        self.cipher = ConnectorCipher(root_secret)
        self.signer = BrowserReturnStateSigner(root_secret)
        self.redirect_uri = f"{web_base_url.rstrip('/')}/prava/connect/return"
        del public_base_url

    async def begin(self, *, organization_id: str, actor_id: str) -> dict[str, str]:
        pkce = PkceAuthorization.create()
        oauth = PravaMcpOAuthClient()
        try:
            client_id = await oauth.register(redirect_uri=self.redirect_uri)
        finally:
            await oauth.aclose()
        state = self.signer.issue()
        async with self.database.transaction(organization_id) as session:
            session.add(
                PravaMcpAuthorization(
                    id=new_id("pma"),
                    organization_id=organization_id,
                    actor_id=actor_id,
                    state_hash=self.signer.digest(state),
                    client_id=client_id,
                    encrypted_code_verifier=self.cipher.encrypt_json(
                        {"verifier": pkce.verifier}
                    ),
                    redirect_uri=self.redirect_uri,
                    expires_at=datetime.now(UTC) + timedelta(minutes=10),
                    consumed_at=None,
                )
            )
        authorization_url = oauth.authorization_url(
            client_id=client_id,
            redirect_uri=self.redirect_uri,
            pkce=PkceAuthorization(
                state=state,
                verifier=pkce.verifier,
                challenge=pkce.challenge,
            ),
        )
        return {"authorization_url": authorization_url}

    async def complete(
        self,
        *,
        organization_id: str,
        actor_id: str,
        state: str,
        code: str,
    ) -> dict[str, str]:
        if not self.signer.verify(state):
            raise ApiProblem(
                code="PRAVA_OAUTH_STATE_INVALID",
                message="The Prava connection state is invalid.",
                status_code=400,
                next_action="restart_prava_connection",
            )
        async with self.database.transaction(organization_id) as session:
            authorization = (
                await session.execute(
                    select(PravaMcpAuthorization)
                    .where(
                        PravaMcpAuthorization.organization_id == organization_id,
                        PravaMcpAuthorization.state_hash == self.signer.digest(state),
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            now = datetime.now(UTC)
            if (
                authorization is None
                or authorization.actor_id != actor_id
                or authorization.consumed_at is not None
                or authorization.expires_at <= now
            ):
                raise ApiProblem(
                    code="PRAVA_OAUTH_STATE_INVALID",
                    message="The Prava connection state is expired or already used.",
                    status_code=409,
                    next_action="restart_prava_connection",
                )
            verifier = self.cipher.decrypt_json(
                authorization.encrypted_code_verifier
            ).get("verifier")
            if not isinstance(verifier, str) or not verifier:
                raise ApiProblem(
                    code="PRAVA_OAUTH_STATE_INVALID",
                    message="The Prava connection verifier is unavailable.",
                    status_code=409,
                    next_action="restart_prava_connection",
                )
            client_id = authorization.client_id
            redirect_uri = authorization.redirect_uri

        oauth = PravaMcpOAuthClient()
        try:
            tokens = await oauth.exchange(
                client_id=client_id,
                redirect_uri=redirect_uri,
                code=code,
                verifier=verifier,
            )
        finally:
            await oauth.aclose()

        async with self.database.transaction(organization_id) as session:
            authorization = (
                await session.execute(
                    select(PravaMcpAuthorization)
                    .where(
                        PravaMcpAuthorization.organization_id == organization_id,
                        PravaMcpAuthorization.state_hash == self.signer.digest(state),
                    )
                    .with_for_update()
                )
            ).scalar_one()
            if authorization.consumed_at is not None:
                raise ApiProblem(
                    code="PRAVA_OAUTH_STATE_REPLAYED",
                    message="The Prava connection response was already consumed.",
                    status_code=409,
                )
            authorization.consumed_at = datetime.now(UTC)
            connection = (
                await session.execute(
                    select(PravaMcpConnection)
                    .where(PravaMcpConnection.organization_id == organization_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            sealed = self.cipher.encrypt_json(tokens.sealed_payload())
            if connection is None:
                session.add(
                    PravaMcpConnection(
                        id=new_id("pmc"),
                        organization_id=organization_id,
                        actor_id=actor_id,
                        client_id=client_id,
                        encrypted_tokens=sealed,
                        scopes=list(tokens.scopes),
                        status="CONNECTED",
                        access_expires_at=tokens.expires_at,
                        revoked_at=None,
                    )
                )
            else:
                connection.actor_id = actor_id
                connection.client_id = client_id
                connection.encrypted_tokens = sealed
                connection.scopes = list(tokens.scopes)
                connection.status = "CONNECTED"
                connection.access_expires_at = tokens.expires_at
                connection.revoked_at = None
        return {"status": "connected"}

    async def status(self, *, organization_id: str) -> dict[str, str]:
        async with self.database.transaction(organization_id) as session:
            connection = (
                await session.execute(
                    select(PravaMcpConnection).where(
                        PravaMcpConnection.organization_id == organization_id
                    )
                )
            ).scalar_one_or_none()
            status = connection.status.lower() if connection is not None else "not_connected"
            return {"status": status}

    async def ping(self, *, organization_id: str) -> dict[str, object]:
        return await self.call_tool(organization_id=organization_id, name="ping", arguments={})

    async def call_tool(
        self, *, organization_id: str, name: str, arguments: dict[str, object]
    ) -> dict[str, object]:
        access_token = await self._access_token(organization_id)
        client = PravaMcpClient(access_token=access_token)
        try:
            return await client.call_tool(name, arguments)
        finally:
            await client.aclose()

    async def quote(
        self,
        *,
        organization_id: str,
        actor_id: str,
        product_id: str,
        variant_id: str,
        merchant: str,
        quantity: int,
        address_id: str | None,
    ) -> dict[str, object]:
        arguments: dict[str, object] = {
            "variant_id": variant_id,
            "merchant": merchant,
            "quantity": quantity,
        }
        if address_id:
            arguments["address_id"] = address_id
        result = await self.call_tool(
            organization_id=organization_id,
            name="shop_quote",
            arguments=arguments,
        )
        checkout_id = result.get("checkout_session_id")
        amount_value = result.get("total", result.get("amount"))
        currency = result.get("currency")
        if (
            not isinstance(checkout_id, str)
            or not isinstance(amount_value, (str, int, float))
            or isinstance(amount_value, bool)
            or not isinstance(currency, str)
            or len(currency) != 3
        ):
            raise ApiProblem(
                code="PRAVA_QUOTE_INVALID",
                message="Prava did not return a complete binding quote.",
                status_code=502,
                next_action="quote_again",
            )
        async with self.database.transaction(organization_id) as session:
            existing = (
                await session.execute(
                    select(PravaShoppingRun).where(
                        PravaShoppingRun.organization_id == organization_id,
                        PravaShoppingRun.checkout_session_id == checkout_id,
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                session.add(
                    PravaShoppingRun(
                        id=new_id("psr"),
                        organization_id=organization_id,
                        actor_id=actor_id,
                        purchase_intent_id=None,
                        product_id=product_id,
                        variant_id=variant_id,
                        merchant=merchant,
                        quantity=quantity,
                        checkout_session_id=checkout_id,
                        payment_session_id=None,
                        payment_url=None,
                        amount=Decimal(str(amount_value)),
                        currency=currency.upper(),
                        quote_payload=result,
                        status="QUOTED",
                        order_id=None,
                        safe_error_code=None,
                    )
                )
        return result

    async def create_payment_session(
        self, *, organization_id: str, actor_id: str, checkout_session_id: str
    ) -> dict[str, object]:
        async with self.database.transaction(organization_id) as session:
            run = (
                await session.execute(
                    select(PravaShoppingRun).where(
                        PravaShoppingRun.organization_id == organization_id,
                        PravaShoppingRun.checkout_session_id == checkout_session_id,
                    )
                )
            ).scalar_one_or_none()
            if run is None or run.actor_id != actor_id:
                raise ApiProblem(
                    code="PRAVA_QUOTE_NOT_FOUND",
                    message="The Prava quote is unavailable for this identity.",
                    status_code=404,
                )
            if run.payment_session_id and run.payment_url:
                return {
                    "session_id": run.payment_session_id,
                    "payment_url": run.payment_url,
                    "replayed": True,
                }
            amount = f"{run.amount:.2f}"
            currency = run.currency
            merchant = run.merchant
            product_description = str(
                run.quote_payload.get("product_name", run.product_id)
            )
            quantity = run.quantity
            merchant_url = self._merchant_url(merchant)
            unit_price = f"{(run.amount / Decimal(quantity)):.2f}"
        result = await self.call_tool(
            organization_id=organization_id,
            name="create_payment_session",
            arguments={
                "total_amount": amount,
                "currency": currency,
                "merchant_name": merchant,
                "merchant_url": merchant_url,
                "merchant_country": "US",
                "products": [
                    {
                        "description": product_description,
                        "unit_price": unit_price,
                        "quantity": quantity,
                    }
                ],
                "idempotency_key": f"sira-{checkout_session_id}",
            },
        )
        session_id = result.get("session_id")
        payment_url = result.get("payment_url")
        if not isinstance(session_id, str) or not isinstance(payment_url, str):
            raise ApiProblem(
                code="PRAVA_PAYMENT_SESSION_INVALID",
                message="Prava did not return a secure approval session.",
                status_code=502,
            )
        async with self.database.transaction(organization_id) as session:
            run = (
                await session.execute(
                    select(PravaShoppingRun)
                    .where(
                        PravaShoppingRun.organization_id == organization_id,
                        PravaShoppingRun.checkout_session_id == checkout_session_id,
                    )
                    .with_for_update()
                )
            ).scalar_one()
            run.payment_session_id = session_id
            run.payment_url = payment_url
            run.status = "AWAITING_APPROVAL"
        return result

    async def queue_checkout(
        self, *, organization_id: str, actor_id: str, checkout_session_id: str
    ) -> dict[str, str]:
        async with self.database.transaction(organization_id) as session:
            run = (
                await session.execute(
                    select(PravaShoppingRun)
                    .where(
                        PravaShoppingRun.organization_id == organization_id,
                        PravaShoppingRun.checkout_session_id == checkout_session_id,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if (
                run is None
                or run.actor_id != actor_id
                or not run.payment_session_id
                or run.status not in {"AWAITING_APPROVAL", "QUEUED"}
            ):
                raise ApiProblem(
                    code="PRAVA_CHECKOUT_NOT_READY",
                    message="The Prava quote is not ready for checkout.",
                    status_code=409,
                    next_action="complete_prava_approval",
                )
            workflow_id = f"wf_prava_shop_{run.id}"
            workflow = (
                await session.execute(
                    select(WorkflowRun).where(
                        WorkflowRun.organization_id == organization_id,
                        WorkflowRun.id == workflow_id,
                    )
                )
            ).scalar_one_or_none()
            if workflow is None:
                session.add(
                    WorkflowRun(
                        id=workflow_id,
                        organization_id=organization_id,
                        aggregate_type="prava_shopping_run",
                        aggregate_id=run.id,
                        operation="prava_shop_checkout",
                        status="PENDING",
                        result_reference=f"/v1/connectors/prava/runs/{run.id}",
                        safe_error_code=None,
                        event_log=[
                            {
                                "id": "1",
                                "status": "PENDING",
                                "message": "Prava checkout queued",
                            }
                        ],
                    )
                )
                session.add(
                    OutboxEvent(
                        id=new_id("evt"),
                        organization_id=organization_id,
                        aggregate_type="prava_shopping_run",
                        aggregate_id=run.id,
                        event_type="prava_mcp_checkout.requested",
                        event_key=f"prava-mcp-checkout:{run.id}",
                        payload={
                            "workflow_id": workflow_id,
                            "shopping_run_id": run.id,
                            "checkout_session_id": run.checkout_session_id,
                            "payment_session_id": run.payment_session_id,
                        },
                    )
                )
            run.status = "QUEUED"
        return {
            "workflow_id": workflow_id,
            "shopping_run_id": run.id,
            "status": "queued",
        }

    async def run_status(
        self, *, organization_id: str, actor_id: str, shopping_run_id: str
    ) -> dict[str, object]:
        async with self.database.transaction(organization_id) as session:
            run = (
                await session.execute(
                    select(PravaShoppingRun).where(
                        PravaShoppingRun.organization_id == organization_id,
                        PravaShoppingRun.id == shopping_run_id,
                    )
                )
            ).scalar_one_or_none()
            if run is None or run.actor_id != actor_id:
                raise ApiProblem(
                    code="PRAVA_RUN_NOT_FOUND",
                    message="That Prava shopping run is unavailable.",
                    status_code=404,
                )
            return {
                "id": run.id,
                "status": run.status,
                "order_id": run.order_id,
                "safe_error_code": run.safe_error_code,
            }

    @staticmethod
    def _merchant_url(merchant: str) -> str:
        candidate = merchant if "://" in merchant else f"https://{merchant}"
        parsed = urlsplit(candidate)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise ApiProblem(
                code="PRAVA_MERCHANT_INVALID",
                message="Prava returned an invalid merchant identity.",
                status_code=502,
            )
        return f"https://{parsed.hostname}"

    async def _access_token(self, organization_id: str) -> str:
        async with self.database.transaction(organization_id) as session:
            connection = (
                await session.execute(
                    select(PravaMcpConnection)
                    .where(
                        PravaMcpConnection.organization_id == organization_id,
                        PravaMcpConnection.status == "CONNECTED",
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if connection is None:
                raise ApiProblem(
                    code="PRAVA_MCP_NOT_CONNECTED",
                    message="Connect Prava before using payment or shopping tools.",
                    status_code=409,
                    next_action="connect_prava",
                )
            payload = self.cipher.decrypt_json(connection.encrypted_tokens)
            access_token = payload.get("access_token")
            refresh_token = payload.get("refresh_token")
            if not isinstance(access_token, str) or not isinstance(refresh_token, str):
                raise ApiProblem(
                    code="PRAVA_MCP_RECONNECT_REQUIRED",
                    message="The Prava connection must be renewed.",
                    status_code=409,
                    next_action="reconnect_prava",
                )
            expires_at = connection.access_expires_at
            if expires_at is None or expires_at > datetime.now(UTC) + timedelta(seconds=60):
                return access_token
            client_id = connection.client_id

        oauth = PravaMcpOAuthClient()
        try:
            tokens = await oauth.refresh(client_id=client_id, refresh_token=refresh_token)
        finally:
            await oauth.aclose()
        async with self.database.transaction(organization_id) as session:
            connection = (
                await session.execute(
                    select(PravaMcpConnection)
                    .where(PravaMcpConnection.organization_id == organization_id)
                    .with_for_update()
                )
            ).scalar_one()
            connection.encrypted_tokens = self.cipher.encrypt_json(tokens.sealed_payload())
            connection.scopes = list(tokens.scopes)
            connection.access_expires_at = tokens.expires_at
            connection.status = "CONNECTED"
        return tokens.access_token
