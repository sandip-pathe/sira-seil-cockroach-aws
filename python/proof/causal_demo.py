"""Live K1 B-A-B causal proof over DataHub MCP and isolated adapters."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

from domain.hashing import content_hash

from .constants import (
    CANARY_MARKER,
    COMPILER_VERSION,
    CONTROL_TAG_URN,
    PII_TAG_URN,
    POLICY_VERSION,
    PROFILE_DATASET_URN,
    ROOT_DATASET_URN,
)
from .datahub_mcp import (
    open_session,
    read_stable,
    set_field_tag,
    wait_for_field_tag,
    wait_for_pii,
)
from .exchange import CandidateRelease
from .manifest_v0 import compile_manifest, evaluate_campaign
from .models import CampaignDecision, EnvironmentObservation, EvaluationManifest

RUNTIME_COMPOSE = Path("infra/datahub/k0/compose.runtime.yaml")


def _manifest_payload(manifest: EvaluationManifest) -> dict[str, Any]:
    return {**manifest.hash_payload(), "manifestHash": manifest.manifest_hash}


def _run_campaign(
    manifest: EvaluationManifest, releases: tuple[CandidateRelease, ...] | None
) -> tuple[CampaignDecision, dict[str, Any]]:
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker is required for the isolated K1 campaign")
    environment = os.environ.copy()
    for key, image in (
        ("ADAPTER_A_DIGEST", "sira-proof-adapter-a:k0"),
        ("ADAPTER_B_DIGEST", "sira-proof-adapter-b:k0"),
    ):
        inspected = subprocess.run(  # noqa: S603 - executable and image names are fixed
            [docker, "image", "inspect", "--format", "{{.Id}}", image],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        if inspected.returncode != 0 or not inspected.stdout.strip().startswith("sha256:"):
            raise RuntimeError(f"isolated campaign image is missing: {image}")
        environment[key] = inspected.stdout.strip()
    completed = subprocess.run(  # noqa: S603 - executable and arguments are fixed locally
        [
            docker,
            "compose",
            "-f",
            str(RUNTIME_COMPOSE),
            "exec",
            "-T",
            "-e",
            f"ADAPTER_A_DIGEST={environment['ADAPTER_A_DIGEST']}",
            "-e",
            f"ADAPTER_B_DIGEST={environment['ADAPTER_B_DIGEST']}",
            "router",
            "python",
            "/app/campaign_probe.py",
        ],
        input=json.dumps(_manifest_payload(manifest), sort_keys=True),
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"isolated campaign failed: {detail}")
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict) or payload.get("status") != "PASS":
        raise RuntimeError("isolated campaign returned an invalid contract")
    results = payload.get("results")
    if not isinstance(results, dict):
        raise RuntimeError("isolated campaign omitted candidate results")
    decision = evaluate_campaign(manifest, results, releases=releases)
    return decision, payload


def _run_record(
    label: str,
    observation: EnvironmentObservation,
    manifest: EvaluationManifest,
    decision: CampaignDecision,
    campaign: dict[str, Any],
) -> dict[str, Any]:
    return {
        "label": label,
        "piiPresent": observation.pii_present,
        "environmentFingerprint": observation.environment_fingerprint,
        "observationHash": observation.semantic_hash,
        "manifestHash": manifest.manifest_hash,
        "emittedGateIds": [gate.gate_id for gate in manifest.gates],
        "winnerAdapterId": decision.winner_adapter_id,
        "decisionHash": decision.decision_hash,
        "decisionGraphSelectedPlanId": decision.decision_graph_selected_plan_id,
        "decisionGraphEvaluationHash": decision.decision_graph_evaluation_hash,
        "verdicts": [asdict(verdict) for verdict in decision.verdicts],
        "runtimeResults": campaign["results"],
    }


async def _compile_and_run(
    label: str,
    releases: tuple[CandidateRelease, ...] | None,
) -> tuple[
    EnvironmentObservation,
    EvaluationManifest,
    CampaignDecision,
    dict[str, Any],
]:
    async with open_session() as session:
        observation = await read_stable(session)
    manifest = compile_manifest(observation)
    decision, campaign = await asyncio.to_thread(_run_campaign, manifest, releases)
    return (
        observation,
        manifest,
        decision,
        _run_record(label, observation, manifest, decision, campaign),
    )


async def run_causal_proof(
    *, releases: tuple[CandidateRelease, ...] | None = None
) -> dict[str, Any]:
    baseline: (
        tuple[
            EnvironmentObservation,
            EvaluationManifest,
            CampaignDecision,
            dict[str, Any],
        ]
        | None
    ) = None
    control_added = False
    pii_removed = False
    recovery_errors: list[str] = []
    runs: list[dict[str, Any]] = []
    try:
        async with open_session() as session:
            await set_field_tag(
                session,
                entity_urn=PROFILE_DATASET_URN,
                column_path="email",
                tag_urn=PII_TAG_URN,
                present=True,
            )
            await wait_for_pii(session, present=True)
        baseline = await _compile_and_run("baseline-pii-present", releases)
        if baseline[2].winner_adapter_id != "adapter-b":
            raise RuntimeError("baseline must select adapter-b")
        runs.append(baseline[3])

        async with open_session() as session:
            await set_field_tag(
                session,
                entity_urn=ROOT_DATASET_URN,
                column_path="ticket_id",
                tag_urn=CONTROL_TAG_URN,
                present=True,
            )
            control_added = True
            await wait_for_field_tag(
                session,
                entity_urn=ROOT_DATASET_URN,
                column_path="ticket_id",
                tag_name="SIRA_K1_CONTROL",
                present=True,
            )
        negative = await _compile_and_run("unrelated-governed-change", releases)
        if (
            negative[0].environment_fingerprint != baseline[0].environment_fingerprint
            or negative[1].manifest_hash != baseline[1].manifest_hash
            or negative[2].decision_hash != baseline[2].decision_hash
        ):
            raise RuntimeError("unrelated governed change altered the accepted proof inputs")
        runs.append(negative[3])
        async with open_session() as session:
            await set_field_tag(
                session,
                entity_urn=ROOT_DATASET_URN,
                column_path="ticket_id",
                tag_urn=CONTROL_TAG_URN,
                present=False,
            )
            await wait_for_field_tag(
                session,
                entity_urn=ROOT_DATASET_URN,
                column_path="ticket_id",
                tag_name="SIRA_K1_CONTROL",
                present=False,
            )
            control_added = False

        async with open_session() as session:
            await set_field_tag(
                session,
                entity_urn=PROFILE_DATASET_URN,
                column_path="email",
                tag_urn=PII_TAG_URN,
                present=False,
            )
            pii_removed = True
            await wait_for_pii(session, present=False)
        mutation = await _compile_and_run("pii-removed", releases)
        if mutation[2].winner_adapter_id != "adapter-a":
            raise RuntimeError("removing PII must select adapter-a")
        if mutation[1].manifest_hash == baseline[1].manifest_hash:
            raise RuntimeError("PII mutation did not change the frozen manifest")
        runs.append(mutation[3])

        async with open_session() as session:
            await set_field_tag(
                session,
                entity_urn=PROFILE_DATASET_URN,
                column_path="email",
                tag_urn=PII_TAG_URN,
                present=True,
            )
            await wait_for_pii(session, present=True)
            pii_removed = False
        restored = await _compile_and_run("pii-restored", releases)
        if restored[2].winner_adapter_id != "adapter-b":
            raise RuntimeError("restoring PII must select adapter-b")
        if (
            restored[0].environment_fingerprint != baseline[0].environment_fingerprint
            or restored[1].manifest_hash != baseline[1].manifest_hash
            or restored[2].decision_hash != baseline[2].decision_hash
        ):
            raise RuntimeError("restored DataHub context did not reproduce baseline hashes")
        runs.append(restored[3])
    finally:
        try:
            async with open_session() as session:
                if control_added:
                    await set_field_tag(
                        session,
                        entity_urn=ROOT_DATASET_URN,
                        column_path="ticket_id",
                        tag_urn=CONTROL_TAG_URN,
                        present=False,
                    )
                    await wait_for_field_tag(
                        session,
                        entity_urn=ROOT_DATASET_URN,
                        column_path="ticket_id",
                        tag_name="SIRA_K1_CONTROL",
                        present=False,
                    )
                if pii_removed:
                    await set_field_tag(
                        session,
                        entity_urn=PROFILE_DATASET_URN,
                        column_path="email",
                        tag_urn=PII_TAG_URN,
                        present=True,
                    )
                    await wait_for_pii(session, present=True)
        except Exception as exc:  # Recovery evidence must survive the original failure.
            recovery_errors.append(f"{type(exc).__name__}: {exc}")
    if recovery_errors:
        raise RuntimeError(f"RECOVERY_REQUIRED: {'; '.join(recovery_errors)}")
    if baseline is None:
        raise RuntimeError("causal proof did not establish a baseline")
    fixed_inputs = {
        "compilerVersion": COMPILER_VERSION,
        "policyVersion": POLICY_VERSION,
        "canaryMarkerHash": content_hash(CANARY_MARKER),
        "adapterArtifactDigests": {
            verdict.adapter_id: verdict.artifact_digest for verdict in baseline[2].verdicts
        },
        "buyerProjectionHashes": (
            {release.adapter_id: release.projection_hash for release in releases}
            if releases is not None
            else None
        ),
    }
    return {
        "status": "PASS",
        "causalSequence": [run["winnerAdapterId"] for run in runs if "pii" in run["label"]],
        "negativeControl": {
            "mutation": "root.ticket_id tag SIRA_K1_CONTROL added then removed",
            "tagObservedBeforeEvaluation": True,
            "acceptedFingerprintUnchanged": True,
            "manifestHashUnchanged": True,
            "decisionHashUnchanged": True,
        },
        "fixedInputs": fixed_inputs,
        "fixedInputsHash": content_hash(fixed_inputs),
        "runs": runs,
        "recovery": {"piiPresent": True, "controlTagAbsent": True},
    }
