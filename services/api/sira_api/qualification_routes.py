"""Authenticated API routes for qualification missions and introductions."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status

from .dependencies import (
    RequestContext,
    enforce_api_security,
    get_request_context,
    require_human_identity,
    require_idempotency_key,
    require_permission,
)
from .errors import ApiProblem
from .qualification_schemas import (
    CompanyContextCreate,
    CompanyContextList,
    CompanyContextUpdate,
    CompanyContextView,
    QualificationApprovalCreate,
    QualificationConsentCreate,
    QualificationEngagementView,
    QualificationEventFeed,
    QualificationIntegrityView,
    QualificationIntroductionCreate,
    QualificationMissionCreate,
    QualificationMissionView,
    QualificationMutationView,
    QualificationSellerResponseCreate,
)
from .qualification_service import QualificationService

qualification_router = APIRouter(dependencies=[Depends(enforce_api_security)])
ContextDependency = Annotated[RequestContext, Depends(get_request_context)]
IdempotencyDependency = Annotated[str, Depends(require_idempotency_key)]
IfMatchDependency = Annotated[str, Header(alias="If-Match", min_length=10, max_length=100)]


def get_qualification_service(request: Request) -> QualificationService:
    return cast(QualificationService, request.app.state.qualification_service)


ServiceDependency = Annotated[QualificationService, Depends(get_qualification_service)]


def _require_buyer(context: RequestContext) -> None:
    if context.party == "SELLER":
        raise ApiProblem(
            code="BUYER_IDENTITY_REQUIRED",
            message="This operation requires a verified buyer identity.",
            status_code=403,
            next_action="use_authorized_buyer_identity",
        )


@qualification_router.get(
    "/v1/qualification/company-context",
    response_model=CompanyContextList,
    tags=["company context"],
    name="qualification_list_company_context",
)
async def list_company_context(
    context: ContextDependency,
    service: ServiceDependency,
    include_retired: bool = False,
) -> dict[str, object]:
    _require_buyer(context)
    require_permission(context, "can_view_context")
    return await service.list_company_context(
        context.organization_id, include_retired=include_retired
    )


@qualification_router.get(
    "/v1/qualification/company-context/{item_id}",
    response_model=CompanyContextView,
    tags=["company context"],
    name="qualification_get_company_context",
)
async def get_company_context(
    item_id: str,
    response: Response,
    context: ContextDependency,
    service: ServiceDependency,
) -> dict[str, object]:
    _require_buyer(context)
    require_permission(context, "can_view_context")
    payload = await service.company_context_view(context.organization_id, item_id)
    item = payload["item"]
    if isinstance(item, dict) and isinstance(item.get("current_hash"), str):
        response.headers["ETag"] = f'"{item["current_hash"]}"'
    return payload


@qualification_router.post(
    "/v1/qualification/company-context",
    response_model=QualificationMutationView,
    status_code=status.HTTP_201_CREATED,
    tags=["company context"],
    name="qualification_create_company_context",
)
async def create_company_context(
    body: CompanyContextCreate,
    response: Response,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
) -> dict[str, object]:
    _require_buyer(context)
    require_human_identity(context)
    require_permission(context, "can_manage_procurement_gate")
    code, payload = await service.create_company_context(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="json"),
    )
    response.status_code = code
    response.headers["Location"] = f"/v1/qualification/company-context/{payload['resource_id']}"
    return payload


@qualification_router.put(
    "/v1/qualification/company-context/{item_id}",
    response_model=QualificationMutationView,
    tags=["company context"],
    name="qualification_update_company_context",
)
async def update_company_context(
    item_id: str,
    body: CompanyContextUpdate,
    response: Response,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    if_match: IfMatchDependency,
) -> dict[str, object]:
    _require_buyer(context)
    require_human_identity(context)
    require_permission(context, "can_manage_procurement_gate")
    code, payload = await service.update_company_context(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        item_id=item_id,
        if_match=if_match,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="json"),
    )
    response.status_code = code
    return payload


@qualification_router.post(
    "/v1/qualification/company-context/{item_id}/retire",
    response_model=QualificationMutationView,
    tags=["company context"],
    name="qualification_retire_company_context",
)
async def retire_company_context(
    item_id: str,
    response: Response,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    if_match: IfMatchDependency,
) -> dict[str, object]:
    _require_buyer(context)
    require_human_identity(context)
    require_permission(context, "can_manage_procurement_gate")
    code, payload = await service.retire_company_context(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        item_id=item_id,
        if_match=if_match,
        idempotency_key=idempotency_key,
    )
    response.status_code = code
    return payload


@qualification_router.post(
    "/v1/qualification/missions",
    response_model=QualificationMutationView,
    status_code=status.HTTP_201_CREATED,
    tags=["qualification marketplace"],
    name="qualification_create_mission",
)
async def create_qualification_mission(
    body: QualificationMissionCreate,
    response: Response,
    request: Request,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
) -> dict[str, object]:
    _require_buyer(context)
    require_human_identity(context)
    require_permission(context, "can_submit_request")
    code, payload = await service.create_mission(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        idempotency_key=idempotency_key,
        trace_id=request.state.request_id,
        body=body.model_dump(mode="json"),
    )
    response.status_code = code
    response.headers["Location"] = f"/v1/qualification/missions/{payload['resource_id']}"
    return payload


@qualification_router.get(
    "/v1/qualification/missions/{mission_id}",
    response_model=QualificationMissionView,
    tags=["qualification marketplace"],
    name="qualification_get_mission",
)
async def get_qualification_mission(
    mission_id: str,
    response: Response,
    context: ContextDependency,
    service: ServiceDependency,
) -> dict[str, object]:
    _require_buyer(context)
    require_permission(context, "can_view_context")
    payload = await service.mission_view(context.organization_id, mission_id)
    decision = payload.get("decision")
    if isinstance(decision, dict) and isinstance(decision.get("decision_digest"), str):
        response.headers["ETag"] = f'"{decision["decision_digest"]}"'
    return payload


@qualification_router.get(
    "/v1/qualification/missions/{mission_id}/events",
    response_model=QualificationEventFeed,
    tags=["qualification marketplace"],
    name="qualification_get_mission_events",
)
async def get_qualification_mission_events(
    mission_id: str,
    context: ContextDependency,
    service: ServiceDependency,
    after: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, object]:
    _require_buyer(context)
    require_permission(context, "can_view_context")
    return await service.mission_events(
        context.organization_id, mission_id, after=after, limit=limit
    )


@qualification_router.post(
    "/v1/qualification/decisions/{decision_id}/approval",
    response_model=QualificationMutationView,
    tags=["qualification marketplace"],
    name="qualification_decide_approval",
)
async def decide_qualification_approval(
    decision_id: str,
    body: QualificationApprovalCreate,
    response: Response,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    if_match: IfMatchDependency,
) -> dict[str, object]:
    _require_buyer(context)
    require_human_identity(context)
    require_permission(context, "can_approve_purchase", require_step_up=True)
    code, payload = await service.decide_approval(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        decision_id=decision_id,
        if_match=if_match,
        idempotency_key=idempotency_key,
        action=body.action,
        reason=body.reason,
    )
    response.status_code = code
    return payload


@qualification_router.get(
    "/v1/qualification/engagements/{engagement_id}",
    response_model=QualificationEngagementView,
    tags=["qualification marketplace"],
    name="qualification_get_engagement",
)
async def get_qualification_engagement(
    engagement_id: str,
    response: Response,
    context: ContextDependency,
    service: ServiceDependency,
) -> dict[str, object]:
    payload = await service.engagement_view(context.organization_id, engagement_id)
    engagement = payload["engagement"]
    if isinstance(engagement, dict) and isinstance(engagement.get("input_digest"), str):
        response.headers["ETag"] = f'"{engagement["input_digest"]}"'
    return payload


@qualification_router.post(
    "/v1/qualification/engagements/{engagement_id}/responses",
    response_model=QualificationMutationView,
    status_code=status.HTTP_201_CREATED,
    tags=["qualification marketplace"],
    name="qualification_record_seller_response",
)
async def record_qualification_seller_response(
    engagement_id: str,
    body: QualificationSellerResponseCreate,
    response: Response,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    if_match: IfMatchDependency,
) -> dict[str, object]:
    require_human_identity(context)
    if context.party != "SELLER":
        raise ApiProblem(
            code="SELLER_IDENTITY_REQUIRED",
            message="Only the selected seller may respond to this opportunity.",
            status_code=403,
            next_action="use_authorized_seller_identity",
        )
    code, payload = await service.respond(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        engagement_id=engagement_id,
        if_match=if_match,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="json"),
    )
    response.status_code = code
    return payload


@qualification_router.post(
    "/v1/qualification/engagements/{engagement_id}/consents",
    response_model=QualificationMutationView,
    status_code=status.HTTP_201_CREATED,
    tags=["qualification marketplace"],
    name="qualification_record_consent",
)
async def record_qualification_consent(
    engagement_id: str,
    body: QualificationConsentCreate,
    response: Response,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    if_match: IfMatchDependency,
) -> dict[str, object]:
    require_human_identity(context)
    if context.party not in {"BUYER", "SELLER"}:
        raise ApiProblem(
            code="VERIFIED_PARTY_REQUIRED",
            message="Consent requires a verified buyer or seller identity.",
            status_code=403,
            next_action="authenticate_party_identity",
        )
    code, payload = await service.consent(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        party=context.party,
        engagement_id=engagement_id,
        if_match=if_match,
        idempotency_key=idempotency_key,
        shared_fields=body.shared_fields,
    )
    response.status_code = code
    return payload


@qualification_router.post(
    "/v1/qualification/engagements/{engagement_id}/introduction",
    response_model=QualificationMutationView,
    status_code=status.HTTP_201_CREATED,
    tags=["qualification marketplace"],
    name="qualification_create_introduction",
)
async def create_qualification_introduction(
    engagement_id: str,
    body: QualificationIntroductionCreate,
    response: Response,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    if_match: IfMatchDependency,
) -> dict[str, object]:
    _require_buyer(context)
    require_human_identity(context)
    require_permission(context, "can_approve_purchase", require_step_up=True)
    code, payload = await service.introduce(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        engagement_id=engagement_id,
        if_match=if_match,
        idempotency_key=idempotency_key,
        shared_fields=body.shared_fields,
    )
    response.status_code = code
    return payload


@qualification_router.get(
    "/v1/qualification/missions/{mission_id}/integrity",
    response_model=QualificationIntegrityView,
    tags=["qualification marketplace"],
    name="qualification_get_integrity",
)
async def get_qualification_integrity(
    mission_id: str,
    context: ContextDependency,
    service: ServiceDependency,
) -> dict[str, object]:
    _require_buyer(context)
    require_permission(context, "can_view_context")
    return await service.integrity(context.organization_id, mission_id)
