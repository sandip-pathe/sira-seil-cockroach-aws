from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sira_worker.outbox_dispatcher import dispatch_batch
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from domain import content_hash
from integrations.aws_services import OutboxEnvelope, PublishedMessage
from persistence.database import Database, DatabaseSettings
from persistence.qualification_models import (
    CatalogProjectionVersion,
    MarketplaceConsent,
    MarketplaceEngagement,
    ProductBundle,
    ProductBundleMember,
    ProductTwinVersion,
    QualificationAttempt,
    QualificationDecision,
    QualificationMission,
    QualificationMissionBundle,
    QualifiedIntroduction,
)
from persistence.qualification_repository import QualificationRepository
from persistence.repositories import PersistenceConflict

pytestmark = pytest.mark.cockroach


def _runtime_url() -> str:
    value = os.environ.get("SIRA_TEST_DATABASE_URL")
    if not value:
        pytest.skip("SIRA_TEST_DATABASE_URL is required")
    return value


def _worker_url() -> str:
    value = os.environ.get("SIRA_TEST_WORKER_DATABASE_URL")
    if not value:
        pytest.skip("SIRA_TEST_WORKER_DATABASE_URL is required")
    return value


async def _ensure_organizations() -> None:
    admin = Database(DatabaseSettings(database_url=_runtime_url().replace("sira_app@", "root@")))
    try:
        async with admin.transaction("org_buyer") as session:
            await session.execute(
                text(
                    "UPSERT INTO organizations (id, name, version) VALUES "
                    "('org_buyer', 'Buyer', 1), "
                    "('org_seller_a', 'Seller A', 1), "
                    "('org_seller_b', 'Seller B', 1), "
                    "('org_other', 'Other', 1)"
                )
            )
    finally:
        await admin.close()


def _bundle_digest(*members: tuple[int, str, str, str]) -> str:
    return content_hash(
        [
            {"ordinal": ordinal, "kind": kind, "id": identifier, "hash": digest}
            for ordinal, kind, identifier, digest in members
        ]
    )


async def _seed_bundle(
    database: Database,
    *,
    organization_id: str,
    product_id: str,
    version: int,
) -> tuple[str, str]:
    twin_id = f"twin_{product_id}_{version}"
    catalog_id = f"catalog_{product_id}_{version}"
    twin_hash = content_hash({"product_id": product_id, "version": version, "kind": "twin"})
    catalog_hash = content_hash({"product_id": product_id, "version": version, "kind": "catalog"})
    members = (
        (0, "PRODUCT_TWIN", twin_id, twin_hash),
        (1, "CATALOG_PROJECTION", catalog_id, catalog_hash),
    )
    bundle_id = f"bundle_{product_id}_{version}"
    digest = _bundle_digest(*members)
    async with database.transaction(organization_id) as session:
        session.add(
            ProductTwinVersion(
                id=twin_id,
                product_id=product_id,
                version=version,
                content_hash=twin_hash,
                payload={"hosting": "EU" if version == 1 else "US"},
                published_by_actor_id="seller_publisher",
                published_at=datetime.now(UTC),
                organization_id=organization_id,
            )
        )
        session.add(
            CatalogProjectionVersion(
                id=catalog_id,
                product_id=product_id,
                version=version,
                content_hash=catalog_hash,
                buyer_safe_payload={"hosting": "EU" if version == 1 else "US"},
                organization_id=organization_id,
            )
        )
        await session.flush()
        session.add(
            ProductBundle(
                id=bundle_id,
                product_id=product_id,
                version=version,
                product_twin_version_id=twin_id,
                catalog_projection_version_id=catalog_id,
                disclosure_policy_version="disclosure-v1",
                embedding_profile="titan-v2:1024:normalize",
                digest=digest,
                state="READY",
                organization_id=organization_id,
            )
        )
        await session.flush()
        for ordinal, kind, identifier, member_hash in members:
            session.add(
                ProductBundleMember(
                    id=f"member_{product_id}_{version}_{ordinal}",
                    bundle_id=bundle_id,
                    ordinal=ordinal,
                    member_kind=kind,
                    member_id=identifier,
                    member_hash=member_hash,
                    organization_id=organization_id,
                )
            )
        await session.flush()
        await QualificationRepository(session, organization_id).activate_bundle(
            bundle_id=bundle_id,
            actor_id="seller_publisher",
            expected_digest=digest,
        )
    return bundle_id, digest


