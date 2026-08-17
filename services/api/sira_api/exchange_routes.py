"""HTTP surface for the governed two-party exchange."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request, status

from .dependencies import (
    RequestContext,
    get_request_context,
    require_human_identity,
    require_idempotency_key,
    require_permission,
)
from .exchange_schemas import (
    ExchangeCaseCreate,
    ExchangeCaseCreated,
    ExchangeEvidencePublish,
    ExchangeOfferAccept,
    ExchangeOfferApprove,
    ExchangeOfferCreate,
    ExchangeProjectionView,
)
from .exchange_service import ExchangeService

exchange_router = APIRouter()
ContextDependency = Annotated[RequestContext, Depends(get_request_context)]
IdempotencyDependency = Annotated[str, Depends(require_idempotency_key)]


def get_exchange_service(request: Request) -> ExchangeService:
    return cast(ExchangeService, request.app.state.exchange_service)


ServiceDependency = Annotated[ExchangeService, Depends(get_exchange_service)]


@exchange_router.post(
    "/v1/exchange-cases",
    response_model=ExchangeCaseCreated,
    status_code=status.HTTP_201_CREATED,
    tags=["bilateral exchange"],
)
async def create_exchange_case(
    body: ExchangeCaseCreate,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
) -> dict[str, object]:
    require_human_identity(context)
    require_permission(context, "can_select_recommendation")
    return await service.create_case(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        party=context.party,
        idempotency_key=idempotency_key,
        purchase_request_id=body.purchase_request_id,
        candidate_id=body.candidate_id,
    )


@exchange_router.get(
    "/v1/exchange-cases/{case_id}",
    response_model=ExchangeProjectionView,
    tags=["bilateral exchange"],
)
async def get_exchange_case(
    case_id: str,
    context: ContextDependency,
    service: ServiceDependency,
    route_capability: Annotated[str, Query(alias="route", min_length=64, max_length=4096)],
) -> dict[str, object]:
    require_human_identity(context)
    require_permission(context, "can_view_context")
    return await service.view_case(
        organization_id=context.organization_id,
        party=context.party,
        case_id=case_id,
        route_capability=route_capability,
    )


@exchange_router.post(
    "/v1/exchange-cases/{case_id}/evidence",
    response_model=ExchangeProjectionView,
    tags=["bilateral exchange"],
)
async def publish_exchange_evidence(
    case_id: str,
    body: ExchangeEvidencePublish,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    route_capability: Annotated[str, Query(alias="route", min_length=64, max_length=4096)],
) -> dict[str, object]:
    require_human_identity(context)
    require_permission(context, "can_view_context")
    return await service.publish_evidence(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        party=context.party,
        case_id=case_id,
        route_capability=route_capability,
        idempotency_key=idempotency_key,
        expected_version=body.expected_version,
        summary=body.summary,
        published_span_ids=body.published_span_ids,
    )


@exchange_router.post(
    "/v1/exchange-cases/{case_id}/offers",
    response_model=ExchangeProjectionView,
    tags=["bilateral exchange"],
)
async def propose_exchange_offer(
    case_id: str,
    body: ExchangeOfferCreate,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    route_capability: Annotated[str, Query(alias="route", min_length=64, max_length=4096)],
) -> dict[str, object]:
    require_human_identity(context)
    require_permission(context, "can_view_context")
    return await service.propose_offer(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        party=context.party,
        case_id=case_id,
        route_capability=route_capability,
        idempotency_key=idempotency_key,
        expected_version=body.expected_version,
        currency=body.currency,
        lines=[item.model_dump(mode="python") for item in body.lines],
        total=body.total,
        rationale=body.rationale,
        changed_terms=body.changed_terms,
        expires_at=body.expires_at,
    )


@exchange_router.post(
    "/v1/exchange-cases/{case_id}/accept",
    response_model=ExchangeProjectionView,
    tags=["bilateral exchange"],
)
async def accept_exchange_offer(
    case_id: str,
    body: ExchangeOfferAccept,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    route_capability: Annotated[str, Query(alias="route", min_length=64, max_length=4096)],
) -> dict[str, object]:
    require_human_identity(context)
    require_permission(context, "can_view_context")
    return await service.accept_offer(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        party=context.party,
        case_id=case_id,
        route_capability=route_capability,
        idempotency_key=idempotency_key,
        expected_version=body.expected_version,
        offer_hash=body.offer_hash,
    )


@exchange_router.post(
    "/v1/exchange-cases/{case_id}/approve",
    response_model=ExchangeProjectionView,
    tags=["bilateral exchange"],
)
async def approve_exchange_offer(
    case_id: str,
    body: ExchangeOfferApprove,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    route_capability: Annotated[str, Query(alias="route", min_length=64, max_length=4096)],
) -> dict[str, object]:
    require_human_identity(context)
    require_permission(context, "can_approve_purchase", require_step_up=True)
    return await service.approve_offer(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        party=context.party,
        case_id=case_id,
        route_capability=route_capability,
        idempotency_key=idempotency_key,
        expected_version=body.expected_version,
        offer_hash=body.offer_hash,
        approval_expires_at=body.approval_expires_at,
    )
