"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import Response

from persistence.database import Database, DatabaseSettings
from persistence.repositories import PersistenceConflict

from .callback_state import BrowserReturnStateSigner
from .config import ApiSettings, get_settings
from .errors import ApiProblem
from .fixtures import DemoFixtureBundle
from .identity import IdentityAdapter, IntrospectionIdentityAdapter
from .marketplace import (
    SellerOrganizationDirectory,
    SellerPrincipalBinding,
    StaticSellerOrganizationDirectory,
)
from .routes import public_router, router
from .routes_v2 import router_v2
from .schemas import ErrorEnvelope
from .seller_routes import seller_router
from .seller_service import SellerEvidenceService
from .service import WorkflowService, translate_persistence_conflict
from .workspace_routes import workspace_router
from .workspace_service import WorkspaceService


def operation_id(route: APIRoute) -> str:
    """Keep generated-client names stable when paths are refactored."""

    return route.name


def create_app(
    *,
    settings: ApiSettings | None = None,
    database: Database | None = None,
    identity_adapter: IdentityAdapter | None = None,
    seller_directory: SellerOrganizationDirectory | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_settings.assert_safe_runtime()
    resolved_database = database or Database(
        DatabaseSettings(database_url=resolved_settings.database_url)
    )
    if (
        not resolved_settings.is_development
        and resolved_database.engine.dialect.name != "postgresql"
    ):
        raise ValueError("production requires a PostgreSQL database engine with RLS support")
    resolved_identity_adapter = identity_adapter
    if not resolved_settings.is_development and resolved_identity_adapter is None:
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

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.settings = resolved_settings
        application.state.database = resolved_database
        application.state.identity_adapter = resolved_identity_adapter
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
            allow_development_tenant_bootstrap=resolved_settings.is_development,
            browser_return_signer=BrowserReturnStateSigner(
                resolved_settings.browser_return_signing_secret()
            ),
            browser_return_ttl_seconds=resolved_settings.browser_return_ttl_seconds,
            seller_directory=resolved_seller_directory,
            quote_clock=fixture_quote_clock,
        )
        seller_evidence_service = SellerEvidenceService(
            resolved_database,
            development_fixture_mode=resolved_settings.development_fixture_mode,
        )
        application.state.workflow_service = workflow_service
        application.state.seller_evidence_service = seller_evidence_service
        application.state.workspace_service = WorkspaceService(
            fixtures,
            api_key=resolved_settings.openai_api_key.get_secret_value(),
            model=resolved_settings.openai_model,
            workflow_service=workflow_service,
            seller_evidence_service=seller_evidence_service,
            database=resolved_database,
        )
        yield
        close_identity = getattr(resolved_identity_adapter, "aclose", None)
        if close_identity is not None:
            await close_identity()
        await resolved_database.close()

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
        ],
    )

    @application.middleware("http")
    async def request_identity(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        supplied = request.headers.get("X-Request-Id", "")
        safe_supplied = supplied if supplied and supplied.replace("-", "").isalnum() else None
        request.state.request_id = safe_supplied or f"rq_{uuid4().hex}"
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
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
        del error
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "Canonical PostgreSQL state is temporarily unavailable.",
                    "request_id": request.state.request_id,
                    "retryable": True,
                    "next_action": "retry_later",
                    "details": {},
                }
            },
        )

    application.include_router(public_router)
    application.include_router(seller_router)
    application.include_router(router_v2)
    application.include_router(workspace_router)
    application.include_router(router)
    return application


app = create_app()
