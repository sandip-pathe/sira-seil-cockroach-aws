"""Buyer-only routes for the Snowflake decision and approval proof."""

from __future__ import annotations

from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field

from .dependencies import (
    RequestContext,
    enforce_api_security,
    get_request_context,
    require_human_identity,
    require_permission,
)
from .errors import ApiProblem
from .snowflake_service import SnowflakeDecisionNotFound, SnowflakeDecisionService


class SnowflakeDecisionCreate(BaseModel):
    context_version: int = Field(default=1, ge=1, le=2)
    mission_id: str | None = Field(default=None, pattern=r"^msn_[a-f0-9]{32}$")


class SnowflakeApprovalCreate(BaseModel):
    decision_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")


router = APIRouter(
    prefix="/v1/snowflake",
    tags=["snowflake"],
    dependencies=[Depends(enforce_api_security)],
)
ContextDependency = Annotated[RequestContext, Depends(get_request_context)]


def _service(request: Request) -> SnowflakeDecisionService:
    service = cast(SnowflakeDecisionService, request.app.state.snowflake_decision_service)
    if not service.enabled:
        raise ApiProblem(
            code="SNOWFLAKE_NOT_CONFIGURED",
            message="The governed Snowflake decision plane is not configured.",
            status_code=503,
            next_action="configure_snowflake",
        )
    return service


ServiceDependency = Annotated[SnowflakeDecisionService, Depends(_service)]


@router.post("/decisions", response_model=dict[str, Any])
async def create_snowflake_decision(
    body: SnowflakeDecisionCreate,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
) -> dict[str, Any]:
    require_permission(context, "can_view_context")
    return await service.create_decision(
        organization_id=context.organization_id,
        context_version=body.context_version,
        mission_id=body.mission_id,
        actor_id=context.actor_id,
        idempotency_key=idempotency_key,
    )


@router.get("/decisions/{request_id}", response_model=dict[str, Any])
async def get_snowflake_decision(
    request_id: str,
    context: ContextDependency,
    service: ServiceDependency,
) -> dict[str, Any]:
    require_permission(context, "can_view_context")
    result = await service.get_decision(request_id, organization_id=context.organization_id)
    if result is None:
        raise ApiProblem(
            code="SNOWFLAKE_DECISION_NOT_FOUND",
            message="Decision not found.",
            status_code=404,
        )
    return result


@router.post("/approvals", response_model=dict[str, Any])
async def approve_snowflake_decision(
    body: SnowflakeApprovalCreate,
    context: ContextDependency,
    service: ServiceDependency,
) -> dict[str, Any]:
    require_human_identity(context)
    require_permission(context, "can_approve_purchase")
    try:
        return await service.approve(
            organization_id=context.organization_id,
            decision_hash=body.decision_hash,
            actor_id=context.actor_id,
            actor_role="BUYER_APPROVER",
        )
    except SnowflakeDecisionNotFound as error:
        raise ApiProblem(
            code="SNOWFLAKE_DECISION_NOT_FOUND",
            message="Decision not found.",
            status_code=404,
        ) from error


__all__ = ["router"]
