from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from domain.hashing import content_hash
from proof.exchange import (
    assert_current_approval,
    candidate_release,
    exact_approval_subject,
    project_published_adapter,
)
from proof.models import ProofContractError


def _projection() -> dict[str, object]:
    artifact_digest = "sha256:" + "a" * 64
    conformance_hash = "sha256:" + "b" * 64
    pack_hash = "sha256:" + "c" * 64
    return project_published_adapter(
        source_seller_organization_id="org_seller",
        source_pack_version_id="pack_adapter_a_v1",
        source_pack_content_hash=pack_hash,
        publication_event_key="seller-pack-published:pack_adapter_a_v1",
        published_payload={
            "proof_adapter": {
                "adapter_id": "adapter-a",
                "artifact_digest": artifact_digest,
                "protocol_version": "TrialCase/v0",
                "capabilities": ["CUSTOMER_EMAIL_OUTPUT", "SUPPORT_SUMMARIZATION"],
                "declared_region": "EU",
                "fixed_price": {"amount": "0.02", "currency": "USD"},
                "conformance_hash": conformance_hash,
            },
            "evidence": [
                {
                    "id": "public-evidence-a",
                    "source_class": "SELLER_ASSERTION",
                    "observed_at": "2030-01-01T00:00:00Z",
                    "verification_state": "VERIFIED",
                    "source_url": "https://example.invalid/adapter-a",
                    "claim_fields": ["seller-private-scope"],
                    "internal_review_notes": "must never cross the projection boundary",
                }
            ],
            "seller_private": {"credentials": "must never cross"},
        },
    )


def test_projection_is_allowlisted_hash_bound_and_replay_deterministic() -> None:
    first = _projection()
    second = _projection()
    rendered = str(first)

    assert first == second
    assert first["projectionHash"] == content_hash(
        {key: value for key, value in first.items() if key != "projectionHash"}
    )
    assert "seller_private" not in rendered
    assert "credentials" not in rendered
    assert "internal_review_notes" not in rendered
    assert "claim_fields" not in rendered


def test_projection_rejects_extra_adapter_fields() -> None:
    with pytest.raises(ProofContractError, match="exact proof_adapter"):
        project_published_adapter(
            source_seller_organization_id="org_seller",
            source_pack_version_id="pack-a",
            source_pack_content_hash="sha256:" + "c" * 64,
            publication_event_key="event-a",
            published_payload={
                "proof_adapter": {
                    "adapter_id": "adapter-a",
                    "artifact_digest": "sha256:" + "a" * 64,
                    "protocol_version": "TrialCase/v0",
                    "capabilities": ["SUPPORT_SUMMARIZATION"],
                    "declared_region": "EU",
                    "fixed_price": {"amount": "0.02", "currency": "USD"},
                    "conformance_hash": "sha256:" + "b" * 64,
                    "private_environment": "forbidden",
                }
            },
        )


def test_exact_approval_requires_current_owner_subject_context_and_digest() -> None:
    release = candidate_release(_projection())
    now = datetime(2030, 1, 1, tzinfo=UTC)
    subject = exact_approval_subject(
        manifest_hash="sha256:" + "d" * 64,
        environment_fingerprint="sha256:" + "e" * 64,
        decision_hash="sha256:" + "f" * 64,
        release=release,
        datahub_owner_urn="urn:li:corpGroup:support-data-owners",
        actor_id="seeded_support_owner",
        actor_role="DATA_OWNER",
        expires_at=now + timedelta(minutes=15),
    )
    valid = {
        "subject": subject,
        "approved_subject_hash": subject.subject_hash,
        "actor_id": "seeded_support_owner",
        "actor_role": "DATA_OWNER",
        "owner_actor_mapping": {"seeded_support_owner": "urn:li:corpGroup:support-data-owners"},
        "current_environment_fingerprint": subject.environment_fingerprint,
        "current_manifest_hash": subject.manifest_hash,
        "current_adapter_digest": subject.adapter_digest,
        "expires_at": now + timedelta(minutes=15),
        "revoked_at": None,
        "now": now,
    }

    assert_current_approval(**valid)
    for changed, code in (
        ({"actor_id": "wrong-owner"}, "PROOF_OWNER_AUTHORITY_REQUIRED"),
        ({"approved_subject_hash": "sha256:" + "0" * 64}, "SUBJECT_MISMATCH"),
        ({"current_manifest_hash": "sha256:" + "1" * 64}, "CONTEXT_DRIFT"),
        ({"current_adapter_digest": "sha256:" + "2" * 64}, "DIGEST_SUBSTITUTION"),
        ({"expires_at": now}, "APPROVAL_EXPIRED"),
        ({"revoked_at": now}, "APPROVAL_REVOKED"),
    ):
        with pytest.raises(ProofContractError, match=code):
            assert_current_approval(**{**valid, **changed})
