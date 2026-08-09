from __future__ import annotations

import pytest

from domain.hashing import content_hash
from proof.models import ProofContractError
from proof.receipt import build_receipt_core


def _arguments() -> dict[str, object]:
    digest = "sha256:" + "a" * 64
    return {
        "observation_hash": "sha256:" + "1" * 64,
        "environment_fingerprint": "sha256:" + "2" * 64,
        "manifest_hash": "sha256:" + "3" * 64,
        "trial_result_hashes": {"adapter-a": "sha256:" + "4" * 64},
        "decision_hash": "sha256:" + "5" * 64,
        "approval_subject_hash": "sha256:" + "6" * 64,
        "datahub_owner_urn": "urn:li:corpGroup:support-data-owners",
        "adapter_projection_hash": "sha256:" + "7" * 64,
        "tested_adapter_digest": digest,
        "selected_adapter_digest": digest,
        "approved_adapter_digest": digest,
        "healthy_adapter_digest": digest,
        "active_adapter_digest": digest,
        "prior_adapter_digest": "sha256:" + "b" * 64,
        "prior_route_version": 1,
        "verified_route_version": 2,
        "routed_traffic_result_hash": "sha256:" + "8" * 64,
        "route_state_at_verification": "ACTIVE_VERIFIED",
        "datahub_anchor_urn": "urn:li:document:sira-proof-receipt",
        "datahub_projection_hash": "sha256:" + "9" * 64,
    }


def test_receipt_hash_covers_only_the_immutable_core() -> None:
    receipt = build_receipt_core(**_arguments())  # type: ignore[arg-type]

    assert receipt.core_hash == content_hash(receipt.payload)
    rendered = str(receipt.payload).casefold()
    for excluded in ("core_hash", "created_at", "delivery", "attempt", "acknowledgement"):
        assert excluded not in rendered


def test_receipt_rejects_any_digest_chain_mismatch() -> None:
    with pytest.raises(ProofContractError, match="DIGEST_CHAIN_MISMATCH"):
        build_receipt_core(  # type: ignore[arg-type]
            **{**_arguments(), "active_adapter_digest": "sha256:" + "0" * 64}
        )
