from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.database import Database, DatabaseSettings
from persistence.models import PurchaseRequest

pytestmark = pytest.mark.cockroach


def _runtime_url() -> str:
    value = os.environ.get("SIRA_TEST_DATABASE_URL")
    if not value:
        pytest.skip("SIRA_TEST_DATABASE_URL is required")
    return value


async def test_runtime_is_ready_and_rls_denies_cross_tenant_rows() -> None:
    database = Database(DatabaseSettings(database_url=_runtime_url()))
    admin = Database(DatabaseSettings(database_url=_runtime_url().replace("sira_app@", "root@")))
    suffix = uuid4().hex
    record_id = f"pr_{suffix}"
    try:
        async with admin.transaction("org_a") as session:
            await session.execute(
                text(
                    "UPSERT INTO organizations (id, name, version) "
                    "VALUES ('org_a', 'Tenant A', 1), ('org_b', 'Tenant B', 1)"
                )
            )
        assert await database.is_ready()
        async with database.transaction("org_a") as session:
            session.add(
                PurchaseRequest(
                    id=record_id,
                    intent="meeting intelligence",
                    status="OPEN",
                    visibility="PRIVATE",
                    version=1,
                    payload={},
                    request_hash=f"hash_{suffix}",
                    organization_id="org_a",
                )
            )
        async with database.transaction("org_a") as session:
            connection_a = int(await session.scalar(text("SELECT pg_backend_pid()")) or 0)
            assert (
                await session.scalar(
                    select(PurchaseRequest.id).where(PurchaseRequest.id == record_id)
                )
                == record_id
            )
            assert (
                await session.execute(text("SELECT id FROM organizations"))
            ).scalars().all() == ["org_a"]
        async with database.transaction("org_b") as session:
            connection_b = int(await session.scalar(text("SELECT pg_backend_pid()")) or 0)
            assert (
                await session.scalar(
                    select(PurchaseRequest.id).where(PurchaseRequest.id == record_id)
                )
                is None
            )
            assert (
                await session.execute(text("SELECT id FROM organizations"))
            ).scalars().all() == ["org_b"]
        assert connection_a == connection_b

        async with database.sessions() as session, session.begin():
            assert (
                await session.scalar(
                    select(PurchaseRequest.id).where(PurchaseRequest.id == record_id)
                )
                is None
            )
    finally:
        await database.close()
        await admin.close()


async def test_real_40001_is_replayed_with_a_fresh_transaction() -> None:
    database = Database(DatabaseSettings(database_url=_runtime_url()))
    attempts = 0

    async def work(session: AsyncSession) -> int:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            await session.execute(text("SELECT crdb_internal.force_retry('100ms'::INTERVAL)"))
        return int(await session.scalar(text("SELECT 7")) or 0)

    try:
        assert await database.run_retryable("org_a", work, base_delay_seconds=0) == 7
    except DBAPIError as error:
        pytest.fail(f"SQLSTATE 40001 was not retried: {error}")
    finally:
        await database.close()
    assert attempts == 2
