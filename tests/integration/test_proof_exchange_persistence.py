from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from persistence.database import Database, DatabaseSettings
from persistence.models import Base, BuyerProofAdapterProjection, Organization, ProofApproval
from persistence.proof_repository import ProofExchangeRepository
from proof.exchange import candidate_release, exact_approval_subject, project_published_adapter


async def _database() -> Database:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.transaction("org_buyer") as session:
        session.add_all(
            (
                Organization(id="org_buyer", name="Buyer", version=1),
                Organization(id="org_seller", name="Seller", version=1),
            )
        )
    return database


def _projection() -> dict[str, object]:
    return project_published_adapter(
        source_seller_organization_id="org_seller",
        source_pack_version_id="pack-a-v1",
        source_pack_content_hash="sha256:" + "a" * 64,
        publication_event_key="seller-pack-published:pack-a-v1",
        published_payload={
            "proof_adapter": {
                "adapter_id": "adapter-a",
                "artifact_digest": "sha256:" + "b" * 64,
                "protocol_version": "TrialCase/v0",
                "capabilities": ["SUPPORT_SUMMARIZATION"],
                "declared_region": "EU",
                "fixed_price": {"amount": "0.02", "currency": "USD"},
                "conformance_hash": "sha256:" + "c" * 64,
            },
            "evidence": [],
        },
    )


@pytest.mark.asyncio
async def test_publication_projection_and_approval_are_idempotent_and_tenant_scoped() -> None:
    database = await _database()
    try:
        projection = _projection()
        release = candidate_release(projection)
        now = datetime(2030, 1, 1, tzinfo=UTC)
        subject = exact_approval_subject(
            manifest_hash="sha256:" + "d" * 64,
            environment_fingerprint="sha256:" + "e" * 64,
            decision_hash="sha256:" + "f" * 64,
            release=release,
            datahub_owner_urn="urn:li:corpGroup:support-data-owners",
            actor_id="seeded_support_owner",
            actor_role="DATA_OWNER",
            expires_at=now + timedelta(minutes=15),
        )
        async with database.transaction("org_buyer") as session:
            repository = ProofExchangeRepository(session, "org_buyer")
            first = await repository.materialize_projection(projection)
            second = await repository.materialize_projection(projection)
            first_approval = await repository.create_approval(
                subject=subject,
            )
            second_approval = await repository.create_approval(
                subject=subject,
            )
            assert first.id == second.id
            assert first_approval.id == second_approval.id

        async with database.transaction("org_seller") as session:
            seller_projections = list(
                (
                    await session.execute(
                        select(BuyerProofAdapterProjection).where(
                            BuyerProofAdapterProjection.organization_id == "org_seller"
                        )
                    )
                ).scalars()
            )
            seller_approvals = list(
                (
                    await session.execute(
                        select(ProofApproval).where(ProofApproval.organization_id == "org_seller")
                    )
                ).scalars()
            )
            assert seller_projections == []
            assert seller_approvals == []
    finally:
        await database.close()
