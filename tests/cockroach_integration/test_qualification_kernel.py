from __future__ import annotations

import asyncio
import json
import math
import os
import threading
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any
from uuid import uuid4

import pytest
from sira_agents.bedrock_runtime import TitanEmbeddingClient
from sira_api.errors import ApiProblem
from sira_api.qualification_service import QualificationService
from sira_worker.outbox_dispatcher import dispatch_batch
from sira_worker.qualification import QualificationWorker
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from domain import content_hash
from integrations.aws_services import OutboxEnvelope, PublishedMessage
from persistence.database import Database, DatabaseSettings
from persistence.qualification_catalog import (
    explain_published_candidate_search,
    search_published_candidates,
)
from persistence.qualification_models import (
    CatalogProjectionVersion,
    CompanyContextItem,
    CompanyContextVersion,
    DecisionDependency,
    MarketplaceConsent,
    MarketplaceEngagement,
    ProductBundle,
    ProductBundleMember,
    ProductEmbedding,
    ProductTwinVersion,
    QualificationAttempt,
    QualificationDecision,
    QualificationMission,
    QualificationMissionBundle,
    QualifiedIntroduction,
    SellerResponse,
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


def _catalog_url() -> str:
    value = os.environ.get("SIRA_TEST_CATALOG_DATABASE_URL")
    if not value:
        pytest.skip("SIRA_TEST_CATALOG_DATABASE_URL is required")
    return value


@pytest.mark.asyncio
async def test_company_context_is_versioned_tenant_private_and_pinned() -> None:
    await _ensure_organizations()
    database = Database(DatabaseSettings(database_url=_runtime_url()))
    service = QualificationService(database)
    try:
        status, created = await service.create_company_context(
            organization_id="org_buyer",
            actor_id="buyer-user",
            idempotency_key=f"context-create-{uuid4().hex}",
            body={
                "kind": "CONSTRAINT",
                "label": "EU residency",
                "payload": {"hosting_region": "EU"},
                "change_reason": "Initial context",
            },
        )
        assert status == 201
        item_id = str(created["resource_id"])
        view = await service.company_context_view("org_buyer", item_id)
        etag = str(view["item"]["etag"])
        old_hash = str(view["item"]["current_hash"])

        status, revised = await service.update_company_context(
            organization_id="org_buyer",
            actor_id="buyer-user",
            item_id=item_id,
            if_match=etag,
            idempotency_key=f"context-update-{uuid4().hex}",
            body={
                "label": "EU customer-data residency",
                "payload": {"hosting_region": "EU", "scope": "customer_data"},
                "change_reason": "Clarified scope",
            },
        )
        assert status == 200
        assert revised["input_digest"] != old_hash

        history = await service.company_context_view("org_buyer", item_id)
        assert [value["version"] for value in history["versions"]] == [2, 1]
        assert history["versions"][1]["content_hash"] == old_hash

        mission_status, mission = await service.create_mission(
            organization_id="org_buyer",
            actor_id="buyer-user",
            idempotency_key=f"context-mission-{uuid4().hex}",
            trace_id=f"trace-{uuid4().hex}",
            body={
                "buyer_context": {"company": "Buyer"},
                "company_context_item_ids": [item_id],
                "requirement_brief": {
                    "category": "meeting intelligence",
                    "goal": "Select a compliant meeting intelligence platform.",
                    "seller_visible_requirements": {"hosting_region": "EU"},
                    "criteria": [
                        {
                            "id": "residency",
                            "label": "EU residency",
                            "requirement": "Customer data remains in the EU.",
                            "priority": "MUST",
                        }
                    ],
                },
                "procurement_policy": {"human_approval": True},
            },
        )
        assert mission_status == 201
        projection = await service.mission_view("org_buyer", str(mission["resource_id"]))
        pinned = projection["mission"]["buyer_context"]["company_memory"][0]
        assert pinned["version"] == 2
        assert pinned["content_hash"] == revised["input_digest"]

        async with database.transaction("org_other") as session:
            assert (
                await session.scalar(
                    select(CompanyContextItem).where(CompanyContextItem.id == item_id)
                )
            ) is None
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(CompanyContextVersion)
                    .where(CompanyContextVersion.item_id == item_id)
                )
            ) == 0
    finally:
        await database.close()


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
                    buyer_context_payload={"buyer": suffix},
                    requirement_brief_version_id="brief-v1",
                    requirement_brief_hash=content_hash({"brief": "EU required"}),
                    requirement_brief_payload={"brief": "EU required"},
                    procurement_policy_version="policy-v1",
                    procurement_policy_hash=content_hash({"region": "EU"}),
                    procurement_policy_payload={"region": "EU"},
                    trace_id=f"trace_{suffix}",
                    state="RUNNING",
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
                    state="QUEUED",
                    generation=0,
                    organization_id="org_buyer",
                )
            )
            await session.flush()
            session.add(
                QualificationMissionBundle(
                    id=f"mission_bundle_{suffix}",
                    mission_id=mission_id,
                    attempt_id=attempt_id,
                    product_id=product_id,
                    seller_organization_id=seller_id,
                    bundle_id=bundle_v1,
                    bundle_digest=digest_v1,
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
                    buyer_context_payload={"buyer": suffix},
                    requirement_brief_version_id="brief-v1",
                    requirement_brief_hash=digest,
                    requirement_brief_payload={"brief": suffix},
                    procurement_policy_version="policy-v1",
                    procurement_policy_hash=digest,
                    procurement_policy_payload={"policy": suffix},
                    trace_id=f"trace_intro_{suffix}",
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
                    buyer_safe_requirement={"category": "meeting intelligence"},
                    buyer_safe_hash=content_hash({"category": "meeting intelligence"}),
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
                        approved_fields_hash=content_hash({"email": "buyer@example.test"}),
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
                        approved_fields_hash=content_hash({"email": "buyer@example.test"}),
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
                shared_fields={"email": "buyer@example.test"},
            )
        async with database.transaction("org_buyer") as session:
            second = await QualificationRepository(session, "org_buyer").introduce(
                engagement_id=engagement_id,
                decision_id=decision_id,
                input_digest=digest,
                shared_fields={"email": "buyer@example.test"},
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
                    buyer_safe_requirement={"category": "meeting intelligence"},
                    buyer_safe_hash=content_hash({"category": "meeting intelligence"}),
                    state="OPEN",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
        async with database.transaction("org_seller_a") as session:
            assert (
                await session.scalar(
                    select(MarketplaceEngagement.id).where(
                        MarketplaceEngagement.id == engagement_id
                    )
                )
                == engagement_id
            )
            session.add(
                SellerResponse(
                    id=f"response_security_{suffix}",
                    engagement_id=engagement_id,
                    buyer_organization_id="org_buyer",
                    seller_organization_id="org_seller_a",
                    input_digest=content_hash({"security": suffix}),
                    response="FIT",
                    cited_evidence_ids=[],
                    message="The published evidence is current.",
                    actor_id="human_seller",
                    organization_id="org_seller_a",
                )
            )
        async with database.transaction("org_buyer") as session:
            assert (
                await session.scalar(
                    select(SellerResponse.id).where(SellerResponse.engagement_id == engagement_id)
                )
                == f"response_security_{suffix}"
            )
        with pytest.raises(DBAPIError):
            async with database.transaction("org_buyer") as session:
                session.add(
                    SellerResponse(
                        id=f"forged_response_{suffix}",
                        engagement_id=engagement_id,
                        buyer_organization_id="org_buyer",
                        seller_organization_id="org_seller_a",
                        input_digest=content_hash({"security": suffix}),
                        response="FIT",
                        cited_evidence_ids=[],
                        message=None,
                        actor_id="human_buyer",
                        organization_id="org_seller_a",
                    )
                )
        async with database.transaction("org_other") as session:
            assert (
                await session.scalar(
                    select(MarketplaceEngagement.id).where(
                        MarketplaceEngagement.id == engagement_id
                    )
                )
                is None
            )
            assert (
                await session.scalar(
                    select(SellerResponse.id).where(SellerResponse.engagement_id == engagement_id)
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


async def test_qualification_service_completes_bilateral_introduction() -> None:
    database = Database(DatabaseSettings(database_url=_runtime_url()))
    service = QualificationService(database)
    suffix = uuid4().hex[:8]
    product_id = f"product_lifecycle_{suffix}"
    input_digest = content_hash({"attempt": suffix})
    shared_fields = {
        "buyer_email": "buyer@example.test",
        "seller_email": "seller@example.test",
    }
    try:
        await _ensure_organizations()
        bundle_id, bundle_digest = await _seed_bundle(
            database,
            organization_id="org_seller_a",
            product_id=product_id,
            version=1,
        )
        create_status, created = await service.create_mission(
            organization_id="org_buyer",
            actor_id="human_buyer",
            idempotency_key=f"create-{suffix}",
            trace_id=f"trace_{suffix}",
            body={
                "buyer_context": {"company": "Buyer", "budget": "25000"},
                "requirement_brief": {
                    "category": f"lifecycle-{suffix}",
                    "goal": "Select a qualified meeting intelligence product.",
                    "seller_visible_requirements": {"hosting_region": "EU"},
                    "criteria": [
                        {
                            "id": "hosting",
                            "label": "EU hosting",
                            "requirement": "Customer data remains in the EU.",
                            "priority": "MUST",
                        }
                    ],
                },
                "procurement_policy": {"human_approval": True},
            },
        )
        assert create_status == 201
        mission_id = str(created["resource_id"])
        attempt_id = f"attempt_lifecycle_{suffix}"
        decision_id = f"decision_lifecycle_{suffix}"
        decision_payload = {
            "recommended_product_id": product_id,
            "summary": "The current Product Bundle satisfies the requirement.",
            "cited_dependency_ids": [product_id],
            "criteria": [{"criterion": "hosting", "result": "PASS"}],
            "confidence": "0.91",
        }
        decision_digest = content_hash(
            {
                "attempt_id": attempt_id,
                "input_digest": input_digest,
                "recommended_product_id": product_id,
                "payload": decision_payload,
            }
        )
        async with database.transaction("org_buyer") as session:
            mission = await session.get(QualificationMission, mission_id)
            assert mission is not None
            mission.state = "AWAITING_APPROVAL"
            session.add(
                QualificationAttempt(
                    id=attempt_id,
                    mission_id=mission_id,
                    root_attempt_id=attempt_id,
                    predecessor_attempt_id=None,
                    replacement_depth=0,
                    state="COMPLETED",
                    generation=1,
                    input_digest=input_digest,
                    organization_id="org_buyer",
                )
            )
            await session.flush()
            session.add(
                QualificationMissionBundle(
                    id=f"mission_bundle_{suffix}",
                    mission_id=mission_id,
                    attempt_id=attempt_id,
                    product_id=product_id,
                    seller_organization_id="org_seller_a",
                    bundle_id=bundle_id,
                    bundle_digest=bundle_digest,
                    organization_id="org_buyer",
                )
            )
            session.add(
                QualificationDecision(
                    id=decision_id,
                    mission_id=mission_id,
                    attempt_id=attempt_id,
                    input_digest=input_digest,
                    decision_digest=decision_digest,
                    recommended_product_id=product_id,
                    payload=decision_payload,
                    approval_state="PENDING",
                    current=True,
                    organization_id="org_buyer",
                )
            )
            await session.flush()
            session.add(
                DecisionDependency(
                    id=f"decision_dependency_{suffix}",
                    decision_id=decision_id,
                    dependency_kind="PRODUCT_BUNDLE",
                    dependency_organization_id="org_seller_a",
                    dependency_id=product_id,
                    dependency_version=bundle_id,
                    dependency_hash=bundle_digest,
                    cited=True,
                    organization_id="org_buyer",
                )
            )

        with pytest.raises(ApiProblem, match="PRECONDITION_FAILED"):
            await service.decide_approval(
                organization_id="org_buyer",
                actor_id="human_buyer",
                decision_id=decision_id,
                if_match='"sha256:wrong"',
                idempotency_key=f"wrong-etag-{suffix}",
                action="APPROVE",
                reason="This client has a stale decision view.",
            )

        approve_status, approved = await service.decide_approval(
            organization_id="org_buyer",
            actor_id="human_buyer",
            decision_id=decision_id,
            if_match=f'"{decision_digest}"',
            idempotency_key=f"approve-{suffix}",
            action="APPROVE",
            reason="The evidence and policy checks are acceptable.",
        )
        assert approve_status == 200
        engagement_id = str(approved["resource_id"])
        seller_view = await service.engagement_view("org_seller_a", engagement_id)
        assert seller_view["engagement"]["buyer_safe_requirement"] == {"hosting_region": "EU"}
        assert "buyer_context" not in seller_view["engagement"]

        response_status, seller_response = await service.respond(
            organization_id="org_seller_a",
            actor_id="human_seller",
            engagement_id=engagement_id,
            if_match=f'"{input_digest}"',
            idempotency_key=f"respond-{suffix}",
            body={"response": "FIT", "cited_evidence_ids": [], "message": "We fit."},
        )
        assert response_status == 201
        assert seller_response["state"] == "FIT"

        for party, organization_id, actor_id in (
            ("BUYER", "org_buyer", "human_buyer"),
            ("SELLER", "org_seller_a", "human_seller"),
        ):
            consent_status, consent = await service.consent(
                organization_id=organization_id,
                actor_id=actor_id,
                party=party,
                engagement_id=engagement_id,
                if_match=f'"{input_digest}"',
                idempotency_key=f"consent-{party.lower()}-{suffix}",
                shared_fields=shared_fields,
            )
            assert consent_status == 201
            assert consent["state"] == "GRANTED"

        introduction_status, introduction = await service.introduce(
            organization_id="org_buyer",
            actor_id="human_buyer",
            engagement_id=engagement_id,
            if_match=f'"{input_digest}"',
            idempotency_key=f"introduce-{suffix}",
            shared_fields=shared_fields,
        )
        assert introduction_status == 201
        assert introduction["state"] == "INTRODUCED"
        final_view = await service.engagement_view("org_seller_a", engagement_id)
        assert final_view["introduction"]["receipt"]["shared_fields"] == shared_fields
        integrity = await service.integrity("org_buyer", mission_id)
        assert integrity["verdict"] == "PASS"
        assert {item["status"] for item in integrity["checks"]} == {"PASS"}
    finally:
        await database.close()


async def test_dvi_retrieves_current_published_candidates_across_sellers() -> None:
    database = Database(DatabaseSettings(database_url=_runtime_url()))
    catalog_database = Database(DatabaseSettings(database_url=_catalog_url()))
    admin = Database(DatabaseSettings(database_url=_runtime_url().replace("sira_app@", "root@")))
    suffix = uuid4().hex[:8]
    category = f"meeting-{suffix}"
    query_vector = (1.0,) + (0.0,) * 1023
    try:
        await _ensure_organizations()
        for index in range(20):
            organization_id = "org_seller_a" if index % 2 == 0 else "org_seller_b"
            product_id = f"product_{index:02d}_{suffix}"
            angle = index * 0.03
            vector = (math.cos(angle), math.sin(angle)) + (0.0,) * 1022
            bundle_id, _digest = await _seed_bundle(
                database,
                organization_id=organization_id,
                product_id=product_id,
                version=1,
            )
            vector_literal = "[" + ",".join(str(value) for value in vector) + "]"
            async with database.transaction(organization_id) as session:
                session.add(
                    ProductEmbedding(
                        id=f"embedding_{product_id}",
                        bundle_id=bundle_id,
                        product_id=product_id,
                        category=category,
                        visibility="BUYER_SAFE",
                        content_hash=content_hash({"product_id": product_id}),
                        model_id="amazon.titan-embed-text-v2:0",
                        dimensions=1024,
                        embedding=vector_literal,
                        organization_id=organization_id,
                    )
                )

        async with admin.transaction("org_buyer") as session:
            await session.execute(text("ANALYZE qualification_product_embeddings"))

        async with catalog_database.transaction("org_buyer") as session:
            candidates = await search_published_candidates(
                session,
                category=category,
                visibility="BUYER_SAFE",
                query_vector=query_vector,
                limit=5,
            )
            plan = await explain_published_candidate_search(
                session,
                category=category,
                visibility="BUYER_SAFE",
                query_vector=query_vector,
                limit=5,
            )
        assert len(candidates) == 5
        assert candidates[0].organization_id == "org_seller_a"
        assert candidates[0].product_id == f"product_00_{suffix}"
        assert any(candidate.organization_id == "org_seller_b" for candidate in candidates)
        assert candidates[0].cosine_distance == pytest.approx(0.0)
        assert "qualification_product_embedding_dvi" in "\n".join(plan)

        with pytest.raises(DBAPIError):
            async with catalog_database.transaction("org_buyer") as session:
                await session.execute(text("SELECT id FROM qualification_missions LIMIT 1"))
        with pytest.raises(DBAPIError):
            async with catalog_database.transaction("org_buyer") as session:
                await session.execute(
                    text(
                        "INSERT INTO qualification_product_embeddings "
                        "SELECT * FROM qualification_product_embeddings LIMIT 0"
                    )
                )

        async with database.transaction("org_buyer") as session:
            assert (
                await search_published_candidates(
                    session,
                    category=category,
                    visibility="BUYER_SAFE",
                    query_vector=query_vector,
                    limit=5,
                )
                == ()
            )
    finally:
        await database.close()
        await catalog_database.close()
        await admin.close()


async def test_worker_replaces_stale_attempt_and_completes_against_v2() -> None:
    database = Database(DatabaseSettings(database_url=_runtime_url()))
    worker_database = Database(DatabaseSettings(database_url=_worker_url()))
    catalog_database = Database(DatabaseSettings(database_url=_catalog_url()))
    suffix = uuid4().hex[:8]
    category = f"worker-{suffix}"
    product_id = f"product_target_{suffix}"
    mission_id = f"mission_worker_{suffix}"
    query_vector = (1.0,) + (0.0,) * 1023
    first_model_call = threading.Event()
    resume_model = threading.Event()

    class AdaptiveBedrock:
        def __init__(self) -> None:
            self.converse_count = 0

        def invoke_model(self, **_kwargs: Any) -> dict[str, Any]:
            return {
                "body": BytesIO(
                    json.dumps(
                        {
                            "embedding": list(query_vector),
                            "inputTextTokenCount": 5,
                        }
                    ).encode()
                )
            }

        def converse(self, **kwargs: Any) -> dict[str, Any]:
            self.converse_count += 1
            messages = kwargs["messages"]
            last_content = messages[-1]["content"]
            if any("toolResult" in block for block in last_content):
                tool_results = [block["toolResult"] for block in last_content]
                evidence = [result["content"][0]["json"] for result in tool_results]
                selected = next(item for item in evidence if item["product_id"] == product_id)
                citations = [selected["product_id"]]
                if selected["catalog"]:
                    citations.append(selected["catalog"][0]["dependency_id"])
                output = {
                    "recommended_product_id": product_id,
                    "summary": "Current evidence satisfies the requirement.",
                    "cited_dependency_ids": citations,
                    "criteria": [{"criterion": "hosting", "result": "PASS"}],
                    "confidence": 0.91,
                }
                return {
                    "stopReason": "end_turn",
                    "output": {
                        "message": {
                            "role": "assistant",
                            "content": [{"text": json.dumps(output)}],
                        }
                    },
                    "usage": {"inputTokens": 50, "outputTokens": 20, "totalTokens": 70},
                }

            request = json.loads(messages[0]["content"][0]["text"])
            candidate_ids = request["context"]["candidate_product_ids"]
            if self.converse_count == 1:
                first_model_call.set()
                assert resume_model.wait(timeout=10)
            return {
                "stopReason": "tool_use",
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "toolUse": {
                                    "toolUseId": f"tool-{index}",
                                    "name": "retrieve_product_evidence",
                                    "input": {"product_id": candidate_id},
                                }
                            }
                            for index, candidate_id in enumerate(candidate_ids)
                        ],
                    }
                },
                "usage": {"inputTokens": 30, "outputTokens": 10, "totalTokens": 40},
            }

    async def add_embedding(
        organization_id: str,
        current_product_id: str,
        bundle_id: str,
        version: int,
        vector: tuple[float, ...],
    ) -> None:
        vector_literal = "[" + ",".join(str(value) for value in vector) + "]"
        async with database.transaction(organization_id) as session:
            session.add(
                ProductEmbedding(
                    id=f"embedding_{current_product_id}_{version}",
                    bundle_id=bundle_id,
                    product_id=current_product_id,
                    category=category,
                    visibility="BUYER_SAFE",
                    content_hash=content_hash(
                        {"product_id": current_product_id, "version": version}
                    ),
                    model_id="amazon.titan-embed-text-v2:0",
                    dimensions=1024,
                    embedding=vector_literal,
                    organization_id=organization_id,
                )
            )

    bedrock = AdaptiveBedrock()
    try:
        await _ensure_organizations()
        bundle_v1, _digest_v1 = await _seed_bundle(
            database,
            organization_id="org_seller_a",
            product_id=product_id,
            version=1,
        )
        await add_embedding("org_seller_a", product_id, bundle_v1, 1, query_vector)
        for index in range(1, 20):
            other_product = f"product_other_{index:02d}_{suffix}"
            organization_id = "org_seller_a" if index % 2 == 0 else "org_seller_b"
            angle = 0.2 + index * 0.02
            vector = (math.cos(angle), math.sin(angle)) + (0.0,) * 1022
            bundle_id, _digest = await _seed_bundle(
                database,
                organization_id=organization_id,
                product_id=other_product,
                version=1,
            )
            await add_embedding(organization_id, other_product, bundle_id, 1, vector)

        async with database.transaction("org_buyer") as session:
            session.add(
                QualificationMission(
                    id=mission_id,
                    buyer_context_version_id=f"context_{suffix}",
                    buyer_context_hash=content_hash({"company": "Buyer"}),
                    buyer_context_payload={"company": "Buyer"},
                    requirement_brief_version_id=f"brief_{suffix}",
                    requirement_brief_hash=content_hash({"category": category}),
                    requirement_brief_payload={
                        "category": category,
                        "goal": "Choose EU-hosted meeting intelligence",
                        "seller_visible_requirements": {"hosting_region": "EU"},
                    },
                    procurement_policy_version="policy-v1",
                    procurement_policy_hash=content_hash({"human_approval": True}),
                    procurement_policy_payload={"human_approval": True},
                    trace_id=f"trace_worker_{suffix}",
                    state="READY",
                    version=1,
                    organization_id="org_buyer",
                )
            )

        worker = QualificationWorker(
            worker_database=worker_database,
            catalog_database=catalog_database,
            embedding_client=TitanEmbeddingClient(client=bedrock),
            bedrock_client=bedrock,
            model_id="amazon.nova-micro-v1:0",
            lease_owner="worker-test",
        )
        run_task = asyncio.create_task(
            worker.run_mission(organization_id="org_buyer", mission_id=mission_id)
        )
        assert await asyncio.to_thread(first_model_call.wait, 10)
        bundle_v2, _digest_v2 = await _seed_bundle(
            database,
            organization_id="org_seller_a",
            product_id=product_id,
            version=2,
        )
        await add_embedding("org_seller_a", product_id, bundle_v2, 2, query_vector)
        resume_model.set()
        result = await run_task

        assert result.state == "COMPLETED"
        assert result.decision_id is not None
        assert len(result.attempts) == 2
        async with database.transaction("org_buyer") as session:
            attempts = (
                await session.scalars(
                    select(QualificationAttempt)
                    .where(QualificationAttempt.mission_id == mission_id)
                    .order_by(QualificationAttempt.replacement_depth)
                )
            ).all()
            assert [attempt.state for attempt in attempts] == ["STALE", "COMPLETED"]
            bundles = (
                await session.scalars(
                    select(QualificationMissionBundle)
                    .where(
                        QualificationMissionBundle.mission_id == mission_id,
                        QualificationMissionBundle.product_id == product_id,
                    )
                    .order_by(QualificationMissionBundle.attempt_id)
                )
            ).all()
            assert {bundle.bundle_id for bundle in bundles} == {bundle_v1, bundle_v2}
    finally:
        resume_model.set()
        await database.close()
        await worker_database.close()
        await catalog_database.close()
