from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from domain.bilateral_exchange import ExchangeParty
from domain.exchange_contracts import OfferLine, OfferVersion
from persistence.bilateral_repository import BilateralRepository
from persistence.database import Database, DatabaseSettings
from persistence.models import BilateralOfferVersion
from persistence.repositories import PersistenceConflict

pytestmark = pytest.mark.cockroach

NOW = datetime(2026, 8, 18, 12, tzinfo=UTC)
HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64


def _runtime_url() -> str:
    value = os.environ.get("SIRA_TEST_DATABASE_URL")
    if not value:
        pytest.skip("SIRA_TEST_DATABASE_URL is required")
    return value


def _offer(
    *,
    case_id: str,
    offer_id: str,
    version: int,
    price: str,
    predecessor_hash: str | None = None,
) -> OfferVersion:
    unit_price = Decimal(price)
    return OfferVersion(
        offer_id=offer_id,
        case_id=case_id,
        version=version,
        proposer=ExchangeParty.BUYER if version == 1 else ExchangeParty.SELLER,
        recipient=ExchangeParty.SELLER if version == 1 else ExchangeParty.BUYER,
        predecessor_hash=predecessor_hash,
        changed_terms=() if version == 1 else ("lines", "total"),
        rationale=f"Exact commercial terms at {price} per seat.",
        currency="USD",
        lines=(
            OfferLine(
                item_id="seat",
                description="Annual seat",
                quantity=10,
                unit_price=unit_price,
            ),
        ),
        total=unit_price * 10,
        expires_at=NOW + timedelta(hours=1),
        requirement_hash=HASH_A,
        evidence_hash=HASH_B,
    )


async def test_simultaneous_counteroffers_commit_exactly_one_version() -> None:
    runtime_url = _runtime_url()
    database = Database(DatabaseSettings(database_url=runtime_url))
    admin = Database(DatabaseSettings(database_url=runtime_url.replace("sira_app@", "root@")))
    suffix = uuid4().hex[:12]
    buyer_id = f"org_race_buyer_{suffix}"
    seller_id = f"org_race_seller_{suffix}"
    case_id = f"case_race_{suffix}"
    first = _offer(case_id=case_id, offer_id=f"offer_{suffix}", version=1, price="100")
    counters = (
        _offer(
            case_id=case_id,
            offer_id=first.offer_id,
            version=2,
            price="95",
            predecessor_hash=first.offer_hash,
        ),
        _offer(
            case_id=case_id,
            offer_id=first.offer_id,
            version=2,
            price="90",
            predecessor_hash=first.offer_hash,
        ),
    )
    try:
        async with admin.transaction(buyer_id) as session:
            await session.execute(
                text(
                    "UPSERT INTO organizations (id, name, version) "
                    "VALUES (:buyer_id, 'Race Buyer', 1), (:seller_id, 'Race Seller', 1)"
                ),
                {"buyer_id": buyer_id, "seller_id": seller_id},
            )
        async with database.transaction(buyer_id) as session:
            repository = BilateralRepository(session, buyer_id)
            await repository.create_case(case_id=case_id, seller_organization_id=seller_id)
            await repository.store_offer(first)

        ready = asyncio.Event()
        contenders = 0
        contenders_lock = asyncio.Lock()

        async def submit(counter: OfferVersion) -> str:
            async def work(session: AsyncSession) -> str:
                nonlocal contenders
                async with contenders_lock:
                    contenders += 1
                    if contenders == 2:
                        ready.set()
                await ready.wait()
                record = await BilateralRepository(session, buyer_id).store_offer(counter)
                return record.offer_hash

            return await database.run_retryable(buyer_id, work, base_delay_seconds=0)

        results = await asyncio.gather(
            *(submit(counter) for counter in counters), return_exceptions=True
        )
        winners = [result for result in results if isinstance(result, str)]
        conflicts = [result for result in results if isinstance(result, PersistenceConflict)]

        assert len(winners) == 1, repr(results)
        assert len(conflicts) == 1
        async with database.transaction(buyer_id) as session:
            latest = await session.scalar(
                select(BilateralOfferVersion).where(
                    BilateralOfferVersion.organization_id == buyer_id,
                    BilateralOfferVersion.case_id == case_id,
                    BilateralOfferVersion.version == 2,
                )
            )
            assert latest is not None
            assert latest.version == 2
            assert latest.offer_hash == winners[0]
    finally:
        await database.close()
        await admin.close()
