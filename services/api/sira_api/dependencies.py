"""Authenticated request context and shared route dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal, cast

from fastapi import Depends, Header, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import ApiSettings
from .errors import ApiProblem
from .identity import IdentityAdapter, IdentityKind, IdentityProviderUnavailable
from .service import DEMO_ACTOR_ID, DEMO_ORGANIZATION_ID, WorkflowService


@dataclass(frozen=True, slots=True)
class RequestContext:
    organization_id: str
    actor_id: str
    roles: frozenset[str]
    step_up_verified: bool
    identity_kind: IdentityKind
    party: Literal["BUYER", "SELLER"] | None
    fixture_identity: bool


_bearer = HTTPBearer(auto_error=False)

# Seller identities are deliberately capability-scoped.  Any new route added to the
# protected API router remains unavailable to sellers until this exact method/path
# pair is reviewed and added here.  Engagement participant membership is checked by
# the service after this coarse route boundary.
_SELLER_ROUTE_ALLOWLIST = frozenset(
    {
        ("POST", "/v1/workspace/chat"),
        ("GET", "/v1/requirement-briefs/{brief_id}"),
        ("POST", "/v1/engagements/{engagement_id}/consent"),
        ("GET", "/v1/seller/products/search"),
        ("POST", "/v1/seller/products/{product_id}/claim"),
        ("GET", "/v1/seller/products/{product_id}/view"),
        ("GET", "/v1/seller/pack-drafts/{draft_id}"),
        ("PATCH", "/v1/seller/pack-drafts/{draft_id}"),
        ("POST", "/v1/seller/pack-drafts/{draft_id}/evidence"),
        ("POST", "/v1/seller/pack-drafts/{draft_id}/submit-review"),
        ("POST", "/v1/seller/pack-drafts/{draft_id}/review-decisions"),
        ("POST", "/v1/seller/pack-drafts/{draft_id}/publish"),
        ("POST", "/v1/seller/pack-versions/{version_id}/suspend"),
        ("GET", "/v1/seller/pack-versions/{version_id}/exports"),
        ("GET", "/v1/seller/products/{product_id}/activity-metrics"),
    }
)


def get_service(request: Request) -> WorkflowService:
    return cast(WorkflowService, request.app.state.workflow_service)


async def get_request_context(
    request: Request,
    organization_header: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
    actor_id: Annotated[str | None, Header(alias="X-Actor-Id")] = None,
    actor_roles: Annotated[str | None, Header(alias="X-Actor-Roles")] = None,
    step_up_verified: Annotated[bool, Header(alias="X-Step-Up-Verified")] = False,
    identity_kind: Annotated[str | None, Header(alias="X-Identity-Kind")] = None,
    actor_party: Annotated[str | None, Header(alias="X-Actor-Party")] = None,
    bearer: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer)] = None,
) -> RequestContext:
    settings: ApiSettings = request.app.state.settings
    if not settings.is_development:
        adapter = cast(IdentityAdapter | None, request.app.state.identity_adapter)
        if adapter is None:
            raise ApiProblem(
                code="IDENTITY_ADAPTER_REQUIRED",
                message="A verified server-side identity is required in production.",
                status_code=503,
                next_action="configure_identity_adapter",
            )
        if bearer is None:
            raise ApiProblem(
                code="AUTHENTICATION_REQUIRED",
                message="A bearer credential is required.",
                status_code=401,
                next_action="authenticate",
            )
        try:
            principal = await adapter.authenticate(bearer.credentials)
        except IdentityProviderUnavailable:
            raise ApiProblem(
                code="IDENTITY_PROVIDER_UNAVAILABLE",
                message="Identity verification is temporarily unavailable.",
                status_code=503,
                retryable=True,
                next_action="retry_later",
            ) from None
        if principal is None:
            raise ApiProblem(
                code="AUTHENTICATION_FAILED",
                message="The bearer credential could not be verified.",
                status_code=401,
                next_action="authenticate",
            )
        return RequestContext(
            organization_id=principal.organization_id,
            actor_id=principal.actor_id,
            roles=frozenset(principal.roles),
            step_up_verified=bool(principal.step_up_verified),
            identity_kind=principal.identity_kind,
            party=principal.party,
            fixture_identity=False,
        )

    del bearer
    if actor_party is not None and actor_party not in {"BUYER", "SELLER"}:
        raise ApiProblem(
            code="INVALID_ACTOR_PARTY",
            message="Development actor party must be BUYER or SELLER.",
            status_code=400,
        )
    if identity_kind is not None and identity_kind not in {"HUMAN", "SERVICE"}:
        raise ApiProblem(
            code="INVALID_IDENTITY_KIND",
            message="Development identity kind must be HUMAN or SERVICE.",
            status_code=400,
        )
    roles = frozenset(
        role.strip() for role in (actor_roles or "requester").split(",") if role.strip()
    )
    verified_party = cast(Literal["BUYER", "SELLER"] | None, actor_party)
    return RequestContext(
        organization_id=organization_header or DEMO_ORGANIZATION_ID,
        actor_id=actor_id or DEMO_ACTOR_ID,
        roles=roles,
        step_up_verified=step_up_verified,
        identity_kind=cast(IdentityKind, identity_kind or "HUMAN"),
        party=verified_party,
        fixture_identity=True,
    )


def enforce_api_security(
    request: Request,
    context: Annotated[RequestContext, Depends(get_request_context)],
) -> None:
    """Apply fail-closed principal policy to every route on the protected router."""

    if context.party != "SELLER":
        return
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if (request.method, route_path) in _SELLER_ROUTE_ALLOWLIST:
        return
    raise ApiProblem(
        code="SELLER_ROUTE_FORBIDDEN",
        message="Seller identities may only access the scoped engagement consent endpoint.",
        status_code=403,
        next_action="use_authorized_buyer_identity",
    )


def require_permission(
    context: RequestContext,
    permission: str,
    *,
    require_step_up: bool = False,
) -> None:
    """Enforce one exact server-owned authority independently of UI visibility."""

    if permission not in context.roles:
        raise ApiProblem(
            code="PERMISSION_REQUIRED",
            message=f"This operation requires the {permission} permission.",
            status_code=403,
            next_action="request_authorized_identity",
            details={"required_permission": permission},
        )
    if require_step_up and not context.step_up_verified:
        raise ApiProblem(
            code="STEP_UP_REQUIRED",
            message="This operation requires recent step-up authentication.",
            status_code=403,
            next_action="complete_step_up_authentication",
            details={"required_permission": permission},
        )


def require_human_identity(context: RequestContext) -> None:
    """Deny machine identities from actions that require human accountability."""

    if context.identity_kind != "HUMAN":
        raise ApiProblem(
            code="HUMAN_IDENTITY_REQUIRED",
            message="This action requires a verified human identity.",
            status_code=403,
            next_action="authenticate_human_identity",
        )


def require_idempotency_key(
    value: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
) -> str:
    return value
