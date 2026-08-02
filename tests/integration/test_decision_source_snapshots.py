from __future__ import annotations

from datetime import UTC, datetime

import pytest

from decision_engine import load_demo_decision_source
from domain import content_hash
from persistence.database import Database, DatabaseSettings
from persistence.models import (
    Base,
    DecisionSourceSnapshot,
    Organization,
    PurchaseBriefVersion,
    PurchaseRequest,
    StackSnapshot,
)
from persistence.repositories import PersistenceConflict, RecordNotFound, WorkflowRepository


async def _database() -> Database:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return database


@pytest.mark.asyncio
async def test_decision_source_is_hash_bound_and_tenant_scoped() -> None:
    database = await _database()
    try:
        payload = load_demo_decision_source().to_payload()
        source_hash = content_hash(payload)
        now = datetime(2026, 8, 2, tzinfo=UTC)
        async with database.transaction("org_consultco") as session:
            session.add(Organization(id="org_consultco", name="ConsultCo", version=1))
            request = PurchaseRequest(
                id="req_source",
                organization_id="org_consultco",
                intent="Find meeting intelligence",
                status="DRAFT",
                visibility="PRIVATE",
                version=1,
                payload={"intent": "Find meeting intelligence"},
                request_hash=content_hash({"request": "source"}),
            )
            brief = PurchaseBriefVersion(
                id="pb_source",
                organization_id="org_consultco",
                purchase_request_id=request.id,
                version=1,
                status="APPROVED",
                payload=payload["purchase_brief"],
                content_hash=content_hash(payload["purchase_brief"]),
                supersedes_id=None,
            )
            stack = StackSnapshot(
                id="stack_source",
                organization_id="org_consultco",
                version=1,
                manifest={"schema_version": "1.0.0"},
                lock=payload["stack_lock"],
                lock_hash=content_hash(payload["stack_lock"]),
            )
            session.add_all((request, brief, stack))
            await session.flush()
            repository = WorkflowRepository(session, "org_consultco")
            await repository.add_decision_source_snapshot(
                DecisionSourceSnapshot(
                    id="dss_source_v1",
                    organization_id="org_consultco",
                    purchase_request_id=request.id,
                    purchase_brief_id=brief.id,
                    stack_snapshot_id=stack.id,
                    version=1,
                    source_kind="MANUAL_VERIFIED",
                    payload=payload,
                    content_hash=source_hash,
                    accepted_by_actor_id="usr_policy_owner",
                    accepted_at=now,
                )
            )

        async with database.transaction("org_consultco") as session:
            restored = await WorkflowRepository(
                session, "org_consultco"
            ).get_decision_source_snapshot("req_source", purchase_brief_id="pb_source")
            assert restored.content_hash == source_hash
            assert restored.payload == payload

        async with database.transaction("org_other") as session:
            with pytest.raises(RecordNotFound):
                await WorkflowRepository(session, "org_other").get_decision_source_snapshot(
                    "req_source"
                )
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_decision_source_rejects_a_mismatched_payload_hash() -> None:
    database = await _database()
    try:
        payload = load_demo_decision_source().to_payload()
        async with database.transaction("org_consultco") as session:
            session.add(Organization(id="org_consultco", name="ConsultCo", version=1))
            repository = WorkflowRepository(session, "org_consultco")
            with pytest.raises(PersistenceConflict, match="hash does not match"):
                await repository.add_decision_source_snapshot(
                    DecisionSourceSnapshot(
                        id="dss_bad",
                        organization_id="org_consultco",
                        purchase_request_id="req_missing",
                        purchase_brief_id="pb_missing",
                        stack_snapshot_id="stack_missing",
                        version=1,
                        source_kind="MANUAL_VERIFIED",
                        payload=payload,
                        content_hash="sha256:" + "0" * 64,
                        accepted_by_actor_id="usr_policy_owner",
                        accepted_at=datetime(2026, 8, 2, tzinfo=UTC),
                    )
                )
    finally:
        await database.close()
