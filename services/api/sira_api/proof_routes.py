"""Buyer-only routes for the DataHub-causal proof workspace."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, status

from .dependencies import (
    RequestContext,
    enforce_api_security,
    get_request_context,
    require_permission,
)
from .proof_runtime import ProofWorkspaceRuntime
from .proof_schemas import ProofRunnerView, ProofWorkspaceView

router = APIRouter(
    prefix="/v1/proof",
    tags=["proof"],
    dependencies=[Depends(enforce_api_security)],
)
ContextDependency = Annotated[RequestContext, Depends(get_request_context)]


def get_proof_runtime(request: Request) -> ProofWorkspaceRuntime:
    return cast(ProofWorkspaceRuntime, request.app.state.proof_runtime)


RuntimeDependency = Annotated[ProofWorkspaceRuntime, Depends(get_proof_runtime)]


@router.get("/workspace", response_model=ProofWorkspaceView)
async def get_proof_workspace(
    context: ContextDependency, runtime: RuntimeDependency
) -> ProofWorkspaceView:
    require_permission(context, "can_view_context")
    return runtime.workspace()


@router.get("/runs/current", response_model=ProofRunnerView)
async def get_proof_run(
    context: ContextDependency, runtime: RuntimeDependency
) -> dict[str, str | None]:
    require_permission(context, "can_view_context")
    return runtime.runner()


@router.post("/runs", response_model=ProofRunnerView, status_code=status.HTTP_202_ACCEPTED)
async def start_proof_run(
    context: ContextDependency, runtime: RuntimeDependency
) -> dict[str, str | None]:
    require_permission(context, "can_manage_procurement_gate")
    return await runtime.start()
