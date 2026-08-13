from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from domain import content_hash
from persistence.database import Database, DatabaseSettings
from persistence.models import Base
from persistence.qualification_models import (
    ActiveProductBundle,
    CatalogProjectionVersion,
    DecisionDependency,
    ProductBundle,
    ProductBundleMember,
    ProductTwinVersion,
    QualificationAttempt,
    QualificationDecision,
    QualificationMission,
    QualificationMissionBundle,
)
from persistence.qualification_repository import QualificationRepository
from persistence.repositories import PersistenceConflict, RecordNotFound


async def _database() -> Database:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return database


async def _seed_bundle(
    database: Database, *, version: int, state: str = "READY"
) -> tuple[str, str]:
    organization_id = "org_seller"
    product_id = "product-qualified"
    twin_id = f"twin-{version}"
    catalog_id = f"catalog-{version}"
    bundle_id = f"bundle-{version}"
    twin_hash = content_hash({"twin": version})
    catalog_hash = content_hash({"catalog": version})
    members = (
        (0, "PRODUCT_TWIN", twin_id, twin_hash),
        (1, "CATALOG_PROJECTION", catalog_id, catalog_hash),
    )
    digest = content_hash(
        [
            {"ordinal": ordinal, "kind": kind, "id": item_id, "hash": item_hash}
            for ordinal, kind, item_id, item_hash in members
        ]
    )
    async with database.transaction(organization_id) as session:
        session.add_all(
            [
                ProductTwinVersion(
                    id=twin_id,
                    product_id=product_id,
                    version=version,
                    content_hash=twin_hash,
                    payload={"hosting": "EU", "version": version},
                    published_by_actor_id="seller-human",
                    published_at=datetime.now(UTC),
                    organization_id=organization_id,
                ),
                CatalogProjectionVersion(
                    id=catalog_id,
                    product_id=product_id,
                    version=version,
                    content_hash=catalog_hash,
                    buyer_safe_payload={"hosting": "EU"},
                    organization_id=organization_id,
                ),
            ]
        )
        await session.flush()
        session.add(
            ProductBundle(
                id=bundle_id,
                product_id=product_id,
                version=version,
                product_twin_version_id=twin_id,
                catalog_projection_version_id=catalog_id,
                disclosure_policy_version="buyer-safe-v1",
                embedding_profile="titan-v2:1024:normalize",
                digest=digest,
                state=state,
                organization_id=organization_id,
            )
        )
        await session.flush()
        session.add_all(
            [
                ProductBundleMember(
                    id=f"member-{version}-{ordinal}",
                    bundle_id=bundle_id,
                    ordinal=ordinal,
                    member_kind=kind,
                    member_id=item_id,
                    member_hash=item_hash,
                    organization_id=organization_id,
                )
                for ordinal, kind, item_id, item_hash in members
            ]
        )
    return bundle_id, digest


async def _seed_mission_attempt(
    database: Database, *, bundle_id: str, bundle_digest: str, attempt_id: str
) -> None:
    digest = content_hash({"mission": attempt_id})
    async with database.transaction("org_buyer") as session:
        session.add(
            QualificationMission(
                id=f"mission-{attempt_id}",
                buyer_context_version_id="buyer-context-v1",
                buyer_context_hash=digest,
                buyer_context_payload={"company": "Buyer"},
                requirement_brief_version_id="brief-v1",
                requirement_brief_hash=digest,
                requirement_brief_payload={"category": "meeting-intelligence"},
                procurement_policy_version="policy-v1",
                procurement_policy_hash=digest,
                procurement_policy_payload={"human_approval": True},
                trace_id=f"trace-{attempt_id}",
                state="RUNNING",
                version=1,
                organization_id="org_buyer",
            )
        )
        await session.flush()
        session.add(
            QualificationAttempt(
                id=attempt_id,
                mission_id=f"mission-{attempt_id}",
                root_attempt_id=attempt_id,
                predecessor_attempt_id=None,
                replacement_depth=0,
                state="QUEUED",
                generation=0,
                organization_id="org_buyer",
            )
        )
        await session.flush()
        session.add(
            QualificationMissionBundle(
                id=f"mission-bundle-{attempt_id}",
                mission_id=f"mission-{attempt_id}",
                attempt_id=attempt_id,
                product_id="product-qualified",
                seller_organization_id="org_seller",
                bundle_id=bundle_id,
                bundle_digest=bundle_digest,
                organization_id="org_buyer",
            )
        )


