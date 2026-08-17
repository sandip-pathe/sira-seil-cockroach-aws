from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sira_api.errors import ApiProblem
from sira_api.exchange_service import ExchangeService
from sira_api.marketplace import SellerPrincipalBinding, StaticSellerOrganizationDirectory

from domain import content_hash
from domain.evidence_pipeline import parse_evidence
from domain.exchange_route import ExchangeRoute, ExchangeRouteCodec
from persistence.database import Database, DatabaseSettings
from persistence.evidence_repository import EvidenceRepository
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
            seller_directory=StaticSellerOrganizationDirectory(
                (
                    SellerPrincipalBinding(
                        candidate_id="candidate-1",
                        product_id="product-1",
                        seller_actor_id="seller-1",
                        seller_organization_id="org-seller",
                        merchant_name="Seller",
                        merchant_url="https://seller.example.test/pay",
                    ),
                )
            ),
            clock=lambda: now,
        )
        parsed = parse_evidence(
            source_version_id="source-version-1",
            body=b"The ten-seat workspace supports source-linked answers and Slack.",
            content_type="text/plain",
        )
        async with database.transaction("org-seller") as session:
            evidence_repository = EvidenceRepository(session, "org-seller")
            source = await evidence_repository.store_parsed(
                product_id="product-1",
                object_bucket="test",
                object_key="evidence.txt",
                object_version_id="version-1",
                size_bytes=64,
                parsed=parsed,
            )
            await evidence_repository.publish(source)
        created = await service.create_case(
            organization_id="org-buyer",
            actor_id="buyer-1",
            party="BUYER",
            idempotency_key="release-request-1",
            purchase_request_id="request-1",
            candidate_id="candidate-1",
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

        evidence = await service.publish_evidence(
            organization_id="org-seller",
            actor_id="seller-1",
            party="SELLER",
            case_id=case_id,
            route_capability=token,
            idempotency_key="publish-evidence-1",
            expected_version=2,
            summary="Published evidence supports the requirement.",
            published_span_ids=[parsed.spans[0].id],
        )
        assert evidence["state"] == "EVIDENCE_RELEASED"

        offered = await service.propose_offer(
            organization_id="org-buyer",
            actor_id="buyer-1",
            party="BUYER",
            case_id=case_id,
            route_capability=token,
            idempotency_key="offer-1",
            expected_version=3,
            currency="USD",
            lines=[
                {
                    "item_id": "workspace",
                    "description": "Ten-seat annual workspace",
                    "quantity": 1,
                    "unit_price": "1200.00",
                }
            ],
            total=Decimal("1200.00"),
            rationale="Buyer-proposed procurement terms.",
            changed_terms=[],
            expires_at=now + timedelta(days=1),
        )
        assert offered["state"] == "OFFERED"
        first_hash = offered["released"]["current_offer"]["offer_hash"]

        countered = await service.propose_offer(
            organization_id="org-seller",
            actor_id="seller-1",
            party="SELLER",
            case_id=case_id,
            route_capability=token,
            idempotency_key="counter-1",
            expected_version=4,
            currency="USD",
            lines=[
                {
                    "item_id": "workspace",
                    "description": "Ten-seat annual workspace",
                    "quantity": 1,
                    "unit_price": "1100.00",
                }
            ],
            total=Decimal("1100.00"),
            rationale="Seller offers a launch discount.",
            changed_terms=["lines", "total"],
            expires_at=now + timedelta(days=1),
        )
        assert countered["state"] == "COUNTERED"
        counter = countered["released"]["current_offer"]
        assert counter["predecessor_hash"] == first_hash

        accepted = await service.accept_offer(
            organization_id="org-buyer",
            actor_id="buyer-1",
            party="BUYER",
            case_id=case_id,
            route_capability=token,
            idempotency_key="accept-counter-1",
            expected_version=5,
            offer_hash=counter["offer_hash"],
        )
        assert accepted["state"] == "AGREED_PENDING_APPROVAL"

        approved = await service.approve_offer(
            organization_id="org-buyer",
            actor_id="budget-owner-1",
            party="BUYER",
            case_id=case_id,
            route_capability=token,
            idempotency_key="approve-counter-1",
            expected_version=6,
            offer_hash=counter["offer_hash"],
            approval_expires_at=now + timedelta(hours=4),
        )
        assert approved["state"] == "APPROVED_FOR_HANDOFF"
        assert approved["released"]["approval"]["offer_hash"] == counter["offer_hash"]

        approved_replay = await service.approve_offer(
            organization_id="org-buyer",
            actor_id="budget-owner-1",
            party="BUYER",
            case_id=case_id,
            route_capability=token,
            idempotency_key="approve-counter-1",
            expected_version=6,
            offer_hash=counter["offer_hash"],
            approval_expires_at=now + timedelta(hours=4),
        )
        assert approved_replay["state"] == "APPROVED_FOR_HANDOFF"
        assert approved_replay["version"] == 7

        handoff = await service.create_handoff(
            organization_id="org-buyer",
            party="BUYER",
            case_id=case_id,
            route_capability=token,
            expected_version=7,
            offer_hash=counter["offer_hash"],
        )
        assert handoff["status"] == "READY"
        assert handoff["destination_url"] == "https://seller.example.test/pay"
        opened = await service.open_handoff(
            organization_id="org-buyer",
            party="BUYER",
            case_id=case_id,
            route_capability=token,
            handoff_id=handoff["id"],
            handoff_hash=handoff["handoff_hash"],
        )
        assert opened["status"] == "OPENED"
        assert opened["handoff_hash"] == handoff["handoff_hash"]
    finally:
        await database.close()


async def test_guest_bridge_requires_explicit_development_policy() -> None:
    now = datetime(2026, 8, 18, tzinfo=UTC)
    codec = ExchangeRouteCodec("route-secret-material" * 2)
    route = ExchangeRoute(
        case_id="case-1",
        candidate_id="candidate-1",
        product_id="product-1",
        merchant_name="Seller",
        merchant_url="https://seller.example.test/pay",
        buyer_organization_id="org_guest_browser",
        seller_organization_id="org-seller",
        development_guest_organization_id="org_guest_browser",
        expires_at=now + timedelta(hours=1),
    )
    token = codec.encode(route)
    denied = ExchangeService(
        Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:")),
        codec,
        clock=lambda: now,
    )
    enabled = ExchangeService(
        denied.database,
        codec,
        allow_development_guest_bridge=True,
        clock=lambda: now,
    )
    try:
        with pytest.raises(ApiProblem, match="authorized exchange participant"):
            denied._decode_route(
                organization_id="org_guest_browser",
                party="SELLER",
                case_id="case-1",
                route_capability=token,
                guest_identity=True,
            )
        with pytest.raises(ApiProblem, match="authorized exchange participant"):
            enabled._decode_route(
                organization_id="org_guest_browser",
                party="SELLER",
                case_id="case-1",
                route_capability=token,
                guest_identity=False,
            )
        assert (
            enabled._decode_route(
                organization_id="org_guest_browser",
                party="SELLER",
                case_id="case-1",
                route_capability=token,
                guest_identity=True,
            )
            == route
        )
    finally:
        await denied.database.close()
