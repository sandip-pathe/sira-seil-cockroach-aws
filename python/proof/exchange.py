"""Pure K2 publication projection and exact proof-authority contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from domain.hashing import content_hash

from .models import ProofContractError

PROOF_ADAPTER_FIELDS = frozenset(
    {
        "adapter_id",
        "artifact_digest",
        "protocol_version",
        "capabilities",
        "declared_region",
        "fixed_price",
        "conformance_hash",
    }
)
PUBLIC_EVIDENCE_FIELDS = frozenset(
    {"id", "source_class", "observed_at", "verification_state", "source_url"}
)


@dataclass(frozen=True, slots=True)
class CandidateRelease:
    projection_hash: str
    adapter_id: str
    artifact_digest: str
    protocol_version: str
    capabilities: tuple[str, ...]
    declared_region: str
    fixed_price: str
    conformance_hash: str


@dataclass(frozen=True, slots=True)
class ExactApprovalSubject:
    manifest_hash: str
    environment_fingerprint: str
    decision_hash: str
    adapter_projection_hash: str
    adapter_digest: str
    datahub_owner_urn: str
    actor_id: str
    actor_role: str
    expires_at: datetime
    subject_hash: str


def _hash(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
        raise ProofContractError(f"{label} must be an exact sha256 digest")
    return value


def project_published_adapter(
    *,
    source_seller_organization_id: str,
    source_pack_version_id: str,
    source_pack_content_hash: str,
    publication_event_key: str,
    published_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Return only fields that may cross from a seller pack into a buyer tenant."""

    adapter = published_payload.get("proof_adapter")
    if not isinstance(adapter, dict) or set(adapter) != PROOF_ADAPTER_FIELDS:
        raise ProofContractError("published pack has no exact proof_adapter/v0 section")
    if adapter.get("protocol_version") != "TrialCase/v0":
        raise ProofContractError("published proof adapter protocol is unsupported")
    capabilities = adapter.get("capabilities")
    if (
        not isinstance(capabilities, list)
        or not capabilities
        or not all(isinstance(item, str) for item in capabilities)
    ):
        raise ProofContractError("published proof adapter capabilities are invalid")
    fixed_price = adapter.get("fixed_price")
    if (
        not isinstance(fixed_price, dict)
        or set(fixed_price) != {"amount", "currency"}
        or fixed_price.get("currency") != "USD"
        or not isinstance(fixed_price.get("amount"), str)
    ):
        raise ProofContractError("published proof adapter fixed price is invalid")
    evidence = published_payload.get("evidence", [])
    if not isinstance(evidence, list):
        raise ProofContractError("published evidence projection is invalid")
    public_evidence = [
        {key: item[key] for key in sorted(PUBLIC_EVIDENCE_FIELDS) if key in item}
        for item in evidence
        if isinstance(item, dict)
    ]
    payload = {
        "schemaVersion": "BuyerProofAdapterProjection/v0",
        "sourceSellerOrganizationId": source_seller_organization_id,
        "sourcePackVersionId": source_pack_version_id,
        "sourcePackContentHash": _hash(source_pack_content_hash, "source pack hash"),
        "publicationEventKey": publication_event_key,
        "adapterId": adapter["adapter_id"],
        "artifactDigest": _hash(adapter["artifact_digest"], "adapter artifact digest"),
        "protocolVersion": adapter["protocol_version"],
        "capabilities": sorted(set(capabilities)),
        "declaredRegion": adapter["declared_region"],
        "fixedPrice": fixed_price,
        "publicEvidenceReferences": public_evidence,
        "conformanceHash": _hash(adapter["conformance_hash"], "conformance hash"),
    }
    return {**payload, "projectionHash": content_hash(payload)}


