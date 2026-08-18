"""Publish the local demo catalogue through the real Bedrock + CockroachDB path."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from sira_agents.bedrock_runtime import TitanEmbeddingClient, create_bedrock_client
from sira_api.config import ApiSettings
from sira_api.fixtures import DemoFixtureBundle
from sira_api.workspace_service import WorkspaceService
from sqlalchemy import select

from domain import content_hash
from persistence.database import Database, DatabaseSettings
from persistence.qualification_models import (
    ActiveProductBundle,
    CatalogProjectionVersion,
    ProductBundle,
    ProductBundleMember,
    ProductEmbedding,
    ProductTwinVersion,
)
from persistence.qualification_repository import QualificationRepository


def _embedding_text(product: dict[str, Any]) -> str:
    values = (
        product.get("name"),
        product.get("seller"),
        product.get("edition"),
        product.get("summary"),
        " ".join(str(item) for item in product.get("claims", ())),
        " ".join(str(item) for item in product.get("integrations", ())),
    )
    return "\n".join(str(value).strip() for value in values if str(value or "").strip())


def _seller_organization(product_id: str) -> str:
    suffix = product_id.rsplit("_", 1)[-1]
    if suffix not in {"a", "b", "c", "d"}:
        raise ValueError("local product id has no seller organization")
    return f"org_seller_fixture_{suffix}"


async def _publish_product(
    database: Database,
    embedding_client: TitanEmbeddingClient,
    product: dict[str, Any],
) -> bool:
    product_id = str(product["id"])
    organization_id = _seller_organization(product_id)
    async with database.transaction(organization_id) as session:
        existing = await session.scalar(
            select(ActiveProductBundle).where(ActiveProductBundle.product_id == product_id)
        )
    if existing is not None:
        return False

    embedded = await embedding_client.embed(_embedding_text(product))
    vector_literal = "[" + ",".join(format(value, ".9g") for value in embedded.vector) + "]"
    public_payload = {
        key: value
        for key, value in product.items()
        if key
        in {
            "id",
            "name",
            "seller",
            "edition",
            "price",
            "billing_unit",
            "summary",
            "claims",
            "integrations",
            "website",
            "evidence_freshness",
            "source_refs",
        }
    }
    twin_payload = {
        "product_id": product_id,
        "edition": product.get("edition"),
        "claims": product.get("claims", []),
        "integrations": product.get("integrations", []),
    }
    twin_id = f"twin_{product_id}_1"
    catalog_id = f"catalog_{product_id}_1"
    bundle_id = f"bundle_{product_id}_1"
    twin_hash = content_hash(twin_payload)
    catalog_hash = content_hash(public_payload)
    members = (
        (0, "PRODUCT_TWIN", twin_id, twin_hash),
        (1, "CATALOG_PROJECTION", catalog_id, catalog_hash),
    )
    bundle_digest = content_hash(
        [
            {"ordinal": ordinal, "kind": kind, "id": identifier, "hash": digest}
            for ordinal, kind, identifier, digest in members
        ]
    )

    async with database.transaction(organization_id) as session:
        session.add_all(
            (
                ProductTwinVersion(
                    id=twin_id,
                    product_id=product_id,
                    version=1,
                    content_hash=twin_hash,
                    payload=twin_payload,
                    published_by_actor_id="local-demo-publisher",
                    published_at=datetime.now(UTC),
                    organization_id=organization_id,
                ),
                CatalogProjectionVersion(
                    id=catalog_id,
                    product_id=product_id,
                    version=1,
                    content_hash=catalog_hash,
                    buyer_safe_payload=public_payload,
                    organization_id=organization_id,
                ),
            )
        )
        await session.flush()
        session.add(
            ProductBundle(
                id=bundle_id,
                product_id=product_id,
                version=1,
                product_twin_version_id=twin_id,
                catalog_projection_version_id=catalog_id,
                disclosure_policy_version="local-demo-v1",
                embedding_profile="titan-v2:1024:normalize",
                digest=bundle_digest,
                state="READY",
                organization_id=organization_id,
            )
        )
        await session.flush()
        session.add_all(
            tuple(
                ProductBundleMember(
                    id=f"member_{product_id}_1_{ordinal}",
                    bundle_id=bundle_id,
                    ordinal=ordinal,
                    member_kind=kind,
                    member_id=identifier,
                    member_hash=digest,
                    organization_id=organization_id,
                )
                for ordinal, kind, identifier, digest in members
            )
        )
        session.add(
            ProductEmbedding(
                id=f"embedding_{product_id}_1",
                bundle_id=bundle_id,
                product_id=product_id,
                category="business-software",
                visibility="PUBLIC",
                content_hash=content_hash(
                    {
                        "model_id": embedded.model_id,
                        "text": _embedding_text(product),
                    }
                ),
                model_id=embedded.model_id,
                dimensions=embedded.dimensions,
                embedding=vector_literal,
                organization_id=organization_id,
            )
        )
        await session.flush()
        await QualificationRepository(session, organization_id).activate_bundle(
            bundle_id=bundle_id,
            actor_id="local-demo-publisher",
            expected_digest=bundle_digest,
        )
    return True


async def seed() -> int:
    settings = ApiSettings()
    database = Database(DatabaseSettings())
    embedding_client = TitanEmbeddingClient(
        client=create_bedrock_client(
            region=settings.aws_region,
            profile=settings.aws_profile.strip() or None,
        ),
        model_id=settings.bedrock_embedding_model_id,
    )
    # Only seller-published listings enter the marketplace. Research-only rows
    # remain visible in the legacy catalogue but never masquerade as seller evidence.
    products = [
        product
        for product in WorkspaceService(DemoFixtureBundle.load()).catalog()
        if product.get("listing_origin") == "SELLER_PUBLISHED"
    ]
    try:
        published = sum(
            [await _publish_product(database, embedding_client, product) for product in products]
        )
    finally:
        await database.close()
    return published


def main() -> int:
    asyncio.run(seed())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
