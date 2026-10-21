"""Routes for the single-screen commerce workspace."""

from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Query, Request
from sira_agents.runtime import AgentRunContext

from .dependencies import (
    RequestContext,
    enforce_api_security,
    get_request_context,
    require_permission,
)
from .errors import ApiProblem
from .workspace_schemas import (
    CapabilityView,
    CatalogProductView,
    ConnectorView,
    MissionSnapshotView,
    ProductResearchCreate,
    WorkspaceChatCreate,
    WorkspaceChatView,
    WorkspaceConversationView,
)
from .workspace_service import WorkspaceService

workspace_router = APIRouter(dependencies=[Depends(enforce_api_security)])
ContextDependency = Annotated[RequestContext, Depends(get_request_context)]


def get_workspace_service(request: Request) -> WorkspaceService:
    return cast(WorkspaceService, request.app.state.workspace_service)


ServiceDependency = Annotated[WorkspaceService, Depends(get_workspace_service)]


def _agent_context(
    request: Request, context: RequestContext, service: WorkspaceService
) -> AgentRunContext:
    return AgentRunContext(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        actor_roles=context.roles,
        permissions=context.roles,
        party=context.party,
        step_up_verified=context.step_up_verified,
        request_id=request.state.request_id,
        services=service.agent_services(),
    )


@workspace_router.get("/v1/capabilities", response_model=list[CapabilityView], tags=["workspace"])
async def workspace_capabilities(
    context: ContextDependency, service: ServiceDependency
) -> list[dict[str, str | None]]:
    require_permission(context, "can_view_context")
    return service.capabilities()


@workspace_router.post("/v1/workspace/chat", response_model=WorkspaceChatView, tags=["workspace"])
async def workspace_chat(
    body: WorkspaceChatCreate,
    request: Request,
    context: ContextDependency,
    service: ServiceDependency,
) -> dict[str, object]:
    if body.mode == "seil" and context.party != "SELLER":
        raise ApiProblem(
            code="SEIL_IDENTITY_REQUIRED",
            message="SEIL requires an authenticated seller identity.",
            status_code=403,
            next_action="use_authorized_seller_identity",
        )
    if body.mode == "sira" and context.party == "SELLER":
        raise ApiProblem(
            code="SIRA_IDENTITY_REQUIRED",
            message="SIRA requires an authenticated buyer identity.",
            status_code=403,
            next_action="use_authorized_buyer_identity",
        )
    if body.mode == "sira":
        require_permission(context, "can_view_context")
    return await service.chat(
        body,
        run_context=_agent_context(request, context, service),
    )


@workspace_router.get(
    "/v1/workspace/conversations",
    response_model=list[WorkspaceConversationView],
    tags=["workspace"],
)
async def workspace_conversations(
    mode: Literal["sira", "seil"],
    request: Request,
    context: ContextDependency,
    service: ServiceDependency,
) -> list[dict[str, object]]:
    if mode == "seil" and context.party != "SELLER":
        raise ApiProblem(
            code="SEIL_IDENTITY_REQUIRED",
            message="SEIL requires an authenticated seller identity.",
            status_code=403,
        )
    if mode == "sira":
        require_permission(context, "can_view_context")
    return await service.conversations(
        run_context=_agent_context(request, context, service),
        mode=mode,
    )


@workspace_router.get(
    "/v1/workspace/missions/{mission_id}",
    response_model=MissionSnapshotView,
    tags=["workspace"],
)
async def workspace_mission(
    mission_id: str,
    request: Request,
    context: ContextDependency,
    service: ServiceDependency,
) -> dict[str, object]:
    require_permission(context, "can_view_context")
    return await service.mission(
        run_context=_agent_context(request, context, service),
        mission_id=mission_id,
    )


@workspace_router.get(
    "/v1/workspace/catalog", response_model=list[CatalogProductView], tags=["workspace"]
)
async def workspace_catalog(
    request: Request,
    context: ContextDependency,
    query: Annotated[str, Query(max_length=1000)] = "",
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[dict[str, object]]:
    require_permission(context, "can_view_context")
    result = await request.app.state.product_marketplace.search(
        context.organization_id, query=query, limit=limit
    )
    return cast(list[dict[str, object]], result["results"])


@workspace_router.get(
    "/v1/workspace/catalog/{product_id}", response_model=CatalogProductView, tags=["workspace"]
)
async def workspace_product(
    product_id: str,
    request: Request,
    context: ContextDependency,
) -> dict[str, object]:
    require_permission(context, "can_view_context")
    return cast(
        dict[str, object],
        await request.app.state.product_marketplace.product(context.organization_id, product_id),
    )


@workspace_router.post(
    "/v1/marketplace/research", tags=["workspace"], name="marketplace_research_products"
)
async def research_marketplace_products(
    body: ProductResearchCreate,
    request: Request,
    context: ContextDependency,
) -> dict[str, object]:
    require_permission(context, "can_view_context")
    return cast(
        dict[str, object],
        await request.app.state.product_marketplace.discover(
            context.organization_id, query=body.query, limit=body.limit, refresh=body.refresh
        ),
    )


@workspace_router.get(
    "/v1/workspace/connectors", response_model=list[ConnectorView], tags=["workspace"]
)
async def workspace_connectors(
    context: ContextDependency, service: ServiceDependency
) -> list[dict[str, str]]:
    require_permission(context, "can_view_context")
    return [
        {
            "id": "business-context",
            "name": "Business Context",
            "purpose": "Company rules, goals, and buying preferences",
            "status": "Needs setup",
            "meta": "Add company documents or confirm details in chat",
        },
        {
            "id": "google-workspace",
            "name": "Google Workspace",
            "purpose": "Inventory and team context",
            "status": "Not connected",
            "meta": "Optional read-only connection",
        },
    ]
