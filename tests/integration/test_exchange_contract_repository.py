from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from domain.bilateral_exchange import ExchangeParty
from domain.exchange_contracts import (
    ExchangeEnvelope,
    ExchangeReceipt,
    OfferApproval,
    OfferLine,
    OfferVersion,
    ReleaseManifest,
)
from domain.hashing import content_hash
from persistence.bilateral_repository import BilateralRepository
from persistence.database import Database, DatabaseSettings
from persistence.models import Base, Organization
from persistence.repositories import PersistenceConflict

NOW = datetime(2026, 8, 18, 12, tzinfo=UTC)
HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64


def _manifest() -> ReleaseManifest:
    approved = {
        "case_id": "case-1",
        "owner": ExchangeParty.BUYER,
        "recipient": ExchangeParty.SELLER,
        "purpose": "qualify an exact purchase",
        "fields": ("goal",),
        "transformations": {},
        "source_versions": {"requirement": 1},
        "expires_at": NOW + timedelta(hours=2),
    }
    return ReleaseManifest(
        manifest_id="manifest-1",
        approval_id="disclosure-approval-1",
        approved_payload_hash=content_hash(approved),
        **approved,
    )


def _offer(
    version: int = 1,
    *,
    predecessor_hash: str | None = None,
    rationale: str = "Exact released scope.",
) -> OfferVersion:
    unit_price = Decimal("100") if version == 1 else Decimal("95")
    return OfferVersion(
        offer_id="offer-1",
        case_id="case-1",
        version=version,
        proposer=ExchangeParty.BUYER if version == 1 else ExchangeParty.SELLER,
        recipient=ExchangeParty.SELLER if version == 1 else ExchangeParty.BUYER,
        predecessor_hash=predecessor_hash,
        changed_terms=() if version == 1 else ("lines", "total"),
        rationale=rationale,
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


async def test_exchange_contracts_are_idempotent_exact_and_current() -> None:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        async with database.transaction("org-buyer") as session:
            session.add(Organization(id="org-buyer", name="Buyer"))
        manifest = _manifest()
        envelope = ExchangeEnvelope(
            envelope_id="envelope-1",
            case_id="case-1",
            sender=ExchangeParty.BUYER,
            recipient=ExchangeParty.SELLER,
            sequence=1,
            causation_id="command-1",
            manifest_hash=manifest.manifest_hash,
            payload=manifest.release({"goal": "meeting intelligence"}, now=NOW),
            expires_at=NOW + timedelta(hours=1),
        )
        receipt = ExchangeReceipt(
            receipt_id="receipt-1",
            envelope_id=envelope.envelope_id,
            case_id=envelope.case_id,
            recipient=ExchangeParty.SELLER,
            envelope_hash=envelope.payload_hash,
            received_at=NOW,
        )
        first = _offer()
        second = _offer(2, predecessor_hash=first.offer_hash)
        approval = OfferApproval(
            approval_id="offer-approval-1",
            case_id="case-1",
            offer_hash=second.offer_hash,
            approver_id="buyer-admin",
            approved_at=NOW,
            expires_at=NOW + timedelta(minutes=30),
        )
        async with database.transaction("org-buyer") as session:
            repository = BilateralRepository(session, "org-buyer")
            stored_manifest = await repository.store_release_manifest(manifest)
            duplicate_manifest = await repository.store_release_manifest(manifest)
            assert stored_manifest.id == duplicate_manifest.id
            await repository.store_envelope(envelope)
            await repository.acknowledge_envelope(receipt)
            await repository.store_offer(first)
            await repository.store_offer(second)
            stored_approval = await repository.approve_offer(approval, now=NOW)
            assert stored_approval.offer_hash == second.offer_hash
            assert stored_approval.approval_hash.startswith("sha256:")

        stale = _offer(2, predecessor_hash=first.offer_hash, rationale="Competing counteroffer.")
        async with database.transaction("org-buyer") as session:
            with pytest.raises(PersistenceConflict, match="sequential"):
                await BilateralRepository(session, "org-buyer").store_offer(stale)
    finally:
        await database.close()