async def test_v2_activation_rejects_v1_finalization_and_creates_one_replacement() -> None:
    database = Database(DatabaseSettings(database_url=_runtime_url()))
    worker_database = Database(DatabaseSettings(database_url=_worker_url()))
    suffix = uuid4().hex[:8]
    seller_id = "org_seller_a"
    product_id = f"product_{suffix}"
    mission_id = f"mission_{suffix}"
    attempt_id = f"attempt_{suffix}"
    try:
        await _ensure_organizations()
        bundle_v1, digest_v1 = await _seed_bundle(
            database, organization_id=seller_id, product_id=product_id, version=1
        )
        async with worker_database.transaction("org_buyer") as session:
            session.add(
                QualificationMission(
                    id=mission_id,
                    buyer_context_version_id="buyer-context-v1",
                    buyer_context_hash=content_hash({"buyer": suffix}),
                    requirement_brief_version_id="brief-v1",
                    requirement_brief_hash=content_hash({"brief": "EU required"}),
                    procurement_policy_version="policy-v1",
                    procurement_policy_hash=content_hash({"region": "EU"}),
                    state="RUNNING",
                    version=1,
                    organization_id="org_buyer",
                )
            )
            await session.flush()
            session.add(
                QualificationMissionBundle(
                    id=f"mission_bundle_{suffix}",
                    mission_id=mission_id,
                    product_id=product_id,
                    seller_organization_id=seller_id,
                    bundle_id=bundle_v1,
                    bundle_digest=digest_v1,
                    organization_id="org_buyer",
                )
            )
            session.add(
                QualificationAttempt(
                    id=attempt_id,
                    mission_id=mission_id,
                    root_attempt_id=attempt_id,
                    predecessor_attempt_id=None,
                    replacement_depth=0,
                    state="QUEUED",
                    generation=0,
                    organization_id="org_buyer",
                )
            )

        async with worker_database.transaction("org_buyer") as session:
            repository = QualificationRepository(session, "org_buyer")
            lease = await repository.claim_attempt(attempt_id=attempt_id, lease_owner="worker-a")
            dependencies = await repository.snapshot_attempt(lease=lease)
            assert any(item.digest == digest_v1 for item in dependencies)

        await _seed_bundle(database, organization_id=seller_id, product_id=product_id, version=2)

        async with worker_database.transaction("org_buyer") as session:
            repository = QualificationRepository(session, "org_buyer")
            result = await repository.finalize_attempt(
                lease=lease,
                recommended_product_id=product_id,
                payload={"fit": True},
                cited_dependency_ids=frozenset({product_id}),
            )
            assert result.state == "STALE"
            assert result.replacement_attempt_id is not None

        async with database.transaction("org_buyer") as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(QualificationDecision)
                    .where(QualificationDecision.mission_id == mission_id)
                )
                == 0
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(QualificationAttempt)
                    .where(QualificationAttempt.predecessor_attempt_id == attempt_id)
                )
                == 1
            )
    finally:
        await database.close()
        await worker_database.close()


