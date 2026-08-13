"""Versioned HTTP surface for the first integrated product vertical."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import StreamingResponse

from .config import ApiSettings
from .dependencies import (
    RequestContext,
    enforce_api_security,
    get_request_context,
    get_service,
    require_human_identity,
    require_idempotency_key,
    require_permission,
)
from .errors import ApiProblem
from .schemas import (
    ApprovalCreate,
    ApprovalRejectCreate,
    ApprovalRequestCreate,
    ApprovalRequestView,
    ApprovalRevokeCreate,
    CalibrationRunCreate,
    CalibrationRunView,
    CandidateActionCreate,
    CandidateActionView,
    ConsentCreate,
    CounterfactualView,
    DecisionLedgerView,
    DecisionSimulationCreate,
    DecisionSimulationView,
    EngagementView,
    EvaluationReplayView,
    HealthResponse,
    OutcomeCheckpointCreate,
    OutcomeCheckpointView,
    PravaBrowserReturnCreate,
    PravaSessionCreate,
    PravaSessionView,
    ProposalDecisionCreate,
    ProposalDecisionView,
    PurchaseBriefView,
    PurchaseIntentCreate,
    PurchaseIntentView,
    PurchaseRequestCreate,
    PurchaseRequestView,
    PurchaseStatusView,
    ReceiptView,
    RequirementBriefView,
    ReversalCreate,
    ReversalView,
    StackfileView,
    WorkflowAccepted,
    WorkflowView,
)
from .schemas_v2 import DecisionView as CurrentDecisionView
from .service import WorkflowService

public_router = APIRouter()
router = APIRouter(dependencies=[Depends(enforce_api_security)])
ContextDependency = Annotated[RequestContext, Depends(get_request_context)]
ServiceDependency = Annotated[WorkflowService, Depends(get_service)]
IdempotencyDependency = Annotated[str, Depends(require_idempotency_key)]


@public_router.get(
    "/health",
    response_model=HealthResponse,
    tags=["runtime"],
)
async def health(request: Request) -> HealthResponse:
    """Process liveness only; dependency failures must not trigger restart loops."""

    settings: ApiSettings = request.app.state.settings
    return HealthResponse(
        status="ok",
        version="0.1.0",
        database="not_checked",
        fixture_mode=settings.development_fixture_mode,
    )


@public_router.get(
    "/ready",
    response_model=HealthResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": HealthResponse,
            "description": "Required CockroachDB readiness checks failed",
        }
    },
    tags=["runtime"],
)
async def ready(request: Request, response: Response, service: ServiceDependency) -> HealthResponse:
    settings: ApiSettings = request.app.state.settings
    database = await service.health()
    if database != "configured":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if database == "configured" else "degraded",
        version="0.1.0",
        database=database,
        fixture_mode=settings.development_fixture_mode,
    )


@router.post("/v1/demo/reset", tags=["development"])
async def reset_demo(
    request: Request, context: ContextDependency, service: ServiceDependency
) -> dict[str, object]:
    settings: ApiSettings = request.app.state.settings
    if (
        not settings.is_development
        or not settings.demo_reset_enabled
        or not settings.development_fixture_mode
    ):
        raise ApiProblem(
            code="DEMO_RESET_DISABLED",
            message="The deterministic reset endpoint is disabled outside development and test.",
            status_code=404,
        )
    return await service.reset_demo(context.organization_id)


@router.post(
    "/v1/purchase-requests",
    response_model=PurchaseRequestView,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
    tags=["purchase requests"],
)
async def create_purchase_request(
    body: PurchaseRequestCreate,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    response: Response,
) -> dict[str, object]:
    require_permission(context, "can_submit_request")
    response_status, payload = await service.create_purchase_request(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="json"),
    )
    response.status_code = response_status
    return payload


@router.get(
    "/v1/purchase-requests/{request_id}",
    response_model=PurchaseRequestView,
    include_in_schema=False,
    tags=["purchase requests"],
)
async def get_purchase_request(
    request_id: str, context: ContextDependency, service: ServiceDependency
) -> dict[str, object]:
    require_permission(context, "can_view_context")
    return await service.get_purchase_request(context.organization_id, request_id)


@router.post(
    "/v1/purchase-requests/{request_id}/discover",
    response_model=WorkflowAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    include_in_schema=False,
    tags=["decisions"],
)
async def discover(
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


@router.get(
    "/v1/purchase-requests/{request_id}/decision-view",
    response_model=CurrentDecisionView,
    include_in_schema=False,
    tags=["decisions"],
)
async def get_decision_view(
    request_id: str, context: ContextDependency, service: ServiceDependency
) -> dict[str, object]:
    require_permission(context, "can_view_context")
    return await service.decision_view(context.organization_id, request_id)


@router.get(
    "/v1/purchase-requests/{request_id}/purchase-brief",
    response_model=PurchaseBriefView,
    include_in_schema=False,
    tags=["purchase requests"],
)
async def get_purchase_brief(
    request_id: str, context: ContextDependency, service: ServiceDependency
) -> dict[str, object]:
    require_permission(context, "can_view_context")
    return await service.get_purchase_brief(context.organization_id, request_id)


@router.get(
    "/v1/requirement-briefs/{brief_id}",
    response_model=RequirementBriefView,
    tags=["seller engagement"],
)
async def get_requirement_brief(
    brief_id: str, context: ContextDependency, service: ServiceDependency
) -> dict[str, object]:
    # The service returns an explicit seller allowlist regardless of caller role.
    require_permission(context, "can_view_context")
    return await service.get_requirement_brief(
        context.organization_id,
        brief_id,
        actor_id=context.actor_id,
        actor_party=context.party,
    )


@router.post(
    "/v1/purchase-requests/{request_id}/calibration-runs",
    response_model=CalibrationRunView,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
    tags=["decisions"],
)
async def run_calibration(
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


@router.post(
    "/v1/purchase-requests/{request_id}/candidates/{candidate_id}/actions",
    response_model=CandidateActionView,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
    tags=["seller engagement"],
)
async def candidate_action(
    request_id: str,
    candidate_id: str,
    body: CandidateActionCreate,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    response: Response,
) -> dict[str, object]:
    require_permission(context, "can_select_recommendation")
    response_status, payload = await service.candidate_action(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        actor_party=context.party,
        request_id=request_id,
        candidate_id=candidate_id,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="json"),
    )
    response.status_code = response_status
    return payload


@router.post(
    "/v1/engagements/{engagement_id}/consent",
    response_model=EngagementView,
    tags=["seller engagement"],
)
async def record_consent(
    engagement_id: str,
    body: ConsentCreate,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    response: Response,
) -> dict[str, object]:
    response_status, payload = await service.record_consent(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        actor_party=context.party,
        engagement_id=engagement_id,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="json"),
    )
    response.status_code = response_status
    return payload


@router.get(
    "/v1/decisions/{decision_id}",
    response_model=DecisionLedgerView,
    tags=["decisions"],
    include_in_schema=False,
)
async def get_decision(
    decision_id: str, context: ContextDependency, service: ServiceDependency
) -> dict[str, object]:
    require_permission(context, "can_view_context")
    return await service.get_decision(context.organization_id, decision_id)


@router.get(
    "/v1/decisions/{decision_id}/counterfactuals",
    response_model=CounterfactualView,
    tags=["decisions"],
)
async def get_counterfactuals(
    decision_id: str, context: ContextDependency, service: ServiceDependency
) -> dict[str, object]:
    require_permission(context, "can_view_context")
    return await service.counterfactuals(context.organization_id, decision_id)


@router.post(
    "/v1/decisions/{decision_id}/simulations",
    response_model=DecisionSimulationView,
    status_code=status.HTTP_201_CREATED,
    tags=["decisions"],
)
async def simulate_decision(
    decision_id: str,
    body: DecisionSimulationCreate,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    response: Response,
) -> dict[str, object]:
    require_permission(context, "can_view_context")
    response_status, payload = await service.simulate_decision(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        decision_id=decision_id,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="json"),
    )
    response.status_code = response_status
    return payload


@router.post(
    "/v1/evaluation-runs/{evaluation_run_id}/replay",
    response_model=EvaluationReplayView,
    tags=["decisions"],
)
async def replay_evaluation(
    evaluation_run_id: str,
    context: ContextDependency,
    service: ServiceDependency,
) -> dict[str, object]:
    require_permission(context, "can_view_context")
    return await service.replay_evaluation(context.organization_id, evaluation_run_id)


@router.post(
    "/v1/purchase-briefs/{brief_id}/proposals/{proposal_id}/accept",
    response_model=ProposalDecisionView,
    include_in_schema=False,
    tags=["decisions"],
)
async def accept_proposal(
    brief_id: str,
    proposal_id: str,
    body: ProposalDecisionCreate,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    response: Response,
) -> dict[str, object]:
    require_permission(context, "can_select_recommendation")
    response_status, payload = await service.decide_proposal(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        actor_roles=context.roles,
        step_up_verified=context.step_up_verified,
        brief_id=brief_id,
        proposal_id=proposal_id,
        accept=True,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="json"),
    )
    response.status_code = response_status
    return payload


@router.post(
    "/v1/purchase-briefs/{brief_id}/proposals/{proposal_id}/reject",
    response_model=ProposalDecisionView,
    include_in_schema=False,
    tags=["decisions"],
)
async def reject_proposal(
    brief_id: str,
    proposal_id: str,
    body: ProposalDecisionCreate,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    response: Response,
) -> dict[str, object]:
    require_permission(context, "can_select_recommendation")
    response_status, payload = await service.decide_proposal(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        actor_roles=context.roles,
        step_up_verified=context.step_up_verified,
        brief_id=brief_id,
        proposal_id=proposal_id,
        accept=False,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="json"),
    )
    response.status_code = response_status
    return payload


@router.post(
    "/v1/decisions/{decision_id}/purchase-intents",
    response_model=PurchaseIntentView,
    status_code=status.HTTP_201_CREATED,
    tags=["commerce"],
)
async def lock_purchase_intent(
    decision_id: str,
    body: PurchaseIntentCreate,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    response: Response,
) -> dict[str, object]:
    require_permission(context, "can_select_recommendation")
    response_status, payload = await service.lock_purchase_intent(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        decision_id=decision_id,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="json"),
    )
    response.status_code = response_status
    return payload


@router.post(
    "/v1/purchase-intents/{intent_id}/approval-requests",
    response_model=ApprovalRequestView,
    status_code=status.HTTP_201_CREATED,
    tags=["commerce"],
)
async def create_approval_request(
    intent_id: str,
    body: ApprovalRequestCreate,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    response: Response,
) -> dict[str, object]:
    require_permission(context, "can_manage_procurement_gate")
    response_status, payload = await service.create_approval_request(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        intent_id=intent_id,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="json"),
    )
    response.status_code = response_status
    return payload


@router.post(
    "/v1/approval-requests/{approval_id}/approve",
    response_model=ApprovalRequestView,
    tags=["commerce"],
)
async def approve(
    approval_id: str,
    body: ApprovalCreate,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    response: Response,
) -> dict[str, object]:
    require_human_identity(context)
    require_permission(context, "can_approve_purchase")
    response_status, payload = await service.approve(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        actor_roles=context.roles,
        step_up_verified=context.step_up_verified,
        approval_id=approval_id,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="json"),
    )
    response.status_code = response_status
    return payload


@router.post(
    "/v1/approval-requests/{approval_id}/reject",
    response_model=ApprovalRequestView,
    tags=["commerce"],
)
async def reject_approval(
    approval_id: str,
    body: ApprovalRejectCreate,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    response: Response,
) -> dict[str, object]:
    require_human_identity(context)
    require_permission(context, "can_approve_purchase")
    response_status, payload = await service.reject_approval(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        actor_roles=context.roles,
        step_up_verified=context.step_up_verified,
        approval_id=approval_id,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="json"),
    )
    response.status_code = response_status
    return payload


@router.post(
    "/v1/approval-requests/{approval_id}/revoke",
    response_model=ApprovalRequestView,
    tags=["commerce"],
)
async def revoke_approval(
    approval_id: str,
    body: ApprovalRevokeCreate,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    response: Response,
) -> dict[str, object]:
    require_human_identity(context)
    require_permission(context, "can_approve_purchase")
    response_status, payload = await service.revoke_approval(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        actor_roles=context.roles,
        step_up_verified=context.step_up_verified,
        approval_id=approval_id,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="json"),
    )
    response.status_code = response_status
    return payload


@router.post(
    "/v1/purchase-intents/{intent_id}/prava-sessions",
    response_model=PravaSessionView,
    status_code=status.HTTP_201_CREATED,
    tags=["commerce"],
)
async def create_prava_session(
    intent_id: str,
    body: PravaSessionCreate,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    response: Response,
) -> dict[str, object]:
    require_human_identity(context)
    require_permission(context, "can_execute_purchase", require_step_up=True)
    response_status, payload = await service.create_prava_session(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        intent_id=intent_id,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="json"),
    )
    response.status_code = response_status
    return payload


@router.post(
    "/v1/prava/browser-return",
    response_model=WorkflowAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["commerce"],
    include_in_schema=False,
)
async def accept_prava_browser_return(
    body: PravaBrowserReturnCreate,
    context: ContextDependency,
    service: ServiceDependency,
) -> dict[str, object]:
    require_human_identity(context)
    require_permission(context, "can_execute_purchase")
    return await service.accept_prava_browser_return(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        body=body.model_dump(mode="json"),
    )


@router.get(
    "/v1/purchase-intents/{intent_id}/status",
    response_model=PurchaseStatusView,
    tags=["commerce"],
)
async def purchase_status(
    intent_id: str, context: ContextDependency, service: ServiceDependency
) -> dict[str, object]:
    require_permission(context, "can_view_context")
    return await service.purchase_status(context.organization_id, intent_id)


@router.post(
    "/v1/purchase-intents/{intent_id}/reversals",
    response_model=ReversalView,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["commerce"],
)
async def request_purchase_reversal(
    intent_id: str,
    body: ReversalCreate,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    response: Response,
) -> dict[str, object]:
    require_human_identity(context)
    require_permission(context, "can_execute_purchase", require_step_up=True)
    response_status, payload = await service.request_reversal(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        intent_id=intent_id,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="json"),
    )
    response.status_code = response_status
    return payload


@router.post(
    "/v1/purchase-intents/{intent_id}/outcome-checkpoints",
    response_model=OutcomeCheckpointView,
    status_code=status.HTTP_201_CREATED,
    tags=["commerce"],
)
async def record_purchase_outcome(
    intent_id: str,
    body: OutcomeCheckpointCreate,
    context: ContextDependency,
    service: ServiceDependency,
    idempotency_key: IdempotencyDependency,
    response: Response,
) -> dict[str, object]:
    require_human_identity(context)
    require_permission(context, "can_select_recommendation")
    response_status, payload = await service.record_outcome_checkpoint(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        intent_id=intent_id,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="json"),
    )
    response.status_code = response_status
    return payload


@router.get("/v1/purchases/{purchase_id}/receipt", response_model=ReceiptView, tags=["commerce"])
async def get_receipt(
    purchase_id: str, context: ContextDependency, service: ServiceDependency
) -> dict[str, object]:
    require_permission(context, "can_view_context")
    return await service.get_receipt(context.organization_id, purchase_id)


@router.get(
    "/v1/organizations/{organization_id}/stackfile",
    response_model=StackfileView,
    tags=["stackfile"],
)
async def get_stackfile(
    organization_id: str, context: ContextDependency, service: ServiceDependency
) -> dict[str, object]:
    require_permission(context, "can_view_context")
    if organization_id != context.organization_id:
        raise ApiProblem(
            code="TENANT_SCOPE_MISMATCH",
            message="The authenticated tenant cannot access this Stackfile.",
            status_code=403,
        )
    return await service.stackfile(context.organization_id)


@router.get("/v1/workflows/{workflow_id}", response_model=WorkflowView, tags=["workflows"])
async def get_workflow(
    workflow_id: str, context: ContextDependency, service: ServiceDependency
) -> dict[str, object]:
    require_permission(context, "can_view_context")
    return await service.workflow(context.organization_id, workflow_id)


@router.get(
    "/v1/workflows/{workflow_id}/events",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Workflow status events",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        }
    },
    tags=["workflows"],
)
async def get_workflow_events(
    workflow_id: str, context: ContextDependency, service: ServiceDependency
) -> StreamingResponse:
    require_permission(context, "can_view_context")
    events = await service.workflow_events(context.organization_id, workflow_id)

    async def event_stream() -> AsyncIterator[str]:
        for event in events:
            event_id = event.get("id", "0")
            yield f"id: {event_id}\nevent: workflow\ndata: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
