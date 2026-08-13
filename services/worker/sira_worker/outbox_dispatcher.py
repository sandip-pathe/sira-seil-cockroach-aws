"""CockroachDB outbox to queue dispatcher with at-least-once delivery."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select, update

from integrations.aws_services import OutboxEnvelope, PublishedMessage
from persistence.database import Database
from persistence.models import OutboxEvent


class OutboxPublisher(Protocol):
    async def publish(self, envelope: OutboxEnvelope) -> PublishedMessage: ...


@dataclass(frozen=True, slots=True)
class DispatchResult:
    attempted: int
    published: int
    event_ids: tuple[str, ...]


async def load_unpublished(
    database: Database, *, organization_id: str, limit: int = 50
) -> tuple[OutboxEnvelope, ...]:
    if limit < 1 or limit > 100:
        raise ValueError("outbox batch limit must be between 1 and 100")
    async with database.transaction(organization_id) as session:
        events: Sequence[OutboxEvent] = (
            await session.scalars(
                select(OutboxEvent)
                .where(
                    OutboxEvent.organization_id == organization_id,
                    OutboxEvent.published_at.is_(None),
                )
                .order_by(OutboxEvent.occurred_at, OutboxEvent.id)
                .limit(limit)
            )
        ).all()
        return tuple(
            OutboxEnvelope(
                id=event.id,
                organization_id=str(event.organization_id),
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                event_type=event.event_type,
                event_key=event.event_key,
                payload=event.payload,
                occurred_at=event.occurred_at.astimezone(UTC).isoformat(),
            )
            for event in events
        )


async def mark_published(
    database: Database, *, envelope: OutboxEnvelope, published_at: datetime
) -> bool:
    """CAS the snapshot after queue delivery; concurrent duplicate sends are harmless."""

    async with database.transaction(envelope.organization_id) as session:
        marked_id = await session.scalar(
            update(OutboxEvent)
            .where(
                OutboxEvent.organization_id == envelope.organization_id,
                OutboxEvent.id == envelope.id,
                OutboxEvent.event_key == envelope.event_key,
                OutboxEvent.published_at.is_(None),
            )
            .values(published_at=published_at)
            .returning(OutboxEvent.id)
        )
        return marked_id is not None


async def dispatch_batch(
    database: Database,
    publisher: OutboxPublisher,
    *,
    organization_id: str,
    limit: int = 50,
) -> DispatchResult:
    """Keep queue I/O outside SQL transactions and mark only acknowledged sends."""

    envelopes = await load_unpublished(database, organization_id=organization_id, limit=limit)
    published: list[str] = []
    for envelope in envelopes:
        await publisher.publish(envelope)
        if await mark_published(
            database,
            envelope=envelope,
            published_at=datetime.now(UTC),
        ):
            published.append(envelope.id)
    return DispatchResult(len(envelopes), len(published), tuple(published))