@pytest.mark.asyncio
async def test_repository_activates_snapshots_checkpoints_and_finalizes() -> None:
    database = await _database()
    bundle_id, bundle_digest = await _seed_bundle(database, version=1)
    await _seed_mission_attempt(
        database,
        bundle_id=bundle_id,
        bundle_digest=bundle_digest,
        attempt_id="attempt-complete",
    )
    try:
        async with database.transaction("org_seller") as session:
            repository = QualificationRepository(session, "org_seller")
            with pytest.raises(RecordNotFound):
                await repository.activate_bundle(
                    bundle_id="missing", actor_id="seller", expected_digest=bundle_digest
                )
            with pytest.raises(PersistenceConflict, match="digest changed"):
                await repository.activate_bundle(
                    bundle_id=bundle_id,
                    actor_id="seller",
                    expected_digest="sha256:" + "0" * 64,
                )
            activated = await repository.activate_bundle(
                bundle_id=bundle_id,
                actor_id="seller",
                expected_digest=bundle_digest,
            )
            assert activated.state == "ACTIVE"

        async with database.transaction("org_buyer") as session:
            repository = QualificationRepository(session, "org_buyer")
            with pytest.raises(ValueError, match="between 1 and 600"):
                await repository.claim_attempt(
                    attempt_id="attempt-complete", lease_owner="worker", lease_seconds=0
                )
            lease = await repository.claim_attempt(
                attempt_id="attempt-complete", lease_owner="worker", lease_seconds=300
            )
            dependencies = await repository.snapshot_attempt(lease=lease)
            assert {item.kind for item in dependencies} >= {
                "BUYER_CONTEXT",
                "REQUIREMENT_BRIEF",
                "PROCUREMENT_POLICY",
                "PRODUCT_BUNDLE",
                "PRODUCT_TWIN",
                "CATALOG_PROJECTION",
            }
            repeated = await repository.snapshot_attempt(lease=lease)
            assert repeated == dependencies
            checkpoint = await repository.checkpoint_attempt(
                lease=lease,
                sequence=2,
                kind="MODEL_COMPLETE",
                payload={"model": "nova"},
            )
            assert checkpoint.sequence == 2

        async with database.transaction("org_buyer") as session:
            repository = QualificationRepository(session, "org_buyer")
            with pytest.raises(PersistenceConflict, match="outside the committed snapshot"):
                await repository.finalize_attempt(
                    lease=lease,
                    recommended_product_id="product-qualified",
                    payload={"summary": "invalid"},
                    cited_dependency_ids=frozenset({"not-snapshotted"}),
                )
            result = await repository.finalize_attempt(
                lease=lease,
                recommended_product_id="product-qualified",
                payload={"summary": "qualified"},
                cited_dependency_ids=frozenset({"product-qualified", "catalog-1"}),
            )
            assert result.state == "COMPLETED"
            assert result.decision_id is not None

        async with database.transaction("org_buyer") as session:
            decision = await session.get(QualificationDecision, result.decision_id)
            assert decision is not None
            dependencies = list(
                await session.scalars(
                    select(DecisionDependency).where(
                        DecisionDependency.decision_id == result.decision_id
                    )
                )
            )
            assert any(item.cited for item in dependencies)
            repository = QualificationRepository(session, "org_buyer")
            receipt, replayed = await repository.record_consumer_receipt(
                consumer_name="worker-v1",
                message_id="message-1",
                payload_hash="sha256:" + "a" * 64,
                result_ref=result.decision_id,
            )
            assert replayed is False
            await session.flush()
            same, replayed = await repository.record_consumer_receipt(
                consumer_name="worker-v1",
                message_id="message-1",
                payload_hash="sha256:" + "a" * 64,
                result_ref=result.decision_id,
            )
            assert replayed is True
            assert same.id == receipt.id
            with pytest.raises(PersistenceConflict, match="another payload"):
                await repository.record_consumer_receipt(
                    consumer_name="worker-v1",
                    message_id="message-1",
                    payload_hash="sha256:" + "b" * 64,
                    result_ref=result.decision_id,
                )
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_repository_invalidates_stale_bundle_and_creates_one_replacement() -> None:
    database = await _database()
    bundle_v1, digest_v1 = await _seed_bundle(database, version=1)
    await _seed_mission_attempt(
        database,
        bundle_id=bundle_v1,
        bundle_digest=digest_v1,
        attempt_id="attempt-stale",
    )
    try:
        async with database.transaction("org_seller") as session:
            await QualificationRepository(session, "org_seller").activate_bundle(
                bundle_id=bundle_v1, actor_id="seller", expected_digest=digest_v1
            )
        async with database.transaction("org_buyer") as session:
            repository = QualificationRepository(session, "org_buyer")
            lease = await repository.claim_attempt(
                attempt_id="attempt-stale", lease_owner="worker", lease_seconds=300
            )
            await repository.snapshot_attempt(lease=lease)

        bundle_v2, digest_v2 = await _seed_bundle(database, version=2)
        async with database.transaction("org_seller") as session:
            activated = await QualificationRepository(session, "org_seller").activate_bundle(
                bundle_id=bundle_v2, actor_id="seller", expected_digest=digest_v2
            )
            active = await session.get(ActiveProductBundle, "product-qualified")
            assert activated.state == "ACTIVE"
            assert active is not None and active.generation == 2

        async with database.transaction("org_buyer") as session:
            repository = QualificationRepository(session, "org_buyer")
            stale = await repository.finalize_attempt(
                lease=lease,
                recommended_product_id="product-qualified",
                payload={"summary": "stale"},
                cited_dependency_ids=frozenset({"product-qualified"}),
            )
            assert stale.state == "STALE"
            assert stale.replacement_attempt_id is not None
            await session.flush()
            stale_attempt = await session.get(QualificationAttempt, "attempt-stale")
            assert stale_attempt is not None
            replacement = await repository._replacement_for(stale_attempt)
            assert replacement.id == stale.replacement_attempt_id
    finally:
        await database.close()