async def test_generation_fence_and_atomic_introduction_are_idempotent() -> None:
    database = Database(DatabaseSettings(database_url=_runtime_url()))
    worker_database = Database(DatabaseSettings(database_url=_worker_url()))
    suffix = uuid4().hex[:8]
    mission_id = f"mission_intro_{suffix}"
    attempt_id = f"attempt_intro_{suffix}"
    decision_id = f"decision_intro_{suffix}"
    engagement_id = f"engagement_intro_{suffix}"
    digest = content_hash({"input": suffix})
    now = datetime.now(UTC)
    try:
        await _ensure_organizations()
        async with worker_database.transaction("org_buyer") as session:
            session.add(
                QualificationMission(
                    id=mission_id,
                    buyer_context_version_id="buyer-context-v1",
                    buyer_context_hash=digest,
                    requirement_brief_version_id="brief-v1",
                    requirement_brief_hash=digest,
                    procurement_policy_version="policy-v1",
                    procurement_policy_hash=digest,
                    state="AWAITING_APPROVAL",
                    version=1,
                    organization_id="org_buyer",
                )
            )
            await session.flush()
            session.add(
                QualificationAttempt(
                    id=attempt_id,
                    mission_id=mission_id,
                    root_attempt_id=attempt_id,
                    predecessor_attempt_id=None,
                    replacement_depth=0,
                    state="RUNNING",
                    generation=0,
                    organization_id="org_buyer",
                )
            )
        async with worker_database.transaction("org_buyer") as session:
            repository = QualificationRepository(session, "org_buyer")
            old_lease = await repository.claim_attempt(
                attempt_id=attempt_id, lease_owner="worker-old", lease_seconds=1
            )
        async with worker_database.transaction("org_buyer") as session:
            attempt = await session.get(QualificationAttempt, attempt_id)
            assert attempt is not None
            attempt.lease_expires_at = now - timedelta(seconds=1)
        async with database.transaction("org_buyer") as session:
            new_lease = await QualificationRepository(session, "org_buyer").claim_attempt(
                attempt_id=attempt_id, lease_owner="worker-new"
            )
            assert new_lease.generation > old_lease.generation
        async with database.transaction("org_buyer") as session:
            with pytest.raises(PersistenceConflict, match="fence was lost"):
                await QualificationRepository(session, "org_buyer").checkpoint_attempt(
                    lease=old_lease,
                    sequence=1,
                    kind="ZOMBIE",
                    payload={},
                )

        async with database.transaction("org_buyer") as session:
            session.add(
                QualificationDecision(
                    id=decision_id,
                    mission_id=mission_id,
                    attempt_id=attempt_id,
                    input_digest=digest,
                    decision_digest=content_hash({"decision": suffix}),
                    recommended_product_id="meeting-product",
                    payload={"fit": True},
                    approval_state="APPROVED",
                    current=True,
                    organization_id="org_buyer",
                )
            )
            session.add(
                MarketplaceEngagement(
                    id=engagement_id,
                    mission_id=mission_id,
                    decision_id=decision_id,
                    buyer_organization_id="org_buyer",
                    seller_organization_id="org_seller_a",
                    product_id="meeting-product",
                    input_digest=digest,
                    state="CONSENT_PENDING",
                    expires_at=now + timedelta(hours=1),
                )
            )
            await session.flush()
            session.add_all(
                [
                    MarketplaceConsent(
                        id=f"consent_buyer_{suffix}",
                        engagement_id=engagement_id,
                        party="BUYER",
                        buyer_organization_id="org_buyer",
                        seller_organization_id="org_seller_a",
                        actor_id="human_buyer",
                        input_digest=digest,
                        approved_fields_hash="sha256:" + "a" * 64,
                        state="GRANTED",
                        expires_at=now + timedelta(hours=1),
                    ),
                    MarketplaceConsent(
                        id=f"consent_seller_{suffix}",
                        engagement_id=engagement_id,
                        party="SELLER",
                        buyer_organization_id="org_buyer",
                        seller_organization_id="org_seller_a",
                        actor_id="human_seller",
                        input_digest=digest,
                        approved_fields_hash="sha256:" + "b" * 64,
                        state="GRANTED",
                        expires_at=now + timedelta(hours=1),
                    ),
                ]
            )
        async with database.transaction("org_buyer") as session:
            repository = QualificationRepository(session, "org_buyer")
            first = await repository.introduce(
                engagement_id=engagement_id,
                decision_id=decision_id,
                input_digest=digest,
                shared_fields_hash="sha256:" + "c" * 64,
            )
        async with database.transaction("org_buyer") as session:
            second = await QualificationRepository(session, "org_buyer").introduce(
                engagement_id=engagement_id,
                decision_id=decision_id,
                input_digest=digest,
                shared_fields_hash="sha256:" + "c" * 64,
            )
            assert first.id == second.id
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(QualifiedIntroduction)
                    .where(QualifiedIntroduction.engagement_id == engagement_id)
                )
                == 1
            )
    finally:
        await database.close()
        await worker_database.close()