def candidate_release(projection: Mapping[str, Any]) -> CandidateRelease:
    price = projection.get("fixedPrice")
    if not isinstance(price, dict) or not isinstance(price.get("amount"), str):
        raise ProofContractError("buyer projection has no fixed price")
    capabilities = projection.get("capabilities")
    if not isinstance(capabilities, list) or not all(
        isinstance(item, str) for item in capabilities
    ):
        raise ProofContractError("buyer projection has invalid capabilities")
    return CandidateRelease(
        projection_hash=_hash(projection.get("projectionHash"), "projection hash"),
        adapter_id=str(projection["adapterId"]),
        artifact_digest=_hash(projection.get("artifactDigest"), "adapter artifact digest"),
        protocol_version=str(projection["protocolVersion"]),
        capabilities=tuple(sorted(capabilities)),
        declared_region=str(projection["declaredRegion"]),
        fixed_price=price["amount"],
        conformance_hash=_hash(projection.get("conformanceHash"), "conformance hash"),
    )


def exact_approval_subject(
    *,
    manifest_hash: str,
    environment_fingerprint: str,
    decision_hash: str,
    release: CandidateRelease,
    datahub_owner_urn: str,
    actor_id: str,
    actor_role: str,
    expires_at: datetime,
) -> ExactApprovalSubject:
    expiry = (
        expires_at.replace(tzinfo=UTC) if expires_at.tzinfo is None else expires_at.astimezone(UTC)
    )
    payload = {
        "manifestHash": _hash(manifest_hash, "manifest hash"),
        "environmentFingerprint": _hash(environment_fingerprint, "environment fingerprint"),
        "decisionHash": _hash(decision_hash, "decision hash"),
        "adapterProjectionHash": release.projection_hash,
        "adapterDigest": release.artifact_digest,
        "dataHubOwnerUrn": datahub_owner_urn,
        "actorId": actor_id,
        "actorRole": actor_role,
        "expiresAt": expiry.isoformat(),
    }
    return ExactApprovalSubject(
        manifest_hash=manifest_hash,
        environment_fingerprint=environment_fingerprint,
        decision_hash=decision_hash,
        adapter_projection_hash=release.projection_hash,
        adapter_digest=release.artifact_digest,
        datahub_owner_urn=datahub_owner_urn,
        actor_id=actor_id,
        actor_role=actor_role,
        expires_at=expiry,
        subject_hash=content_hash(payload),
    )


def assert_current_approval(
    *,
    subject: ExactApprovalSubject,
    approved_subject_hash: str,
    actor_id: str,
    actor_role: str,
    owner_actor_mapping: Mapping[str, str],
    current_environment_fingerprint: str,
    current_manifest_hash: str,
    current_adapter_digest: str,
    expires_at: datetime,
    revoked_at: datetime | None,
    now: datetime,
) -> None:
    current_time = now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)
    expiry = (
        expires_at.replace(tzinfo=UTC) if expires_at.tzinfo is None else expires_at.astimezone(UTC)
    )
    if (
        actor_id != subject.actor_id
        or actor_role != subject.actor_role
        or actor_role != "DATA_OWNER"
        or owner_actor_mapping.get(actor_id) != subject.datahub_owner_urn
    ):
        raise ProofContractError("PROOF_OWNER_AUTHORITY_REQUIRED")
    if revoked_at is not None:
        raise ProofContractError("PROOF_APPROVAL_REVOKED")
    if expiry != subject.expires_at or expiry <= current_time:
        raise ProofContractError("PROOF_APPROVAL_EXPIRED")
    if approved_subject_hash != subject.subject_hash:
        raise ProofContractError("PROOF_APPROVAL_SUBJECT_MISMATCH")
    if (
        current_environment_fingerprint != subject.environment_fingerprint
        or current_manifest_hash != subject.manifest_hash
    ):
        raise ProofContractError("PROOF_DATAHUB_CONTEXT_DRIFT")
    if current_adapter_digest != subject.adapter_digest:
        raise ProofContractError("PROOF_ADAPTER_DIGEST_SUBSTITUTION")
