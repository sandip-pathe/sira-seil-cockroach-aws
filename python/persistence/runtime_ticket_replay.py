"""CockroachDB replay guard for short-lived AgentCore runtime tickets."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.database import Database
from persistence.models import RuntimeTicketUse
from persistence.repositories import new_id


class CockroachReplayGuard:
    def __init__(self, database: Database, organization_id: str) -> None:
        self.database = database
        self.organization_id = organization_id

    async def consume(self, ticket_id: str, nonce: str, expires_at: datetime) -> bool:
        nonce_hash = f"sha256:{sha256(nonce.encode()).hexdigest()}"

        async def work(session: AsyncSession) -> bool:
            existing = await session.scalar(
                select(RuntimeTicketUse.id).where(
                    RuntimeTicketUse.organization_id == self.organization_id,
                    RuntimeTicketUse.ticket_id == ticket_id,
                    RuntimeTicketUse.nonce_hash == nonce_hash,
                )
            )
            if existing is not None:
                return False
            session.add(
                RuntimeTicketUse(
                    id=new_id("rtuse"),
                    organization_id=self.organization_id,
                    ticket_id=ticket_id,
                    nonce_hash=nonce_hash,
                    expires_at=expires_at,
                )
            )
            await session.flush()
            return True

        return await self.database.run_retryable(self.organization_id, work)
