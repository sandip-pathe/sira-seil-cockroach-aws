from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sira_api.exchange_service import ExchangeService

from domain import content_hash
from domain.exchange_route import ExchangeRouteCodec
from persistence.database import Database, DatabaseSettings
from persistence.models import (
    Base,
    Organization,
    PurchaseBriefVersion,
    PurchaseRequest,
    RequirementBriefVersion,
)


async def test_buyer_release_creates_distinct_safe_party_projections() -> None:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    now = datetime(2026, 8, 18, tzinfo=UTC)
    requirement_payload = {
        "category_id": "meeting_intelligence",
        "intent": "Find meeting intelligence",
        "desired_outcome": "Find source-linked decisions",
        "team": {"seat_count": 10},
        "data_profile": {"client_conversations_restricted": True},
        "hard_requirements": [{"field": "source_links", "value": True}],
        "preferences": [{"field": "admin_effort", "value": "low"}],
        "allowed_stack_context": {"required_integrations": ["slack"]},
        "seller_questions": ["Confirm availability"],
        "expires_at": (now + timedelta(days=2)).isoformat(),
    }
    requirement_hash = content_hash(requirement_payload)
    try:
        async with database.transaction("org-buyer") as session:
            session.add_all(
                (
                    Organization(id="org-buyer", name="Buyer"),
                    Organization(id="org-seller", name="Seller"),
                    PurchaseRequest(
                        id="request-1",
                        organization_id="org-buyer",
                        intent="Find meeting intelligence",
                        status="DECISION_READY",
                        visibility="SELECTIVE",
                        version=1,
                        payload={},
                        request_hash=content_hash({"id": "request-1"}),
                    ),
                )
            )
            await session.flush()
            session.add(
                PurchaseBriefVersion(
                    id="brief-1",
                    organization_id="org-buyer",
                    purchase_request_id="request-1",
                    version=1,
                    status="APPROVED",
                    payload={},
                    content_hash=content_hash({"id": "brief-1"}),
                    supersedes_id=None,
                )
            )
            await session.flush()
            session.add(
                RequirementBriefVersion(
                    id="requirement-1",
                    organization_id="org-buyer",
                    purchase_request_id="request-1",
                    purchase_brief_id="brief-1",
                    version=1,
                    payload=requirement_payload,
                    content_hash=requirement_hash,
                )
            )

        service = ExchangeService(
            database,
            ExchangeRouteCodec("route-secret-material" * 2),
            clock=lambda: now,
        )
        created = await service.create_case(
            organization_id="org-buyer",
            actor_id="buyer-1",
            party="BUYER",
            idempotency_key="release-request-1",
            purchase_request_id="request-1",
            seller_organization_id="org-seller",
        )
        token = str(created["route_capability"])
        case_id = str(created["case_id"])
        buyer = await service.view_case(
            organization_id="org-buyer",
            party="BUYER",
            case_id=case_id,
            route_capability=token,
        )
        seller = await service.view_case(
            organization_id="org-seller",
            party="SELLER",
            case_id=case_id,
            route_capability=token,
        )

        assert buyer["party"] == "BUYER"
        assert seller["party"] == "SELLER"
        assert buyer["released"] == seller["released"]
        serialized = repr(seller["released"]).lower()
        assert "org-buyer" not in serialized
        assert "hidden_budget" not in serialized
        assert "requirement-1" not in serialized
        assert "org-buyer" not in token
    finally:
        await database.close()
