"""Public research persistence and private seller onboarding, with isolated test data."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sira_api.product_marketplace import ProductMarketplace, publish_seller_observation
from sira_api.seller_schemas import SellerProductRegisterCreate
from sira_api.seller_service import SellerEvidenceService
from sqlalchemy import func, select, update

from integrations.product_search import ProductFact, ProductResearch, ResearchedProduct
from persistence.database import Database, DatabaseSettings
from persistence.marketplace_models import MarketplaceObservation, MarketplaceProduct
from persistence.models import Base, SellerPackVersion, SellerProduct


class SearchProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def search(
        self, query: str, *, limit: int = 5
    ) -> tuple[ProductResearch, list[dict[str, Any]]]:
        self.calls += 1
        return ProductResearch(
            products=[
                ResearchedProduct(
                    name="Example Calendar",
                    seller="Example",
                    website="https://example.com/calendar",
                    edition="Team",
                    category="scheduling",
                    summary="Shared scheduling for teams.",
                    facts=[
                        ProductFact(
                            field="price",
                            value=f"USD {10 + self.calls} per seat/month",
                            source_urls=["https://example.com/calendar/pricing"],
                        )
                    ],
                )
            ]
        ), [{"url": "https://example.com/calendar/pricing", "title": "Pricing"}]


@pytest.fixture
async def database() -> Any:
    db = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with db.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield db
    await db.close()


async def test_research_persists_across_service_instances_and_reuses_fresh_records(
    database: Database,
) -> None:
    provider = SearchProvider()
    marketplace = ProductMarketplace(database, provider)
    first = await marketplace.discover("org_buyer", query="shared calendar", limit=1)
    assert first["results"][0]["seller_attested"] is False
    assert first["results"][0]["evidence_status"] == "RESEARCH_ONLY"
    assert first["results"][0]["facts"][0]["observed_at"]
    recreated = ProductMarketplace(database, provider)
    cached = await recreated.discover("org_other_buyer", query="shared calendar", limit=1)
    assert cached["source"] == "catalog"
    assert cached["results"][0]["id"] == first["results"][0]["id"]
    assert provider.calls == 1
    await recreated.discover("org_buyer", query="shared calendar", limit=1, refresh=True)
    async with database.transaction("org_buyer") as session:
        assert await session.scalar(select(func.count()).select_from(MarketplaceProduct)) == 1
        assert await session.scalar(select(func.count()).select_from(MarketplaceObservation)) == 2
    detail = await recreated.product("org_buyer", first["results"][0]["id"])
    assert len(detail["observations"]) == 2
    assert sum(item["active"] for item in detail["observations"]) == 1
    assert "USD 12" in detail["price"]


async def test_expired_observations_trigger_research_and_empty_catalog_stays_empty(
    database: Database,
) -> None:
    provider = SearchProvider()
    marketplace = ProductMarketplace(database, provider)
    assert (await marketplace.search("org_buyer"))["results"] == []
    await marketplace.discover("org_buyer", query="calendar", limit=1)
    async with database.transaction("org_buyer") as session:
        await session.execute(
            update(MarketplaceObservation).values(
                expires_at=datetime.now(UTC) - timedelta(seconds=1)
            )
        )
    await marketplace.discover("org_buyer", query="calendar", limit=1)
    assert provider.calls == 2


async def test_registration_stays_private_until_publication_and_links_existing_research(
    database: Database,
) -> None:
    marketplace = ProductMarketplace(database, SearchProvider())
    researched = await marketplace.discover("org_buyer", query="calendar", limit=1)
    body = SellerProductRegisterCreate(
        name="Example Calendar",
        seller_name="Example",
        website="https://www.example.com/calendar/?tracking=unused",
        edition="Team",
        category="scheduling",
        summary="A seller's draft summary",
    ).model_dump()
    seller = SellerEvidenceService(database)
    _, registered = await seller.register_product(
        organization_id="org_seller",
        actor_id="editor",
        actor_role="SELLER_EDITOR",
        idempotency_key="register-calendar-001",
        body=body,
    )
    product_id = registered["results"][0]["id"]
    _, replay = await seller.register_product(
        organization_id="org_seller",
        actor_id="editor",
        actor_role="SELLER_EDITOR",
        idempotency_key="register-calendar-001",
        body=body,
    )
    assert registered == replay
    assert (
        await seller.search_products(
            organization_id="org_other", actor_id="editor", actor_role="SELLER_EDITOR", query=None
        )
    )["results"] == []
    before = await marketplace.product("org_buyer", researched["results"][0]["id"])
    assert not before["seller_attested"]
    assert "draft summary" not in str(before)
    async with database.transaction("org_seller") as session:
        product = await session.get(SellerProduct, product_id)
        assert product is not None
        # This helper is called only after SellerEvidenceService.publish validates review.
        pack = SellerPackVersion(
            id="pack_test_published",
            product_id=product_id,
            source_draft_id=product.current_draft_id,
            source_revision=1,
            source_revision_hash="sha256:" + "a" * 64,
            organization_id="org_seller",
            version=1,
            content_hash="sha256:" + "b" * 64,
            publisher_authority="SELLER_SEALED",
            payload={"claims": [{"field": "public_summary", "value": "Reviewed public summary"}]},
            published_by_actor_id="reviewer",
            published_at=datetime.now(UTC),
        )
        session.add(pack)
        await publish_seller_observation(
            session, organization_id="org_seller", product=product, pack=pack
        )
    after = await marketplace.product("org_buyer", researched["results"][0]["id"])
    assert after["seller_attested"]
    assert after["summary"] == "Reviewed public summary"
    assert {o["origin"] for o in after["observations"]} == {"PUBLIC_WEB", "SELLER_PUBLISHED"}
    async with database.transaction("org_seller") as session:
        await session.execute(
            update(MarketplaceObservation)
            .where(MarketplaceObservation.origin == "SELLER_PUBLISHED")
            .values(withdrawn_at=datetime.now(UTC))
        )
    assert not (await marketplace.product("org_buyer", after["id"]))["seller_attested"]
