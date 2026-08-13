from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from sira_worker.outbox_dispatcher import dispatch_batch, load_unpublished

from integrations.aws_services import OutboxEnvelope, PublishedMessage
from persistence.database import Database, DatabaseSettings
from persistence.models import Base, OutboxEvent


@dataclass
class Publisher:
    envelopes: list[OutboxEnvelope] = field(default_factory=list)
    fail: bool = False

    async def publish(self, envelope: OutboxEnvelope) -> PublishedMessage:
        self.envelopes.append(envelope)
        if self.fail:
            raise RuntimeError("queue unavailable")
        return PublishedMessage("message-1", "1", "sha256:" + "a" * 64)


async def _database() -> Database:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.transaction("org_dispatch") as session:
        session.add_all(
            [
                OutboxEvent(
                    id="outbox-ready",
                    aggregate_type="QUALIFICATION_MISSION",
                    aggregate_id="qmission_0123456789abcdef0123456789abcdef",
                    event_type="QUALIFICATION_MISSION_READY",
                    event_key="qualification-mission-ready:mission-1",
                    payload={"mission_id": "mission-1"},
                    organization_id="org_dispatch",
                ),
                OutboxEvent(
                    id="outbox-unrelated",
                    aggregate_type="PRODUCT_BUNDLE",
                    aggregate_id="bundle-1",
                    event_type="PRODUCT_BUNDLE_ACTIVATED",
                    event_key="product-bundle-activated:bundle-1",
                    payload={"bundle_id": "bundle-1"},
                    organization_id="org_dispatch",
                ),
            ]
        )
    return database


@pytest.mark.asyncio
async def test_dispatch_filters_marks_and_does_not_redeliver() -> None:
    database = await _database()
    publisher = Publisher()
    try:
        first = await dispatch_batch(
            database,
            publisher,
            organization_id="org_dispatch",
            event_types=frozenset({"QUALIFICATION_MISSION_READY"}),
        )
        second = await dispatch_batch(
            database,
            publisher,
            organization_id="org_dispatch",
            event_types=frozenset({"QUALIFICATION_MISSION_READY"}),
        )
        remaining = await load_unpublished(database, organization_id="org_dispatch")

        assert first.attempted == first.published == 1
        assert first.event_ids == ("outbox-ready",)
        assert second.attempted == second.published == 0
        assert [item.id for item in remaining] == ["outbox-unrelated"]
        assert publisher.envelopes[0].organization_id == "org_dispatch"
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_queue_failure_keeps_outbox_event_unpublished() -> None:
    database = await _database()
    publisher = Publisher(fail=True)
    try:
        with pytest.raises(RuntimeError, match="queue unavailable"):
            await dispatch_batch(
                database,
                publisher,
                organization_id="org_dispatch",
                event_types=frozenset({"QUALIFICATION_MISSION_READY"}),
            )
        remaining = await load_unpublished(
            database,
            organization_id="org_dispatch",
            event_types=frozenset({"QUALIFICATION_MISSION_READY"}),
        )
        assert [item.id for item in remaining] == ["outbox-ready"]
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_outbox_batch_limit_is_bounded() -> None:
    database = await _database()
    try:
        with pytest.raises(ValueError, match="between 1 and 100"):
            await load_unpublished(database, organization_id="org_dispatch", limit=0)
        with pytest.raises(ValueError, match="between 1 and 100"):
            await load_unpublished(database, organization_id="org_dispatch", limit=101)
    finally:
        await database.close()
