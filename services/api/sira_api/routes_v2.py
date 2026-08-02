"""Current procurement-native API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from .dependencies import (
    RequestContext,
    enforce_api_security,
    get_request_context,
    get_service,
    require_human_identity,
    require_idempotency_key,
    require_permission,
)
from .schemas import (
    CalibrationRunCreate,
    CalibrationRunView,
    PravaBrowserReturnCreate,
    ProposalDecisionCreate,
    ProposalDecisionView,
    WorkflowAccepted,
)
from .schemas_v2 import (
    ActionRunCreate,
    ActionRunView,
    DecisionIndexView,
    DecisionLedgerV2,
    DecisionRequestCreate,
    DecisionRequestView,
    DecisionRulesView,
    DecisionView,
    OptionFeedbackCreate,
    OptionFeedbackView,
    PlanSelectionCreate,
    PlanSelectionView,
)
from .service import WorkflowService
from .surface_v2 import DecisionRoomSurface

router_v2 = APIRouter(dependencies=[Depends(enforce_api_security)])
ContextDependency = Annotated[RequestContext, Depends(get_request_context)]
ServiceDependency = Annotated[WorkflowService, Depends(get_service)]
IdempotencyDependency = Annotated[str, Depends(require_idempotency_key)]


@router_v2.get(
    "/v1/decision-requests",
    response_model=DecisionIndexView,
    tags=["decision requests"],
)
async def list_decision_requests(
    context: ContextDependency, service: ServiceDependency
) -> dict[str, object]:
    require_permission(context, "can_view_context")
    return await DecisionRoomSurface(service).list_requests(
        organization_id=context.organization_id,
        roles=context.roles,
        party=context.party,
    )


@router_v2.post(
    "/v1/decision-requests",
    response_model=DecisionRequestView,
    status_code=status.HTTP_201_CREATED,
    tags=["decision requests"],
)
async def create_decision_request(
    body: DecisionRequestCreate,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    response: Response,
) -> dict[str, object]:
    require_permission(context, "can_submit_request")
    response_status, payload = await DecisionRoomSurface(service).create_request(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        roles=context.roles,
        party=context.party,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="json"),
    )
    response.status_code = response_status
    return payload


@router_v2.get(
    "/v1/decision-requests/{request_id}",
    response_model=DecisionRequestView,
    tags=["decision requests"],
)
async def get_decision_request(
    request_id: str, context: ContextDependency, service: ServiceDependency
) -> dict[str, object]:
    require_permission(context, "can_view_context")
    return await DecisionRoomSurface(service).get_request(
        organization_id=context.organization_id,
        request_id=request_id,
        roles=context.roles,
        party=context.party,
    )


@router_v2.post(
    "/v1/decision-requests/{request_id}/discover",
    response_model=WorkflowAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["decisions"],
)
async def discover_decision_request(
    request_id: str,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
) -> dict[str, object]:
    require_permission(context, "can_view_context")
    return await service.discover(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        request_id=request_id,
        idempotency_key=idempotency_key,
    )


@router_v2.get(
    "/v1/decision-requests/{request_id}/decision-view",
    response_model=DecisionView,
    tags=["decisions"],
)
async def get_decision_room(
    request_id: str, context: ContextDependency, service: ServiceDependency
) -> dict[str, object]:
    require_permission(context, "can_view_context")
    return await DecisionRoomSurface(service).decision_view(
        organization_id=context.organization_id,
        request_id=request_id,
        roles=context.roles,
        party=context.party,
    )


@router_v2.get(
    "/v1/decision-requests/{request_id}/decision-rules",
    response_model=DecisionRulesView,
    tags=["decisions"],
)
async def get_decision_rules(
    request_id: str, context: ContextDependency, service: ServiceDependency
) -> dict[str, object]:
    require_permission(context, "can_view_context")
    return await DecisionRoomSurface(service).decision_rules(
        organization_id=context.organization_id,
        request_id=request_id,
    )


@router_v2.post(
    "/v1/decision-requests/{request_id}/calibration-runs",
    response_model=CalibrationRunView,
    status_code=status.HTTP_201_CREATED,
    tags=["decisions"],
)
async def run_decision_calibration(
    request_id: str,
    body: CalibrationRunCreate,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    response: Response,
) -> dict[str, object]:
    require_permission(context, "can_select_recommendation")
    response_status, payload = await service.run_calibration(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        request_id=request_id,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="json"),
    )
    response.status_code = response_status
    return payload


@router_v2.post(
    "/v1/decision-requests/{request_id}/solution-options/{solution_plan_id}/actions",
    response_model=OptionFeedbackView,
    status_code=status.HTTP_201_CREATED,
    tags=["decisions"],
)
async def record_solution_option_feedback(
    request_id: str,
    solution_plan_id: str,
    body: OptionFeedbackCreate,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    response: Response,
) -> dict[str, object]:
    require_permission(context, "can_select_recommendation")
    response_status, payload = await DecisionRoomSurface(service).feedback(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        actor_party=context.party,
        request_id=request_id,
        solution_plan_id=solution_plan_id,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="json"),
    )
    response.status_code = response_status
    return payload


@router_v2.post(
    "/v1/decision-rules/{rules_id}/proposals/{proposal_id}/accept",
    response_model=ProposalDecisionView,
    tags=["decisions"],
)
async def accept_rule_proposal(
    rules_id: str,
    proposal_id: str,
    body: ProposalDecisionCreate,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    response: Response,
) -> dict[str, object]:
    require_human_identity(context)
    require_permission(context, "can_select_recommendation")
    response_status, payload = await service.decide_proposal(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        actor_roles=context.roles,
        step_up_verified=context.step_up_verified,
        brief_id=rules_id,
        proposal_id=proposal_id,
        accept=True,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="json"),
    )
    response.status_code = response_status
    return payload


@router_v2.post(
    "/v1/decision-rules/{rules_id}/proposals/{proposal_id}/reject",
    response_model=ProposalDecisionView,
    tags=["decisions"],
)
async def reject_rule_proposal(
    rules_id: str,
    proposal_id: str,
    body: ProposalDecisionCreate,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    response: Response,
) -> dict[str, object]:
    require_human_identity(context)
    require_permission(context, "can_select_recommendation")
    response_status, payload = await service.decide_proposal(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        actor_roles=context.roles,
        step_up_verified=context.step_up_verified,
        brief_id=rules_id,
        proposal_id=proposal_id,
        accept=False,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="json"),
    )
    response.status_code = response_status
    return payload


@router_v2.get(
    "/v1/decisions/{decision_id}",
    response_model=DecisionLedgerV2,
    tags=["decisions"],
)
async def get_decision_ledger_v2(
    decision_id: str, context: ContextDependency, service: ServiceDependency
) -> dict[str, object]:
    require_permission(context, "can_view_context")
    return await service.get_decision(context.organization_id, decision_id)


@router_v2.post(
    "/v1/decisions/{decision_id}/plan-selections",
    response_model=PlanSelectionView,
    status_code=status.HTTP_201_CREATED,
    tags=["decisions"],
)
async def select_action_plan(
    decision_id: str,
    body: PlanSelectionCreate,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    response: Response,
) -> dict[str, object]:
    require_human_identity(context)
    require_permission(context, "can_select_recommendation", require_step_up=True)
    response_status, payload = await DecisionRoomSurface(service).select_plan(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        roles=context.roles,
        party=context.party,
        decision_id=decision_id,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="json"),
    )
    response.status_code = response_status
    return payload


@router_v2.post(
    "/v1/decisions/{decision_id}/action-runs",
    response_model=ActionRunView,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["execution"],
)
async def start_action_run(
    decision_id: str,
    body: ActionRunCreate,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    response: Response,
) -> dict[str, object]:
    require_human_identity(context)
    require_permission(context, "can_select_recommendation")
    response_status, payload = await DecisionRoomSurface(service).start_action_run(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        roles=context.roles,
        party=context.party,
        decision_id=decision_id,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="json"),
    )
    response.status_code = response_status
    return payload


@router_v2.get(
    "/v1/action-runs/{action_run_id}",
    response_model=ActionRunView,
    tags=["execution"],
)
async def get_action_run(
    action_run_id: str, context: ContextDependency, service: ServiceDependency
) -> dict[str, object]:
    require_permission(context, "can_view_context")
    return await DecisionRoomSurface(service).get_action_run(
        organization_id=context.organization_id,
        action_run_id=action_run_id,
    )


@router_v2.get(
    "/v1/prava/browser-return",
    response_model=WorkflowAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["commerce"],
)
async def accept_prava_browser_return_v2(
    context: ContextDependency,
    service: ServiceDependency,
    state_value: Annotated[
        str,
        Query(alias="state", min_length=16, max_length=256, pattern=r"^[A-Za-z0-9._~-]+$"),
    ],
    return_url: Annotated[str, Query(min_length=8, max_length=2048)],
) -> dict[str, object]:
    require_human_identity(context)
    require_permission(context, "can_execute_purchase")
    body = PravaBrowserReturnCreate(state=state_value, return_url=return_url)
    return await service.accept_prava_browser_return(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        body=body.model_dump(mode="json"),
    )
