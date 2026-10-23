"""Read and acknowledge durable work directly through CockroachDB."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select, update

from integrations.outbox import OutboxEnvelope
from persistence.database import Database
from persistence.models import OutboxEvent


async def load_unpublished(
    database: Database,
    *,
    organization_id: str,
    limit: int = 50,
    event_types: frozenset[str] | None = None,
) -> tuple[OutboxEnvelope, ...]:
    if limit < 1 or limit > 100:
        raise ValueError("outbox batch limit must be between 1 and 100")
    async with database.transaction(organization_id) as session:
        query = select(OutboxEvent).where(
            OutboxEvent.organization_id == organization_id,
            OutboxEvent.published_at.is_(None),
        )
        if event_types:
            query = query.where(OutboxEvent.event_type.in_(event_types))
        events: Sequence[OutboxEvent] = (
            await session.scalars(
                query.order_by(OutboxEvent.occurred_at, OutboxEvent.id).limit(limit)
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
