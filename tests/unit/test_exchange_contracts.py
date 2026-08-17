from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from domain.bilateral_exchange import ExchangeParty
from domain.exchange_contracts import (
    ContractViolation,
    ExchangeEnvelope,
    OfferApproval,
    OfferLine,
    OfferVersion,
    ReleaseManifest,
    ReleaseStatus,
    validate_counteroffer,
)
from domain.hashing import content_hash

NOW = datetime(2026, 8, 18, 12, tzinfo=UTC)
HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64


def _release(**changes: object) -> ReleaseManifest:
    payload = {
        "case_id": "case-1",
        "owner": ExchangeParty.BUYER,
        "recipient": ExchangeParty.SELLER,
        "purpose": "qualify one meeting-intelligence purchase",
        "fields": ("goal", "seats"),
        "transformations": {"goal": "IDENTITY"},
        "source_versions": {"requirement": 3},
        "expires_at": NOW + timedelta(hours=1),
    }
    payload.update({key: value for key, value in changes.items() if key in payload})
    return ReleaseManifest(
        manifest_id="manifest-1",
        approval_id="approval-1",
        approved_payload_hash=content_hash(payload),
        status=changes.get("status", ReleaseStatus.ACTIVE),
        **payload,
    )


def _offer(version: int = 1, **changes: object) -> OfferVersion:
    values: dict[str, object] = {
        "offer_id": "offer-1",
        "case_id": "case-1",
        "version": version,
        "proposer": ExchangeParty.BUYER if version % 2 else ExchangeParty.SELLER,
        "recipient": ExchangeParty.SELLER if version % 2 else ExchangeParty.BUYER,
        "predecessor_hash": None,
        "changed_terms": (),
        "rationale": "Matches the released scope.",
        "currency": "USD",
        "lines": (
            OfferLine(
                item_id="license",
                description="Annual workspace license",
                quantity=10,
                unit_price=Decimal("120.00"),
            ),
        ),
        "total": Decimal("1200.00"),
        "expires_at": NOW + timedelta(hours=1),
        "requirement_hash": HASH_A,
        "evidence_hash": HASH_B,
    }
    values.update(changes)
    return OfferVersion.model_validate(values)


def test_release_manifest_discloses_only_exact_approved_fields() -> None:
    manifest = _release()
    released = manifest.release(
        {"goal": "Meeting Intelligence", "seats": 10, "hidden_budget": 2500}, now=NOW
    )
    assert released == {"goal": "Meeting Intelligence", "seats": 10}
    assert manifest.manifest_hash.startswith("sha256:")


def test_release_manifest_rejects_changed_expired_revoked_and_private_contracts() -> None:
    with pytest.raises(ValidationError, match="exact disclosure"):
        ReleaseManifest(
            manifest_id="manifest-1",
            case_id="case-1",
            owner=ExchangeParty.BUYER,
            recipient=ExchangeParty.SELLER,
            purpose="qualification",
            fields=("goal",),
            transformations={},
            source_versions={"requirement": 1},
            expires_at=NOW + timedelta(hours=1),
            approval_id="approval-1",
            approved_payload_hash=HASH_A,
        )
    with pytest.raises(ValidationError, match="safe top-level"):
        _release(fields=("seller_floor",))
    with pytest.raises(ContractViolation, match="expired"):
        _release(expires_at=NOW).release({"goal": "x", "seats": 1}, now=NOW)
    with pytest.raises(ContractViolation, match="revoked"):
        _release(status=ReleaseStatus.REVOKED).release(
            {"goal": "x", "seats": 1}, now=NOW
        )


def test_envelope_hash_rejects_changed_terms_and_private_values() -> None:
    envelope = ExchangeEnvelope(
        envelope_id="envelope-1",
        case_id="case-1",
        sender=ExchangeParty.BUYER,
        recipient=ExchangeParty.SELLER,
        sequence=1,
        causation_id="command-1",
        manifest_hash=HASH_A,
        payload={"goal": "meeting intelligence"},
        expires_at=NOW + timedelta(hours=1),
    )
    with pytest.raises(ValidationError, match="payload_hash"):
        ExchangeEnvelope(**{**envelope.model_dump(), "payload": {"goal": "changed"}})
    with pytest.raises(ValidationError, match="private-plane"):
        ExchangeEnvelope(
            **{
                **envelope.model_dump(exclude={"payload_hash"}),
                "payload": {"reservation_value": 2000},
            }
        )


def test_offer_arithmetic_expiry_wrong_party_and_exact_approval_binding() -> None:
    offer = _offer()
    with pytest.raises(ValidationError, match="line-item arithmetic"):
        _offer(total=Decimal("1199.00"))
    with pytest.raises(ContractViolation, match="recipient"):
        offer.assert_actionable(actor=ExchangeParty.BUYER, now=NOW)
    with pytest.raises(ContractViolation, match="expired"):
        offer.assert_actionable(actor=ExchangeParty.SELLER, now=offer.expires_at)
    wrong = OfferApproval(
        approval_id="approval-1",
        case_id="case-1",
        offer_hash=HASH_A,
        approver_id="buyer-admin",
        approved_at=NOW,
        expires_at=NOW + timedelta(minutes=30),
    )
    with pytest.raises(ContractViolation, match="exact offer"):
        wrong.authorize(offer, now=NOW)
    exact = wrong.model_copy(update={"offer_hash": offer.offer_hash})
    approved = exact.authorize(offer, now=NOW)
    assert approved.approval_status == "APPROVED"
    assert approved.offer_hash == offer.offer_hash


def test_counteroffers_are_sequential_alternating_and_exactly_describe_changes() -> None:
    first = _offer()
    second = _offer(
        2,
        predecessor_hash=first.offer_hash,
        changed_terms=("total", "lines"),
        lines=(
            OfferLine(
                item_id="license",
                description="Annual workspace license",
                quantity=10,
                unit_price=Decimal("110.00"),
            ),
        ),
        total=Decimal("1100.00"),
    )
    validate_counteroffer(first, second)
    simultaneous = _offer(
        2,
        predecessor_hash=first.offer_hash,
        changed_terms=("currency",),
        currency="EUR",
    )
    validate_counteroffer(first, simultaneous)
    with pytest.raises(ContractViolation, match="version is not sequential"):
        validate_counteroffer(second, simultaneous)
    stale = _offer(
        2,
        predecessor_hash=HASH_A,
        changed_terms=("currency",),
        currency="EUR",
    )
    with pytest.raises(ContractViolation, match="current offer"):
        validate_counteroffer(first, stale)
