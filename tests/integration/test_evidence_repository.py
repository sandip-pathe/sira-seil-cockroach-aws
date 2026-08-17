from __future__ import annotations

from sqlalchemy import select

from domain.evidence_pipeline import parse_evidence
from persistence.database import Database, DatabaseSettings
from persistence.evidence_repository import EvidenceRepository
from persistence.models import Base, Organization
from persistence.qualification_models import EvidenceSpan


async def test_parsed_evidence_is_idempotent_private_then_explicitly_published() -> None:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.transaction("org-seller") as session:
        session.add(Organization(id="org-seller", name="Seller"))
    body = b"EU recordings stay in Frankfurt for 30 days."
    parsed = parse_evidence(source_version_id="source-v1", body=body, content_type="text/plain")
    try:
        async with database.transaction("org-seller") as session:
            repository = EvidenceRepository(session, "org-seller")
            source = await repository.store_parsed(
                product_id="product-1",
                object_bucket="local-evidence",
                object_key="org-seller/evidence/sha256/abc",
                object_version_id="sha256-abc",
                size_bytes=len(body),
                parsed=parsed,
            )
            duplicate = await repository.store_parsed(
                product_id="product-1",
                object_bucket="local-evidence",
                object_key="org-seller/evidence/sha256/abc",
                object_version_id="sha256-abc",
                size_bytes=len(body),
                parsed=parsed,
            )
            assert duplicate.id == source.id
            private = tuple((await session.execute(select(EvidenceSpan))).scalars())
            assert {item.visibility for item in private} == {"PRIVATE"}
            await repository.publish(source)

        async with database.transaction("org-seller") as session:
            published = tuple((await session.execute(select(EvidenceSpan))).scalars())
        assert {item.visibility for item in published} == {"BUYER_SAFE"}
        assert published[0].source_version_id == "source-v1"
    finally:
        await database.close()
