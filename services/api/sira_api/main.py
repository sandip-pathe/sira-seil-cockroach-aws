"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from typing import cast
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sira_agents.bedrock_runtime import (
    BedrockConverseRuntime,
    BedrockGuardrail,
    TitanEmbeddingClient,
    bedrock_tools_from_function_tools,
    create_bedrock_client,
)
from sira_agents.commerce_tools import commerce_tool_registry
from sira_agents.workspace_tools import workspace_tool_registry
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import Response

from integrations.aws_services import (
    ContentAddressedEvidenceStore,
    S3Client,
    create_aws_client,
)
from persistence.database import Database, DatabaseSettings
from persistence.repositories import PersistenceConflict

from .config import ApiSettings, get_settings
from .errors import ApiProblem
from .fixtures import DemoFixtureBundle
from .guest_security import FixedWindowLimiter, GuestSessionSigner, RateLimitDecision
from .identity import FirebaseIdentityAdapter, IdentityAdapter, IntrospectionIdentityAdapter
from .marketplace import (
    SellerOrganizationDirectory,
    SellerPrincipalBinding,
    StaticSellerOrganizationDirectory,
)
from .qualification_routes import qualification_router
from .qualification_service import QualificationService
from .routes import public_router, router
from .routes_v2 import router_v2
from .schemas import ErrorEnvelope
from .seller_routes import seller_router
from .seller_service import SellerEvidenceService
from .service import WorkflowService, translate_persistence_conflict
from .workspace_routes import workspace_router
from .workspace_service import WorkspaceService

logger = logging.getLogger(__name__)


def operation_id(route: APIRoute) -> str:
    """Keep generated-client names stable when paths are refactored."""

    return route.name


def _origin(value: str) -> str | None:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _rate_limited_response(request: Request, decision: RateLimitDecision) -> JSONResponse:
    retry_after = max(1, int(decision.reset_at - datetime.now().timestamp()))
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMITED",
                "message": "This guest workspace has reached its request limit. Try again shortly.",
                "request_id": request.state.request_id,
                "retryable": True,
                "next_action": "retry_after_cooldown",
                "details": {"retry_after_seconds": retry_after},
            }
        },
        headers={
            "Retry-After": str(retry_after),
            "RateLimit-Limit": str(decision.limit),
            "RateLimit-Remaining": str(decision.remaining),
            "RateLimit-Reset": str(decision.reset_at),
        },
    )


