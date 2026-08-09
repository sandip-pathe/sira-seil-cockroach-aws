"""Immutable K3 proof receipt core without delivery or self-hash cycles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domain.hashing import content_hash

from .models import ProofContractError


@dataclass(frozen=True, slots=True)
class ProofReceipt:
    payload: dict[str, Any]
    core_hash: str


def build_receipt_core(
    *,
    observation_hash: str,
    environment_fingerprint: str,
    manifest_hash: str,
    trial_result_hashes: dict[str, str],
    decision_hash: str,
    approval_subject_hash: str,
    datahub_owner_urn: str,
    adapter_projection_hash: str,
    tested_adapter_digest: str,
    selected_adapter_digest: str,
    approved_adapter_digest: str,
    healthy_adapter_digest: str,
    active_adapter_digest: str,
    prior_adapter_digest: str,
    prior_route_version: int,
    verified_route_version: int,
    routed_traffic_result_hash: str,
    route_state_at_verification: str,
    datahub_anchor_urn: str,
    datahub_projection_hash: str,
) -> ProofReceipt:
    bound_digests = {
        tested_adapter_digest,
        selected_adapter_digest,
        approved_adapter_digest,
        healthy_adapter_digest,
        active_adapter_digest,
    }
    if len(bound_digests) != 1:
        raise ProofContractError("PROOF_RECEIPT_DIGEST_CHAIN_MISMATCH")
    if route_state_at_verification not in {"ACTIVE_VERIFIED", "ROLLBACK_VERIFIED"}:
        raise ProofContractError("PROOF_RECEIPT_ROUTE_STATE_INVALID")
    if verified_route_version <= prior_route_version:
        raise ProofContractError("PROOF_RECEIPT_ROUTE_VERSION_INVALID")
    payload = {
        "schemaVersion": "ProofReceiptCore/v0",
        "causal": {
            "observationHash": observation_hash,
            "environmentFingerprint": environment_fingerprint,
            "manifestHash": manifest_hash,
            "trialResultHashes": dict(sorted(trial_result_hashes.items())),
            "decisionHash": decision_hash,
        },
        "authority": {
            "approvalSubjectHash": approval_subject_hash,
            "dataHubOwnerUrn": datahub_owner_urn,
            "adapterProjectionHash": adapter_projection_hash,
            "approvedAdapterDigest": approved_adapter_digest,
        },
        "verifiedEffect": {
            "testedAdapterDigest": tested_adapter_digest,
            "selectedAdapterDigest": selected_adapter_digest,
            "healthyAdapterDigest": healthy_adapter_digest,
            "activeAdapterDigest": active_adapter_digest,
            "priorAdapterDigest": prior_adapter_digest,
            "priorRouteVersion": prior_route_version,
            "verifiedRouteVersion": verified_route_version,
            "routedTrafficResultHash": routed_traffic_result_hash,
            "routeStateAtVerification": route_state_at_verification,
        },
        "dataHubProjection": {
            "anchorUrn": datahub_anchor_urn,
            "projectionHash": datahub_projection_hash,
        },
    }
    return ProofReceipt(payload=payload, core_hash=content_hash(payload))
