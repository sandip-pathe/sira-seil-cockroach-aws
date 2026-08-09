"""Live K3 approved effect, DataHub writeback, receipt, and rollback proof."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from domain.hashing import content_hash

from .causal_demo import _run_campaign
from .constants import PII_TAG_URN, PROFILE_DATASET_URN, SUPPORT_OWNER_URN
from .datahub_mcp import (
    create_receipt_anchor,
    open_session,
    publish_receipt_projection,
    read_stable,
    reread_receipt_projection,
    set_field_tag,
    wait_for_pii,
)
from .exchange import assert_current_approval, candidate_release, exact_approval_subject
from .exchange_demo import OWNER_ACTOR_ID, OWNER_ACTOR_MAPPING, _published_projection
from .manifest_v0 import compile_manifest
from .models import ProofContractError
from .receipt import build_receipt_core

RUNTIME_COMPOSE = Path("infra/datahub/k0/compose.runtime.yaml")
LOGGER = logging.getLogger(__name__)


def _effect(plan: dict[str, Any]) -> dict[str, Any]:
    docker = shutil.which("docker")
    if docker is None:
        raise ProofContractError("Docker is required for the K3 effect proof")
    environment = os.environ.copy()
    for key, image in (
        ("ADAPTER_A_DIGEST", "sira-proof-adapter-a:k0"),
        ("ADAPTER_B_DIGEST", "sira-proof-adapter-b:k0"),
    ):
        inspected = subprocess.run(  # noqa: S603 - fixed local executable and image names
            [docker, "image", "inspect", "--format", "{{.Id}}", image],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        if inspected.returncode != 0 or not inspected.stdout.strip().startswith("sha256:"):
            raise ProofContractError(f"router effect image is missing: {image}")
        environment[key] = inspected.stdout.strip()
    completed = subprocess.run(  # noqa: S603 - fixed local executable and compose file
        [
            docker,
            "compose",
            "-f",
            str(RUNTIME_COMPOSE),
            "exec",
            "-T",
            "router",
            "python",
            "/app/effect_probe.py",
        ],
        input=json.dumps(plan, sort_keys=True),
        text=True,
        capture_output=True,
        env=environment,
        timeout=20,
        check=False,
    )
    if completed.returncode != 0:
        raise ProofContractError(
            f"ROUTER_EFFECT_FAILED: {completed.stderr.strip() or completed.stdout.strip()}"
        )
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict) or payload.get("status") != "VERIFIED":
        raise ProofContractError("router effect did not return verified evidence")
    return payload


async def _set_pii(present: bool) -> None:
    async with open_session() as session:
        await set_field_tag(
            session,
            entity_urn=PROFILE_DATASET_URN,
            column_path="email",
            tag_urn=PII_TAG_URN,
            present=present,
        )
        await wait_for_pii(session, present=present)


async def run_deployment_proof(*, simulate_writeback_failure: bool = False) -> dict[str, Any]:
    projections = (
        _published_projection("adapter-a", "sira-proof-adapter-a:k0", "0.02"),
        _published_projection("adapter-b", "sira-proof-adapter-b:k0", "0.05"),
    )
    releases = tuple(map(candidate_release, projections))
    release_by_id = {release.adapter_id: release for release in releases}
    pii_removed = False
    active_a = False
    successful_effect: dict[str, Any] | None = None
    rollback: dict[str, Any] | None = None
    try:
        await _set_pii(False)
        pii_removed = True
        async with open_session() as session:
            observation = await read_stable(session)
        manifest = compile_manifest(observation)
        decision, campaign = await asyncio.to_thread(_run_campaign, manifest, releases)
        if decision.winner_adapter_id != "adapter-a":
            raise ProofContractError("K3 governed context must select adapter-a")
        selected = release_by_id[decision.winner_adapter_id]
        prior = release_by_id["adapter-b"]
        now = datetime.now(UTC)
        expiry = now + timedelta(minutes=15)
        approval = exact_approval_subject(
            manifest_hash=manifest.manifest_hash,
            environment_fingerprint=observation.environment_fingerprint,
            decision_hash=decision.decision_hash,
            release=selected,
            datahub_owner_urn=SUPPORT_OWNER_URN,
            actor_id=OWNER_ACTOR_ID,
            actor_role="DATA_OWNER",
            expires_at=expiry,
        )
        async with open_session() as session:
            decisive_reread = await read_stable(session)
            anchor_urn = await create_receipt_anchor(
                session, title=f"SIRA verified proof {approval.subject_hash[-12:]}"
            )
        decisive_manifest = compile_manifest(decisive_reread)
        assert_current_approval(
            subject=approval,
            approved_subject_hash=approval.subject_hash,
            actor_id=OWNER_ACTOR_ID,
            actor_role="DATA_OWNER",
            owner_actor_mapping=OWNER_ACTOR_MAPPING,
            current_environment_fingerprint=decisive_reread.environment_fingerprint,
            current_manifest_hash=decisive_manifest.manifest_hash,
            current_adapter_digest=selected.artifact_digest,
            expires_at=expiry,
            revoked_at=None,
            now=now,
        )
        successful_effect = await asyncio.to_thread(
            _effect,
            {
                "operation": "apply",
                "targetAdapterId": selected.adapter_id,
                "targetDigest": selected.artifact_digest,
                "expectedPriorDigest": prior.artifact_digest,
                "trialId": f"effect-{approval.subject_hash[-12:]}",
                "nonce": f"nonce-{approval.subject_hash[-16:]}",
            },
        )
        active_a = True
        async with open_session() as session:
            post_effect = await read_stable(session)
        if post_effect.environment_fingerprint != observation.environment_fingerprint:
            raise ProofContractError("POST_EFFECT_DATAHUB_DRIFT")
        if simulate_writeback_failure:
            rollback = await asyncio.to_thread(
                _effect,
                {
                    "operation": "rollback",
                    "targetAdapterId": prior.adapter_id,
                    "targetDigest": prior.artifact_digest,
                    "expectedPriorDigest": selected.artifact_digest,
                    "trialId": f"writeback-failure-{approval.subject_hash[-12:]}",
                    "nonce": f"writeback-failure-nonce-{approval.subject_hash[-12:]}",
                },
            )
            active_a = False
            return {
                "status": "PASS",
                "scenario": "DATAHUB_WRITEBACK_FAILURE",
                "effect": successful_effect,
                "writeback": {
                    "status": "FAILED",
                    "safeErrorCode": "DATAHUB_WRITEBACK_INJECTED_FAILURE",
                    "anchorUrn": anchor_urn,
                    "receiptIssued": False,
                },
                "recovery": {
                    "status": "ROLLBACK_VERIFIED",
                    "rollback": rollback,
                    "currentAdapterDigest": rollback["verifiedState"]["activeDigest"],
                },
            }
        projection = {
            "schemaVersion": "DataHubProofReceiptProjection/v0",
            "manifestHash": manifest.manifest_hash,
            "decisionHash": decision.decision_hash,
            "approvalSubjectHash": approval.subject_hash,
            "verifiedAdapterDigest": selected.artifact_digest,
            "routeStateAtVerification": "ACTIVE_VERIFIED",
            "verifiedRouteVersion": successful_effect["verifiedState"]["version"],
            "environmentFingerprint": observation.environment_fingerprint,
        }
        projection_hash = content_hash(projection)
        receipt = build_receipt_core(
            observation_hash=observation.semantic_hash,
            environment_fingerprint=observation.environment_fingerprint,
            manifest_hash=manifest.manifest_hash,
            trial_result_hashes={
                verdict.adapter_id: verdict.result_hash for verdict in decision.verdicts
            },
            decision_hash=decision.decision_hash,
            approval_subject_hash=approval.subject_hash,
            datahub_owner_urn=SUPPORT_OWNER_URN,
            adapter_projection_hash=selected.projection_hash,
            tested_adapter_digest=selected.artifact_digest,
            selected_adapter_digest=selected.artifact_digest,
            approved_adapter_digest=selected.artifact_digest,
            healthy_adapter_digest=successful_effect["health"]["artifactDigest"],
            active_adapter_digest=successful_effect["verifiedState"]["activeDigest"],
            prior_adapter_digest=prior.artifact_digest,
            prior_route_version=successful_effect["priorState"]["version"],
            verified_route_version=successful_effect["verifiedState"]["version"],
            routed_traffic_result_hash=successful_effect["routedTrafficResultHash"],
            route_state_at_verification="ACTIVE_VERIFIED",
            datahub_anchor_urn=anchor_urn,
            datahub_projection_hash=projection_hash,
        )
        async with open_session() as session:
            await publish_receipt_projection(
                session,
                anchor_urn=anchor_urn,
                title=f"SIRA verified proof {receipt.core_hash[-12:]}",
                core_hash=receipt.core_hash,
                projection=projection,
            )
        reread = await reread_receipt_projection(anchor_urn, core_hash=receipt.core_hash)
        rollback = await asyncio.to_thread(
            _effect,
            {
                "operation": "rollback",
                "targetAdapterId": prior.adapter_id,
                "targetDigest": prior.artifact_digest,
                "expectedPriorDigest": selected.artifact_digest,
                "trialId": f"rollback-{approval.subject_hash[-12:]}",
                "nonce": f"rollback-nonce-{approval.subject_hash[-12:]}",
            },
        )
        active_a = False
        return {
            "status": "PASS",
            "approvalSubjectHash": approval.subject_hash,
            "effect": successful_effect,
            "receipt": {"coreHash": receipt.core_hash, "payload": receipt.payload},
            "dataHubWriteback": {
                "anchorUrn": anchor_urn,
                "projectionHash": projection_hash,
                "rereadMatched": receipt.core_hash in json.dumps(reread, sort_keys=True),
            },
            "rollback": rollback,
            "historicalTruth": {
                "verifiedAdapterDigest": selected.artifact_digest,
                "routeStateAtVerification": "ACTIVE_VERIFIED",
                "currentRouteAfterRollback": prior.artifact_digest,
            },
            "campaign": campaign,
        }
    finally:
        if active_a and successful_effect is not None:
            try:
                await asyncio.to_thread(
                    _effect,
                    {
                        "operation": "rollback",
                        "targetAdapterId": "adapter-b",
                        "targetDigest": release_by_id["adapter-b"].artifact_digest,
                        "expectedPriorDigest": release_by_id["adapter-a"].artifact_digest,
                        "trialId": "failure-recovery-rollback",
                        "nonce": "failure-recovery-nonce",
                    },
                )
            except Exception:
                LOGGER.exception("Emergency router rollback failed")
        if pii_removed:
            await _set_pii(True)
