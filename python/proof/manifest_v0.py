"""Pure four-rule compiler and deterministic campaign selector."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from domain.hashing import content_hash

from .constants import (
    CANDIDATE_PRICES,
    COMPILER_VERSION,
    POLICY_VERSION,
    PROFILE_DATASET_URN,
    PROFILE_REQUIRED_FIELDS,
    ROOT_REQUIRED_FIELDS,
    SUPPORT_OWNER_URN,
)
from .decision_bridge import evaluate_with_decision_graph
from .models import (
    CampaignDecision,
    CandidateVerdict,
    EnvironmentObservation,
    EvaluationManifest,
    ManifestGate,
    ProofContractError,
)


def compile_manifest(observation: EnvironmentObservation) -> EvaluationManifest:
    missing_root = sorted(set(ROOT_REQUIRED_FIELDS) - set(observation.root_fields))
    missing_profile = sorted(set(PROFILE_REQUIRED_FIELDS) - set(observation.profile_fields))
    if missing_root or missing_profile:
        raise ProofContractError(
            f"R-SCHEMA-01 missing fields: root={missing_root}, profile={missing_profile}"
        )
    if PROFILE_DATASET_URN not in observation.upstream_urns:
        raise ProofContractError("R-SCHEMA-01 profile lineage dependency is missing")
    if SUPPORT_OWNER_URN not in observation.owner_urns:
        raise ProofContractError("R-OWNER-01 governing owner is missing")
    if not observation.allowed_regions:
        raise ProofContractError("R-REGION-01 allowed execution regions are missing")

    gates = [
        ManifestGate(
            rule_id="R-REGION-01",
            gate_id="EXECUTION_REGION_ALLOWED",
            dependency_paths=("structuredProperties.io.sira.allowedExecutionRegions",),
        ),
        ManifestGate(
            rule_id="R-SCHEMA-01",
            gate_id="REQUIRED_SCHEMA_SUPPORTED",
            dependency_paths=(
                "root.schemaMetadata.fields",
                "profile.schemaMetadata.fields",
                "root.upstream.profile",
            ),
        ),
    ]
    if observation.pii_present:
        gates.append(
            ManifestGate(
                rule_id="R-PII-01",
                gate_id="RAW_PII_EGRESS_FORBIDDEN",
                dependency_paths=("profile.schemaMetadata.fields.email.tags.PII",),
            )
        )
    gates.sort(key=lambda gate: gate.rule_id)
    seller_safe = {
        "protocolVersion": "TrialCase/v0",
        "requirementIds": [gate.rule_id for gate in gates],
        "allowedExecutionRegions": list(observation.allowed_regions),
        "requiredInputFields": list(ROOT_REQUIRED_FIELDS),
    }
    payload = {
        "compilerVersion": COMPILER_VERSION,
        "policyVersion": POLICY_VERSION,
        "environmentFingerprint": observation.environment_fingerprint,
        "observationHash": observation.semantic_hash,
        "gates": [gate.to_dict() for gate in gates],
        "allowedExecutionRegions": list(observation.allowed_regions),
        "requiredInputFields": list(ROOT_REQUIRED_FIELDS),
        "activationOwnerUrn": SUPPORT_OWNER_URN,
        "sellerSafePayload": seller_safe,
    }
    return EvaluationManifest(
        compiler_version=COMPILER_VERSION,
        policy_version=POLICY_VERSION,
        environment_fingerprint=observation.environment_fingerprint,
        observation_hash=observation.semantic_hash,
        gates=tuple(gates),
        allowed_execution_regions=observation.allowed_regions,
        required_input_fields=ROOT_REQUIRED_FIELDS,
        activation_owner_urn=SUPPORT_OWNER_URN,
        seller_safe_payload=seller_safe,
        manifest_hash=content_hash(payload),
    )


def evaluate_campaign(
    manifest: EvaluationManifest, runtime_results: Mapping[str, Mapping[str, Any]]
) -> CampaignDecision:
    expected_gates = {
        "FUNCTIONAL_CANARY_PASSED",
        *(gate.gate_id for gate in manifest.gates),
    }
    verdicts: list[CandidateVerdict] = []
    for adapter_id, price in sorted(CANDIDATE_PRICES.items()):
        result = runtime_results.get(adapter_id)
        if result is None:
            raise ProofContractError(f"missing runtime result for {adapter_id}")
        if result.get("status") != "completed":
            failed = tuple(sorted(expected_gates | {"ADAPTER_RUNTIME_COMPLETED"}))
        else:
            gate_results = result.get("gateResults")
            if not isinstance(gate_results, dict):
                raise ProofContractError(f"invalid gate results for {adapter_id}")
            failed = tuple(
                sorted(gate for gate in expected_gates if gate_results.get(gate) is not True)
            )
        artifact_digest = result.get("artifactDigest")
        result_hash = result.get("resultHash")
        if not isinstance(artifact_digest, str) or not isinstance(result_hash, str):
            raise ProofContractError(f"missing immutable runtime identity for {adapter_id}")
        verdicts.append(
            CandidateVerdict(
                adapter_id=adapter_id,
                eligible=not failed,
                failed_gate_ids=failed,
                declared_price=price,
                result_hash=result_hash,
                artifact_digest=artifact_digest,
            )
        )
    winner_adapter_id, selected_plan_id, graph_hash = evaluate_with_decision_graph(
        manifest, tuple(verdicts)
    )
    decision_payload = {
        "manifestHash": manifest.manifest_hash,
        "winnerAdapterId": winner_adapter_id,
        "decisionGraphSelectedPlanId": selected_plan_id,
        "decisionGraphEvaluationHash": graph_hash,
        "verdicts": [
            {
                "adapterId": verdict.adapter_id,
                "eligible": verdict.eligible,
                "failedGateIds": list(verdict.failed_gate_ids),
                "declaredPrice": verdict.declared_price,
                "resultHash": verdict.result_hash,
                "artifactDigest": verdict.artifact_digest,
            }
            for verdict in verdicts
        ],
    }
    return CampaignDecision(
        manifest_hash=manifest.manifest_hash,
        winner_adapter_id=winner_adapter_id,
        verdicts=tuple(verdicts),
        decision_graph_selected_plan_id=selected_plan_id,
        decision_graph_evaluation_hash=graph_hash,
        decision_hash=content_hash(decision_payload),
    )
