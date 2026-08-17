from __future__ import annotations

from datetime import UTC, datetime, timedelta

from persistence.database import Database, DatabaseSettings
from persistence.models import Base, Organization
from persistence.runtime_ticket_replay import CockroachReplayGuard


async def test_runtime_ticket_replay_is_durable_and_tenant_scoped() -> None:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    for organization_id in ("org-a", "org-b"):
        async with database.transaction(organization_id) as session:
            session.add(Organization(id=organization_id, name=organization_id))
    expires_at = datetime.now(UTC) + timedelta(minutes=2)
    try:
        first = CockroachReplayGuard(database, "org-a")
        second_tenant = CockroachReplayGuard(database, "org-b")
        assert await first.consume("ticket-1", "nonce-1", expires_at) is True
        assert await first.consume("ticket-1", "nonce-1", expires_at) is False
        assert await second_tenant.consume("ticket-1", "nonce-1", expires_at) is True
    finally:
        await database.close()