async def test_runtime_roles_enforce_published_and_bilateral_boundaries() -> None:
    database = Database(DatabaseSettings(database_url=_runtime_url()))
    worker_database = Database(DatabaseSettings(database_url=_worker_url()))
    suffix = uuid4().hex[:8]
    product_id = f"product_security_{suffix}"
    engagement_id = f"engagement_security_{suffix}"
    try:
        await _ensure_organizations()
        await _seed_bundle(
            database,
            organization_id="org_seller_a",
            product_id=product_id,
            version=1,
        )

        async with database.transaction("org_buyer") as session:
            assert (
                await session.scalar(
                    select(ProductBundle.id).where(ProductBundle.product_id == product_id)
                )
                is None
            )
        async with worker_database.transaction("org_buyer") as session:
            assert (
                await session.scalar(
                    select(ProductBundle.id).where(ProductBundle.product_id == product_id)
                )
                == f"bundle_{product_id}_1"
            )

        with pytest.raises(DBAPIError):
            async with database.transaction("org_seller_a") as session:
                await session.execute(
                    text(
                        "UPDATE qualification_product_twin_versions "
                        "SET payload = '{}'::JSONB WHERE product_id = :product_id"
                    ),
                    {"product_id": product_id},
                )

        async with database.transaction("org_buyer") as session:
            session.add(
                MarketplaceEngagement(
                    id=engagement_id,
                    mission_id=f"mission_security_{suffix}",
                    decision_id=f"decision_security_{suffix}",
                    buyer_organization_id="org_buyer",
                    seller_organization_id="org_seller_a",
                    product_id=product_id,
                    input_digest=content_hash({"security": suffix}),
                    state="OPEN",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
        async with database.transaction("org_seller_a") as session:
            assert await session.scalar(
                select(MarketplaceEngagement.id).where(
                    MarketplaceEngagement.id == engagement_id
                )
            ) == engagement_id
        async with database.transaction("org_other") as session:
            assert (
                await session.scalar(
                    select(MarketplaceEngagement.id).where(
                        MarketplaceEngagement.id == engagement_id
                    )
                )
                is None
            )
    finally:
        await database.close()
        await worker_database.close()


async def test_outbox_dispatch_marks_only_acknowledged_delivery() -> None:
    database = Database(DatabaseSettings(database_url=_runtime_url()))
    suffix = uuid4().hex[:8]
    organization_id = f"org_dispatch_{suffix}"

    class Publisher:
        def __init__(self) -> None:
            self.envelopes: list[OutboxEnvelope] = []

        async def publish(self, envelope: OutboxEnvelope) -> PublishedMessage:
            self.envelopes.append(envelope)
            return PublishedMessage("message-1", "1", "sha256:" + "a" * 64)

    publisher = Publisher()
    admin = Database(DatabaseSettings(database_url=_runtime_url().replace("sira_app@", "root@")))
    try:
        async with admin.transaction(organization_id) as session:
            await session.execute(
                text("INSERT INTO organizations (id, name, version) VALUES (:id, :name, 1)"),
                {"id": organization_id, "name": "Dispatch test"},
            )
        await _seed_bundle(
            database,
            organization_id=organization_id,
            product_id=f"product_dispatch_{suffix}",
            version=1,
        )

        first = await dispatch_batch(
            database,
            publisher,
            organization_id=organization_id,
        )
        second = await dispatch_batch(
            database,
            publisher,
            organization_id=organization_id,
        )

        assert first.attempted == first.published == 1
        assert second.attempted == second.published == 0
        assert len(publisher.envelopes) == 1
        assert publisher.envelopes[0].event_type == "PRODUCT_BUNDLE_ACTIVATED"
    finally:
        await database.close()
        await admin.close()
