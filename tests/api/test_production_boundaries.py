from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

import httpx
import pytest
import pytest_asyncio
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sira_api.config import ApiSettings
from sira_api.dependencies import (
    RequestContext,
    enforce_api_security,
    get_request_context,
    require_human_identity,
)
from sira_api.errors import ApiProblem
from sira_api.identity import VerifiedPrincipal
from sira_api.main import create_app

from persistence.database import Database, DatabaseSettings


class FakeIdentityAdapter:
    async def authenticate(self, bearer_token: str) -> VerifiedPrincipal | None:
        if bearer_token == "verified-test-token":
            return VerifiedPrincipal(
                organization_id="org_production_test",
                actor_id="usr_production_test",
                roles=frozenset({"requester"}),
                step_up_verified=False,
                identity_kind="HUMAN",
                party="BUYER",
            )
        if bearer_token == "verified-seller-token":
            return VerifiedPrincipal(
                organization_id="org_production_test",
                actor_id="usr_production_seller",
                roles=frozenset({"seller"}),
                step_up_verified=False,
                identity_kind="HUMAN",
                party="SELLER",
            )
        if bearer_token == "verified-service-token":
            return VerifiedPrincipal(
                organization_id="org_production_test",
                actor_id="svc_production_approver",
                roles=frozenset({"can_approve_purchase", "budget_owner"}),
                step_up_verified=True,
                identity_kind="SERVICE",
                party="BUYER",
            )
        return None


def production_settings() -> ApiSettings:
    return ApiSettings(
        app_env="production",
        database_url="postgresql+asyncpg://localhost:5432/sira",
        development_fixture_mode=False,
        demo_reset_enabled=False,
        browser_return_signing_key="production-test-browser-return-key",
    )


def test_configuration_requires_an_explicit_environment() -> None:
    with pytest.raises(ValidationError, match="APP_ENV must be explicitly set"):
        ApiSettings(app_env="unset")


def test_production_configuration_rejects_development_modes_including_defaults() -> None:
    with pytest.raises(ValidationError, match="DEVELOPMENT_FIXTURE_MODE=false"):
        ApiSettings(app_env="production")

    with pytest.raises(ValidationError, match="DEVELOPMENT_FIXTURE_MODE=false"):
        ApiSettings(
            app_env="production",
            development_fixture_mode=False,
            demo_reset_enabled=True,
        )


def test_production_configuration_requires_postgresql() -> None:
    with pytest.raises(ValidationError, match="PostgreSQL DATABASE_URL"):
        ApiSettings(
            app_env="production",
            database_url="sqlite+aiosqlite:///:memory:",
            development_fixture_mode=False,
            demo_reset_enabled=False,
        )


def test_production_configuration_requires_stable_browser_return_signing_key() -> None:
    with pytest.raises(ValidationError, match="32-byte BROWSER_RETURN_SIGNING_KEY"):
        ApiSettings(
            app_env="production",
            database_url="postgresql+asyncpg://localhost:5432/sira",
            development_fixture_mode=False,
            demo_reset_enabled=False,
        )


def test_app_startup_rechecks_runtime_modes_after_settings_mutation() -> None:
    settings = production_settings()
    settings.development_fixture_mode = True

    with pytest.raises(ValueError, match="DEVELOPMENT_FIXTURE_MODE=false"):
        create_app(settings=settings)


@pytest.mark.asyncio
async def test_app_rejects_injected_non_postgresql_database_in_production() -> None:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    try:
        with pytest.raises(ValueError, match="PostgreSQL database engine"):
            create_app(settings=production_settings(), database=database)
    finally:
        await database.close()


@pytest_asyncio.fixture
async def production_security_client() -> AsyncIterator[httpx.AsyncClient]:
    """Exercise production identity and route scope before any persistence access."""

    application = FastAPI()
    application.state.settings = production_settings()
    application.state.identity_adapter = FakeIdentityAdapter()

    @application.exception_handler(ApiProblem)
    async def api_problem(_request: Request, error: ApiProblem) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={"error": {"code": error.code, "message": error.message}},
        )

    protected = APIRouter(dependencies=[Depends(enforce_api_security)])

    @protected.get("/v1/purchase-requests/{request_id}/decision-view")
    @protected.get("/v1/purchase-requests/{request_id}/purchase-brief")
    @protected.get("/v1/organizations/{organization_id}/stackfile")
    @protected.get("/v1/workflows/{workflow_id}")
    async def buyer_private(
        context: Annotated[RequestContext, Depends(get_request_context)],
    ) -> dict[str, object]:
        return {
            "organization_id": context.organization_id,
            "actor_id": context.actor_id,
            "party": context.party,
        }

    @protected.post("/v1/engagements/{engagement_id}/consent")
    async def seller_consent(
        context: Annotated[RequestContext, Depends(get_request_context)],
    ) -> dict[str, object]:
        return {"actor_id": context.actor_id, "party": context.party}

    @protected.post("/v1/approval-requests/{approval_id}/approve")
    async def approve(context: Annotated[RequestContext, Depends(get_request_context)]) -> None:
        require_human_identity(context)

    application.include_router(protected)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="https://api.test"
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_production_identity_ignores_browser_supplied_claims(
    production_security_client: httpx.AsyncClient,
) -> None:
    response = await production_security_client.get(
        "/v1/purchase-requests/req_production/decision-view",
        headers={
            "Authorization": "Bearer verified-test-token",
            "X-Actor-Id": "usr_attacker_supplied",
            "X-Actor-Party": "SELLER",
            "X-Organization-Id": "org_attacker_supplied",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "organization_id": "org_production_test",
        "actor_id": "usr_production_test",
        "party": "BUYER",
    }


@pytest.mark.asyncio
async def test_production_rejects_unverified_bearer(
    production_security_client: httpx.AsyncClient,
) -> None:
    response = await production_security_client.get(
        "/v1/purchase-requests/req_missing/decision-view",
        headers={"Authorization": "Bearer invalid"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_FAILED"


@pytest.mark.asyncio
async def test_production_seller_is_scoped_only_to_engagement_consent(
    production_security_client: httpx.AsyncClient,
) -> None:
    seller_headers = {
        "Authorization": "Bearer verified-seller-token",
        "X-Actor-Id": "usr_attacker_supplied",
        "X-Actor-Party": "BUYER",
        "X-Organization-Id": "org_attacker_supplied",
    }
    buyer_private_paths = (
        "/v1/purchase-requests/req_production/decision-view",
        "/v1/purchase-requests/req_production/purchase-brief",
        "/v1/organizations/org_production_test/stackfile",
        "/v1/workflows/wf_production",
    )
    for path in buyer_private_paths:
        denied = await production_security_client.get(path, headers=seller_headers)
        assert denied.status_code == 403, denied.text
        assert denied.json()["error"]["code"] == "SELLER_ROUTE_FORBIDDEN"

    consent = await production_security_client.post(
        "/v1/engagements/eng_production/consent",
        headers=seller_headers,
    )
    assert consent.status_code == 200, consent.text
    assert consent.json() == {
        "actor_id": "usr_production_seller",
        "party": "SELLER",
    }


@pytest.mark.asyncio
async def test_production_service_identity_cannot_approve_as_a_human(
    production_security_client: httpx.AsyncClient,
) -> None:
    response = await production_security_client.post(
        "/v1/approval-requests/apr_production/approve",
        headers={
            "Authorization": "Bearer verified-service-token",
            "X-Identity-Kind": "HUMAN",
        },
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "HUMAN_IDENTITY_REQUIRED"
