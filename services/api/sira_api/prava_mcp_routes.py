"""Prava MCP connection endpoints."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from .dependencies import (
    RequestContext,
    enforce_api_security,
    get_request_context,
    require_human_identity,
    require_permission,
)
from .prava_mcp_service import PravaMcpConnectionService

router = APIRouter(dependencies=[Depends(enforce_api_security)])
ContextDependency = Annotated[RequestContext, Depends(get_request_context)]


class PravaConnectView(BaseModel):
    authorization_url: str


class PravaConnectCreate(BaseModel):
    loopback_port: int | None = Field(default=None, ge=1024, le=65535)


class PravaCallbackCreate(BaseModel):
    state: str = Field(min_length=16, max_length=256)
    code: str = Field(min_length=8, max_length=2048)


class PravaConnectionStatus(BaseModel):
    status: str


class PravaSearchCreate(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    merchant: str | None = Field(default=None, max_length=255)


class PravaQuoteCreate(BaseModel):
    product_id: str = Field(min_length=1, max_length=200)
    variant_id: str = Field(min_length=1, max_length=200)
    merchant: str = Field(min_length=3, max_length=255)
    quantity: int = Field(default=1, ge=1, le=100)
    address_id: str | None = Field(default=None, max_length=200)


class PravaCheckoutCreate(BaseModel):
    checkout_session_id: str = Field(min_length=1, max_length=200)


def _service(request: Request) -> PravaMcpConnectionService:
    return cast(PravaMcpConnectionService, request.app.state.prava_mcp_service)


@router.post("/v1/connectors/prava/connect", response_model=PravaConnectView, tags=["commerce"])
async def connect_prava(
    body: PravaConnectCreate, request: Request, context: ContextDependency
) -> dict[str, str]:
    require_human_identity(context)
    require_permission(context, "can_execute_purchase", require_step_up=True)
    return await _service(request).begin(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        loopback_port=body.loopback_port,
    )


@router.post(
    "/v1/connectors/prava/callback",
    response_model=PravaConnectionStatus,
    tags=["commerce"],
)
async def complete_prava_connection(
    body: PravaCallbackCreate, request: Request, context: ContextDependency
) -> dict[str, str]:
    require_human_identity(context)
    require_permission(context, "can_execute_purchase")
    return await _service(request).complete(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        state=body.state,
        code=body.code,
    )


@router.get(
    "/v1/connectors/prava/status",
    response_model=PravaConnectionStatus,
    tags=["commerce"],
)
async def prava_connection_status(request: Request, context: ContextDependency) -> dict[str, str]:
    require_permission(context, "can_view_context")
    return await _service(request).status(organization_id=context.organization_id)


@router.post("/v1/connectors/prava/ping", tags=["commerce"])
async def ping_prava(request: Request, context: ContextDependency) -> dict[str, object]:
    require_permission(context, "can_view_context")
    return await _service(request).ping(organization_id=context.organization_id)


@router.post("/v1/connectors/prava/search", tags=["commerce"])
async def search_prava(
    body: PravaSearchCreate, request: Request, context: ContextDependency
) -> dict[str, object]:
    require_permission(context, "can_view_context")
    arguments: dict[str, object] = {"query": body.query}
    if body.merchant:
        arguments["merchant"] = body.merchant
    return await _service(request).call_tool(
        organization_id=context.organization_id,
        name="shop_search",
        arguments=arguments,
    )


@router.post("/v1/connectors/prava/quote", tags=["commerce"])
async def quote_prava(
    body: PravaQuoteCreate, request: Request, context: ContextDependency
) -> dict[str, object]:
    require_human_identity(context)
    require_permission(context, "can_execute_purchase", require_step_up=True)
    return await _service(request).quote(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        product_id=body.product_id,
        variant_id=body.variant_id,
        merchant=body.merchant,
        quantity=body.quantity,
        address_id=body.address_id,
    )


@router.post("/v1/connectors/prava/payment-session", tags=["commerce"])
async def create_prava_payment_session(
    body: PravaCheckoutCreate, request: Request, context: ContextDependency
) -> dict[str, object]:
    require_human_identity(context)
    require_permission(context, "can_execute_purchase", require_step_up=True)
    return await _service(request).create_payment_session(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        checkout_session_id=body.checkout_session_id,
    )


@router.post("/v1/connectors/prava/checkout", tags=["commerce"])
async def queue_prava_checkout(
    body: PravaCheckoutCreate, request: Request, context: ContextDependency
) -> dict[str, str]:
    require_human_identity(context)
    require_permission(context, "can_execute_purchase", require_step_up=True)
    return await _service(request).queue_checkout(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        checkout_session_id=body.checkout_session_id,
    )


@router.get("/v1/connectors/prava/runs/{shopping_run_id}", tags=["commerce"])
async def prava_run_status(
    shopping_run_id: str, request: Request, context: ContextDependency
) -> dict[str, object]:
    require_human_identity(context)
    require_permission(context, "can_view_context")
    return await _service(request).run_status(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        shopping_run_id=shopping_run_id,
    )
