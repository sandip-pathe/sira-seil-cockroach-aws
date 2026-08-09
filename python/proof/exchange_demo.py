"""Live K2 exchange-bound causal rerun and exact DataHub-owner approval proof."""

from __future__ import annotations

import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from typing import Any

from domain.hashing import content_hash

from .causal_demo import run_causal_proof
from .constants import SUPPORT_OWNER_URN
from .datahub_mcp import open_session, read_stable
from .exchange import (
    CandidateRelease,
    assert_current_approval,
    candidate_release,
    exact_approval_subject,
    project_published_adapter,
)
from .manifest_v0 import compile_manifest
from .models import ProofContractError

OWNER_ACTOR_ID = "seeded_support_owner"
OWNER_ACTOR_MAPPING = {OWNER_ACTOR_ID: SUPPORT_OWNER_URN}


def _image_digest(image: str) -> str:
    docker = shutil.which("docker")
    if docker is None:
        raise ProofContractError("Docker is required for the K2 exchange proof")
    completed = subprocess.run(  # noqa: S603 - executable and image are fixed locally
        [docker, "image", "inspect", "--format", "{{.Id}}", image],
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    digest = completed.stdout.strip()
    if completed.returncode != 0 or not digest.startswith("sha256:"):
        raise ProofContractError(f"missing curated adapter image: {image}")
    return digest


def _published_projection(adapter_id: str, image: str, price: str) -> dict[str, Any]:
    digest = _image_digest(image)
    conformance_hash = content_hash(
        {
            "protocolVersion": "TrialCase/v0",
            "artifactDigest": digest,
            "canaryContract": "support-pii-canary-v1",
            "runtimeIsolation": "uds-no-network-v1",
        }
    )
    published_payload = {
        "schema_version": "1.0.0",
        "proof_adapter": {
            "adapter_id": adapter_id,
            "artifact_digest": digest,
            "protocol_version": "TrialCase/v0",
            "capabilities": sorted(
                {
                    "SUPPORT_SUMMARIZATION",
                    "CUSTOMER_EMAIL_OUTPUT",
                    *({"PII_REDACTION"} if adapter_id == "adapter-b" else set()),
                }
            ),
            "declared_region": "EU",
            "fixed_price": {"amount": price, "currency": "USD"},
            "conformance_hash": conformance_hash,
        },
        "evidence": [],
        "seller_private": {"build_environment": "intentionally excluded"},
    }
    pack_id = f"pack-{adapter_id}-v1"
    pack_hash = content_hash(published_payload)
    return project_published_adapter(
        source_seller_organization_id=f"org-seller-{adapter_id}",
        source_pack_version_id=pack_id,
        source_pack_content_hash=pack_hash,
        publication_event_key=f"seller-pack-published:{pack_id}",
        published_payload=published_payload,
    )


async def run_exchange_proof() -> dict[str, Any]:
    projections = (
        _published_projection("adapter-a", "sira-proof-adapter-a:k0", "0.02"),
        _published_projection("adapter-b", "sira-proof-adapter-b:k0", "0.05"),
    )
    releases: tuple[CandidateRelease, ...] = tuple(map(candidate_release, projections))
    causal = await run_causal_proof(releases=releases)
    if causal.get("status") != "PASS":
        raise ProofContractError("exchange-bound causal rerun did not pass")
    baseline = causal["runs"][0]
    winner_id = str(baseline["winnerAdapterId"])
    winner = next(release for release in releases if release.adapter_id == winner_id)
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=15)
    subject = exact_approval_subject(
        manifest_hash=str(baseline["manifestHash"]),
        environment_fingerprint=str(baseline["environmentFingerprint"]),
        decision_hash=str(baseline["decisionHash"]),
        release=winner,
        datahub_owner_urn=SUPPORT_OWNER_URN,
        actor_id=OWNER_ACTOR_ID,
        actor_role="DATA_OWNER",
        expires_at=expires_at,
    )

    # This read is intentionally after authority is frozen and immediately before
    # the K3 effect boundary. K2 proves every mismatch blocks before any router call.
    async with open_session() as session:
        current_observation = await read_stable(session)
    current_manifest = compile_manifest(current_observation)
    assert_current_approval(
        subject=subject,
        approved_subject_hash=subject.subject_hash,
        actor_id=OWNER_ACTOR_ID,
        actor_role="DATA_OWNER",
        owner_actor_mapping=OWNER_ACTOR_MAPPING,
        current_environment_fingerprint=current_observation.environment_fingerprint,
        current_manifest_hash=current_manifest.manifest_hash,
        current_adapter_digest=winner.artifact_digest,
        expires_at=expires_at,
        revoked_at=None,
        now=now,
    )
    blocked_cases: dict[str, str] = {}
    for label, changes in (
        ("wrong-owner", {"actor_id": "not-the-owner"}),
        ("stale-context", {"current_manifest_hash": "sha256:" + "0" * 64}),
        ("digest-substitution", {"current_adapter_digest": "sha256:" + "1" * 64}),
        ("expired", {"expires_at": now}),
        ("revoked", {"revoked_at": now}),
    ):
        arguments: dict[str, Any] = {
            "subject": subject,
            "approved_subject_hash": subject.subject_hash,
            "actor_id": OWNER_ACTOR_ID,
            "actor_role": "DATA_OWNER",
            "owner_actor_mapping": OWNER_ACTOR_MAPPING,
            "current_environment_fingerprint": current_observation.environment_fingerprint,
            "current_manifest_hash": current_manifest.manifest_hash,
            "current_adapter_digest": winner.artifact_digest,
            "expires_at": expires_at,
            "revoked_at": None,
            "now": now,
        }
        try:
            assert_current_approval(**{**arguments, **changes})
        except ProofContractError as exc:
            blocked_cases[label] = str(exc)
        else:
            raise ProofContractError(f"K2 negative case did not block: {label}")
    return {
        "status": "PASS",
        "exchangeCausalProof": causal,
        "buyerProjections": list(projections),
        "approval": {
            "subjectHash": subject.subject_hash,
            "actorId": subject.actor_id,
            "actorRole": subject.actor_role,
            "dataHubOwnerUrn": subject.datahub_owner_urn,
            "expiresAt": subject.expires_at.isoformat(),
            "preEffectRereadMatched": True,
            "routerCallCount": 0,
        },
        "blockedBeforeEffect": blocked_cases,
    }
