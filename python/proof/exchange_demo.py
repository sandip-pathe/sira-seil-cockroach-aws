"""Live K2 exchange-bound causal rerun and exact DataHub-owner approval proof."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from typing import Any

from domain.hashing import content_hash

from .causal_demo import run_causal_proof
from .constants import SUPPORT_OWNER_URN
from .datahub_mcp import (
    create_receipt_anchor,
    open_session,
    publish_receipt_projection,
    read_stable,
    reread_receipt_projection,
)
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


def _require_run(causal: dict[str, Any], label: str) -> dict[str, Any]:
    runs = causal.get("runs")
    if not isinstance(runs, list):
        raise ProofContractError("buyer decision evidence has no causal runs")
    matches = [run for run in runs if isinstance(run, dict) and run.get("label") == label]
    if len(matches) != 1:
        raise ProofContractError(f"buyer decision evidence requires one {label} run")
    return matches[0]


def _buyer_decision_evidence_core(
    causal: dict[str, Any], projections: tuple[dict[str, Any], ...]
) -> dict[str, Any]:
    baseline = _require_run(causal, "baseline-pii-present")
    counterfactual = _require_run(causal, "pii-removed")
    restored = _require_run(causal, "pii-restored")
    if causal.get("status") != "PASS" or causal.get("causalSequence") != [
        "adapter-b",
        "adapter-a",
        "adapter-b",
    ]:
        raise ProofContractError("buyer decision evidence requires a passing B-A-B proof")
    if (
        baseline.get("winnerAdapterId") != "adapter-b"
        or restored.get("winnerAdapterId") != "adapter-b"
        or baseline.get("piiPresent") is not True
        or restored.get("piiPresent") is not True
        or counterfactual.get("winnerAdapterId") != "adapter-a"
        or counterfactual.get("piiPresent") is not False
    ):
        raise ProofContractError("buyer decision evidence causal winners are invalid")
    for field in ("observationHash", "environmentFingerprint", "manifestHash", "decisionHash"):
        if baseline.get(field) != restored.get(field):
            raise ProofContractError("buyer decision evidence restored baseline does not match")
    if counterfactual.get("decisionHash") == restored.get("decisionHash"):
        raise ProofContractError("buyer decision evidence counterfactual did not change decision")

    observation = restored.get("environmentObservation")
    if not isinstance(observation, dict):
        raise ProofContractError("buyer decision evidence has no safe DataHub observation")
    safe_context = observation.get("safeContext")
    source_details = observation.get("sourceDetails")
    if not isinstance(safe_context, dict) or not isinstance(source_details, list):
        raise ProofContractError("buyer decision evidence DataHub sources are invalid")
    if observation.get("semanticHash") != restored.get("observationHash"):
        raise ProofContractError("buyer decision evidence observation hash is unbound")

    negative_control = causal.get("negativeControl")
    required_controls = (
        "tagObservedBeforeEvaluation",
        "acceptedFingerprintUnchanged",
        "manifestHashUnchanged",
        "decisionHashUnchanged",
    )
    if not isinstance(negative_control, dict) or not all(
        negative_control.get(field) is True for field in required_controls
    ):
        raise ProofContractError("buyer decision evidence negative control did not pass")

    projections_by_id = {
        projection.get("adapterId"): projection
        for projection in projections
        if isinstance(projection.get("adapterId"), str)
    }
    if set(projections_by_id) != {"adapter-a", "adapter-b"}:
        raise ProofContractError("buyer decision evidence requires two exact seller projections")
    verdicts = restored.get("verdicts")
    if not isinstance(verdicts, list):
        raise ProofContractError("buyer decision evidence has no candidate verdicts")
    verdicts_by_id = {
        verdict.get("adapter_id"): verdict
        for verdict in verdicts
        if isinstance(verdict, dict) and isinstance(verdict.get("adapter_id"), str)
    }
    if set(verdicts_by_id) != {"adapter-a", "adapter-b"}:
        raise ProofContractError("buyer decision evidence requires two exact verdicts")

    seller_evidence = []
    for adapter_id in ("adapter-a", "adapter-b"):
        projection = projections_by_id[adapter_id]
        verdict = verdicts_by_id[adapter_id]
        if projection.get("artifactDigest") != verdict.get("artifact_digest"):
            raise ProofContractError("buyer decision evidence seller digest is unbound")
        seller_evidence.append(
            {
                "adapterId": adapter_id,
                "sourceSellerOrganizationId": projection.get("sourceSellerOrganizationId"),
                "sourcePackVersionId": projection.get("sourcePackVersionId"),
                "projectionHash": projection.get("projectionHash"),
                "artifactDigest": projection.get("artifactDigest"),
                "capabilities": projection.get("capabilities"),
                "fixedPrice": projection.get("fixedPrice"),
                "eligible": verdict.get("eligible"),
                "failedGateIds": verdict.get("failed_gate_ids"),
                "trialResultHash": verdict.get("result_hash"),
            }
        )

    return {
        "schemaVersion": "BuyerDecisionEvidenceCore/v0",
        "decisionHash": restored["decisionHash"],
        "recommendation": {
            "adapterId": "adapter-b",
            "manifestHash": restored["manifestHash"],
            "observationHash": restored["observationHash"],
            "environmentFingerprint": restored["environmentFingerprint"],
            "decisionGraphSelectedPlanId": restored["decisionGraphSelectedPlanId"],
            "decisionGraphEvaluationHash": restored["decisionGraphEvaluationHash"],
            "requiredGateIds": restored["emittedGateIds"],
        },
        "dataHubContext": {
            "safeContext": safe_context,
            "sourceDetails": source_details,
        },
        "sellerEvidence": seller_evidence,
        "counterfactual": {
            "sourceUrn": safe_context.get("profileUrn"),
            "fact": "customer_profile.email PII tag",
            "from": True,
            "to": False,
            "alternativeAdapterId": "adapter-a",
            "decisionHash": counterfactual["decisionHash"],
            "manifestHash": counterfactual["manifestHash"],
            "environmentFingerprint": counterfactual["environmentFingerprint"],
        },
        "causalVerification": {
            "sequence": causal["causalSequence"],
            "baselineDecisionHash": baseline["decisionHash"],
            "restoredDecisionHash": restored["decisionHash"],
            "restoredBaselineMatched": True,
            "negativeControlPassed": True,
        },
    }


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
    restored = _require_run(causal, "pii-restored")
    decision_evidence = _buyer_decision_evidence_core(causal, projections)
    decision_evidence_hash = content_hash(decision_evidence)
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
        if (
            current_observation.semantic_hash != restored["observationHash"]
            or current_observation.environment_fingerprint != restored["environmentFingerprint"]
        ):
            raise ProofContractError("buyer decision evidence DataHub context drifted")
    current_manifest = compile_manifest(current_observation)
    if current_manifest.manifest_hash != restored["manifestHash"]:
        raise ProofContractError("buyer decision evidence manifest drifted")
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

    datahub_projection = {
        "schemaVersion": "DataHubBuyerDecisionProjection/v0",
        "buyerDecisionCoreHash": decision_evidence_hash,
        "decisionHash": decision_evidence["decisionHash"],
        "recommendedAdapterId": decision_evidence["recommendation"]["adapterId"],
        "counterfactualDecisionHash": decision_evidence["counterfactual"]["decisionHash"],
        "counterfactualAdapterId": decision_evidence["counterfactual"]["alternativeAdapterId"],
        "environmentFingerprint": decision_evidence["recommendation"]["environmentFingerprint"],
        "sourceUrns": sorted(
            {
                detail["urn"]
                for detail in decision_evidence["dataHubContext"]["sourceDetails"]
                if isinstance(detail, dict) and isinstance(detail.get("urn"), str)
            }
        ),
    }
    projection_hash = content_hash(datahub_projection)
    published_projection = {**datahub_projection, "projectionHash": projection_hash}
    async with open_session() as session:
        anchor_urn = await create_receipt_anchor(
            session, title=f"SIRA buyer decision {decision_evidence_hash[-12:]}"
        )
        await publish_receipt_projection(
            session,
            anchor_urn=anchor_urn,
            title=f"SIRA buyer decision {decision_evidence_hash[-12:]}",
            core_hash=decision_evidence_hash,
            projection=published_projection,
        )
    reread = await reread_receipt_projection(anchor_urn, core_hash=decision_evidence_hash)
    reread_text = json.dumps(reread, sort_keys=True)
    if decision_evidence_hash not in reread_text or projection_hash not in reread_text:
        raise ProofContractError("DATAHUB_BUYER_DECISION_REREAD_MISMATCH")
    return {
        "status": "PASS",
        "exchangeCausalProof": causal,
        "buyerProjections": list(projections),
        "buyerDecisionReceipt": {
            "schemaVersion": "BuyerDecisionReceipt/v0",
            "coreHash": decision_evidence_hash,
            "decisionHash": decision_evidence["decisionHash"],
            "payload": decision_evidence,
            "dataHubWriteback": {
                "status": "REREAD_VERIFIED",
                "anchorUrn": anchor_urn,
                "projectionHash": projection_hash,
                "rereadMatched": True,
            },
        },
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