def create_app(
    *,
    settings: ApiSettings | None = None,
    database: Database | None = None,
    catalog_database: Database | None = None,
    identity_adapter: IdentityAdapter | None = None,
    seller_directory: SellerOrganizationDirectory | None = None,
    evidence_store: ContentAddressedEvidenceStore | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_settings.assert_safe_runtime()
    resolved_database = database or Database(
        DatabaseSettings(database_url=resolved_settings.database_url)
    )
    catalog_url = resolved_settings.catalog_database_url.get_secret_value().strip()
    resolved_catalog_database = catalog_database or (
        Database(DatabaseSettings(database_url=catalog_url)) if catalog_url else None
    )
    if (
        not resolved_settings.is_development
        and resolved_database.engine.dialect.name != "cockroachdb"
    ):
        raise ValueError("production requires a CockroachDB database engine with RLS support")
    if (
        not resolved_settings.is_development
        and resolved_catalog_database is not None
        and resolved_catalog_database.engine.dialect.name != "cockroachdb"
    ):
        raise ValueError("production requires a CockroachDB catalog engine with RLS support")
    resolved_identity_adapter = identity_adapter
    if resolved_identity_adapter is None and resolved_settings.firebase_project_id:
        resolved_identity_adapter = FirebaseIdentityAdapter(
            project_id=resolved_settings.firebase_project_id,
            step_up_max_age_seconds=resolved_settings.identity_step_up_max_age_seconds,
        )
    if (
        not resolved_settings.is_development
        and not resolved_settings.guest_session_enabled
        and resolved_identity_adapter is None
    ):
        resolved_settings.assert_identity_configuration()
        resolved_identity_adapter = IntrospectionIdentityAdapter(
            introspection_url=resolved_settings.identity_introspection_url,
            client_id=resolved_settings.identity_client_id,
            client_secret=resolved_settings.identity_client_secret.get_secret_value(),
            expected_issuer=resolved_settings.identity_expected_issuer,
            expected_audience=resolved_settings.identity_expected_audience,
            allowed_roles=resolved_settings.identity_roles(),
            step_up_acr_values=resolved_settings.identity_step_up_values(),
            step_up_max_age_seconds=resolved_settings.identity_step_up_max_age_seconds,
        )
    guest_signer = (
        GuestSessionSigner(
            resolved_settings.guest_session_signing_secret(),
            ttl_seconds=resolved_settings.guest_session_ttl_seconds,
        )
        if resolved_settings.guest_session_enabled
        else None
    )
    abuse_limiter = FixedWindowLimiter()
    guest_cookie_name = "sira_guest" if resolved_settings.is_development else "__Host-sira_guest"

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.settings = resolved_settings
        application.state.database = resolved_database
        application.state.identity_adapter = resolved_identity_adapter
        application.state.guest_signer = guest_signer
        application.state.guest_cookie_name = guest_cookie_name
        fixtures = DemoFixtureBundle.load() if resolved_settings.development_fixture_mode else None
        fixture_quote_clock: Callable[[], datetime] | None = None
        if fixtures is not None:
            fixture_quote_now = datetime.fromisoformat(
                str(fixtures.expected_purchase_intent["locked_at"]).replace("Z", "+00:00")
            )

            def fixed_fixture_quote_clock() -> datetime:
                return fixture_quote_now

            fixture_quote_clock = fixed_fixture_quote_clock
        resolved_seller_directory = seller_directory
        if resolved_seller_directory is None and fixtures is not None:
            resolved_seller_directory = StaticSellerOrganizationDirectory(
                tuple(
                    SellerPrincipalBinding(
                        candidate_id=candidate_id,
                        seller_actor_id=str(pack["seller_id"]),
                        seller_organization_id=f"org_{pack['seller_id']}",
                    )
                    for candidate_id, pack in sorted(fixtures.packs.items())
                )
            )
        workflow_service = WorkflowService(
            resolved_database,
            fixtures,
            allow_development_tenant_bootstrap=(
                resolved_settings.is_development or resolved_settings.guest_session_enabled
            ),
            seller_directory=resolved_seller_directory,
            quote_clock=fixture_quote_clock,
        )
        resolved_evidence_store = evidence_store
        if resolved_evidence_store is None and resolved_settings.s3_evidence_bucket.strip():
            resolved_evidence_store = ContentAddressedEvidenceStore(
                client=cast(
                    S3Client,
                    create_aws_client(
                        "s3",
                        region=resolved_settings.aws_region,
                        profile=resolved_settings.aws_profile.strip() or None,
                    ),
                ),
                bucket=resolved_settings.s3_evidence_bucket.strip(),
                kms_key_id=resolved_settings.s3_evidence_kms_key_id.strip() or None,
            )
        seller_evidence_service = SellerEvidenceService(
            resolved_database,
            development_fixture_mode=resolved_settings.development_fixture_mode,
            evidence_store=resolved_evidence_store,
        )
        bedrock_client = (
            create_bedrock_client(
                region=resolved_settings.aws_region,
                profile=resolved_settings.aws_profile.strip() or None,
            )
            if resolved_settings.agent_runtime_provider == "bedrock"
            or resolved_catalog_database is not None
            else None
        )
        workspace_runtime = None
        if resolved_settings.agent_runtime_provider == "bedrock":
            if bedrock_client is None:
                raise RuntimeError("Bedrock runtime client was not initialized")
            guardrail_id = resolved_settings.bedrock_guardrail_id.strip()
            workspace_runtime = BedrockConverseRuntime(
                client=bedrock_client,
                model_id=resolved_settings.bedrock_chat_model_id,
                tools=bedrock_tools_from_function_tools(
                    {**workspace_tool_registry(), **commerce_tool_registry()}
                ),
                guardrail=(
                    BedrockGuardrail(
                        identifier=guardrail_id,
                        version=resolved_settings.bedrock_guardrail_version,
                    )
                    if guardrail_id
                    else None
                ),
            )
        application.state.workflow_service = workflow_service
        application.state.seller_evidence_service = seller_evidence_service
        application.state.qualification_service = QualificationService(
            resolved_database,
            catalog_database=resolved_catalog_database,
            embedding_client=(
                TitanEmbeddingClient(
                    client=bedrock_client,
                    model_id=resolved_settings.bedrock_embedding_model_id,
                )
                if resolved_catalog_database is not None and bedrock_client is not None
                else None
            ),
            allow_development_tenant_bootstrap=(
                resolved_settings.is_development or resolved_settings.guest_session_enabled
            ),
        )
        application.state.workspace_service = WorkspaceService(
            fixtures,
            api_key=resolved_settings.openai_api_key.get_secret_value(),  # pragma: allowlist secret
            seil_api_key=resolved_settings.resolved_seil_openai_api_key(),
            model=resolved_settings.openai_model,
            workflow_service=workflow_service,
            seller_evidence_service=seller_evidence_service,
            database=resolved_database,
            runtime=workspace_runtime,
            runtime_provider=resolved_settings.agent_runtime_provider,
        )
        yield
        close_identity = getattr(resolved_identity_adapter, "aclose", None)
        if close_identity is not None:
            await close_identity()
        await resolved_database.close()
        if resolved_catalog_database is not None:
            await resolved_catalog_database.close()

    application = FastAPI(
        title="SIRA + SEIL API",
        version="0.1.0",
        summary="B2B commerce agents with exact authority and verified fulfillment",
        description=(
            "Backend for SIRA buyer and SEIL seller B2B commerce agents. "
            "Development fixtures are fictional and never indicate production provider success."
        ),
        lifespan=lifespan,
        generate_unique_id_function=operation_id,
        responses={
            400: {"model": ErrorEnvelope, "description": "Invalid request semantics"},
            401: {"model": ErrorEnvelope, "description": "Authentication failed"},
            403: {"model": ErrorEnvelope, "description": "Authority denied"},
            404: {"model": ErrorEnvelope, "description": "Resource unavailable"},
            409: {"model": ErrorEnvelope, "description": "State or hash conflict"},
            422: {"model": ErrorEnvelope, "description": "Contract validation failed"},
            502: {"model": ErrorEnvelope, "description": "Provider rejected the operation"},
            503: {"model": ErrorEnvelope, "description": "Dependency or setup unavailable"},
        },
        openapi_tags=[
            {"name": "runtime"},
            {"name": "development"},
            {"name": "purchase requests"},
            {"name": "decision requests"},
            {"name": "decisions"},
            {"name": "execution"},
            {"name": "seller engagement"},
            {"name": "seller product evidence"},
            {"name": "commerce"},
            {"name": "stackfile"},
            {"name": "workflows"},
            {"name": "workspace"},
            {"name": "qualification marketplace"},
        ],
    )

    @application.middleware("http")
    async def request_identity(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        supplied = request.headers.get("X-Request-Id", "")
        safe_supplied = supplied if supplied and supplied.replace("-", "").isalnum() else None
        request.state.request_id = safe_supplied or f"rq_{uuid4().hex}"
        new_guest_token: str | None = None
        active_subject: str | None = None
        credential_subject: str | None = None
        protected_request = request.url.path.startswith("/v1/")
        authorization = request.headers.get("authorization", "")
        if protected_request and authorization:
            credential_subject = f"bearer:{authorization}"
        elif protected_request and guest_signer is not None:
            raw_token = request.cookies.get(guest_cookie_name, "")
            guest = guest_signer.verify(raw_token) if raw_token else None
            if guest is None:
                network_subject = request.client.host if request.client else "unknown"
                bootstrap = await abuse_limiter.check(
                    subject=f"network:{network_subject}",
                    scope="guest-bootstrap",
                    limit=60,
                    window_seconds=3_600,
                )
                if not bootstrap.allowed:
                    return _rate_limited_response(request, bootstrap)
                guest, new_guest_token = guest_signer.issue()
            request.state.guest_session = guest
            credential_subject = f"guest:{guest.session_id}"

        if protected_request:
            origin = request.headers.get("origin")
            if request.method not in {"GET", "HEAD", "OPTIONS"} and origin:
                allowed_origins = {
                    item
                    for item in (
                        _origin(resolved_settings.web_base_url),
                        _origin(resolved_settings.public_base_url),
                    )
                    if item
                }
                if resolved_settings.is_development:
                    allowed_origins.update({"http://localhost:3000", "http://127.0.0.1:3000"})
                if origin.rstrip("/") not in allowed_origins:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": {
                                "code": "ORIGIN_FORBIDDEN",
                                "message": (
                                    "This request did not originate from the SIRA workspace."
                                ),
                                "request_id": request.state.request_id,
                                "retryable": False,
                                "next_action": "reload_workspace",
                                "details": {},
                            }
                        },
                    )

            content_length = request.headers.get("content-length")
            if content_length and content_length.isdigit() and int(content_length) > 131_072:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "REQUEST_TOO_LARGE",
                            "message": "Request bodies are limited to 128 KB.",
                            "request_id": request.state.request_id,
                            "retryable": False,
                            "next_action": "send_less_context",
                            "details": {},
                        }
                    },
                )

        if credential_subject is not None:
            checks = [("api:minute", 120, 60)]
            if request.url.path == "/v1/workspace/chat" and request.method == "POST":
                checks.extend(
                    (
                        ("chat:minute", 8, 60),
                        ("chat:hour", 40, 3_600),
                        ("chat:day", 100, 86_400),
                    )
                )
            elif request.method not in {"GET", "HEAD", "OPTIONS"}:
                checks.append(("mutation:minute", 30, 60))
            for scope, limit, window_seconds in checks:
                decision = await abuse_limiter.check(
                    subject=credential_subject,
                    scope=scope,
                    limit=limit,
                    window_seconds=window_seconds,
                )
                if not decision.allowed:
                    return _rate_limited_response(request, decision)

            if request.url.path == "/v1/workspace/chat" and request.method == "POST":
                if not await abuse_limiter.acquire(subject=credential_subject, scope="active-chat"):
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": {
                                "code": "CHAT_ALREADY_RUNNING",
                                "message": "This workspace already has an agent run in progress.",
                                "request_id": request.state.request_id,
                                "retryable": True,
                                "next_action": "wait_for_current_run",
                                "details": {},
                            }
                        },
                        headers={"Retry-After": "2"},
                    )
                active_subject = credential_subject
        try:
            response = await call_next(request)
        finally:
            if active_subject is not None:
                await abuse_limiter.release(subject=active_subject, scope="active-chat")
        response.headers["X-Request-Id"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/v1/"):
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["Vary"] = "Cookie, Authorization, X-Workspace-Mode"
        if new_guest_token is not None:
            response.set_cookie(
                guest_cookie_name,
                new_guest_token,
                max_age=resolved_settings.guest_session_ttl_seconds,
                httponly=True,
                secure=not resolved_settings.is_development,
                samesite="lax",
                path="/",
            )
        return response

    @application.exception_handler(ApiProblem)
    async def api_problem(request: Request, error: ApiProblem) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": {
                    "code": error.code,
                    "message": error.message,
                    "request_id": request.state.request_id,
                    "retryable": error.retryable,
                    "next_action": error.next_action,
                    "details": error.details,
                }
            },
        )

    @application.exception_handler(PersistenceConflict)
    async def persistence_conflict(request: Request, error: PersistenceConflict) -> JSONResponse:
        translated = translate_persistence_conflict(error)
        return await api_problem(request, translated)

    @application.exception_handler(RequestValidationError)
    async def validation_problem(request: Request, error: RequestValidationError) -> JSONResponse:
        safe_details = [
            {"location": list(item["loc"]), "type": item["type"]} for item in error.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "The request did not match the frozen API contract.",
                    "request_id": request.state.request_id,
                    "retryable": False,
                    "next_action": "correct_request",
                    "details": {"fields": safe_details},
                }
            },
        )

    @application.exception_handler(SQLAlchemyError)
    async def database_problem(request: Request, error: SQLAlchemyError) -> JSONResponse:
        logger.exception(
            "database request failed",
            exc_info=error,
            extra={"request_id": request.state.request_id},
        )
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "Canonical CockroachDB state is temporarily unavailable.",
                    "request_id": request.state.request_id,
                    "retryable": True,
                    "next_action": "retry_later",
                    "details": {},
                }
            },
        )

    application.include_router(public_router)
    application.include_router(seller_router)
    application.include_router(qualification_router)
    application.include_router(router_v2)
    application.include_router(workspace_router)
    application.include_router(router)
    return application


app = create_app()
