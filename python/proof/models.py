"""Immutable value objects for the causal proof kernel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True, order=True)
class DependencyRow:
    urn: str
    aspect: str
    field_path: str
    observed_hash: str

    def to_dict(self) -> dict[str, str]:
        return {
            "urn": self.urn,
            "aspect": self.aspect,
            "fieldPath": self.field_path,
            "observedHash": self.observed_hash,
        }


@dataclass(frozen=True, slots=True)
class EnvironmentObservation:
    root_urn: str
    profile_urn: str
    root_fields: tuple[str, ...]
    profile_fields: tuple[str, ...]
    upstream_urns: tuple[str, ...]
    owner_urns: tuple[str, ...]
    allowed_regions: tuple[str, ...]
    pii_present: bool
    dependencies: tuple[DependencyRow, ...]
    environment_fingerprint: str
    semantic_hash: str
    read_attempts: int

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "rootUrn": self.root_urn,
            "profileUrn": self.profile_urn,
            "rootFields": list(self.root_fields),
            "profileFields": list(self.profile_fields),
            "upstreamUrns": list(self.upstream_urns),
            "ownerUrns": list(self.owner_urns),
            "allowedRegions": list(self.allowed_regions),
            "piiPresent": self.pii_present,
            "dependencies": [row.to_dict() for row in self.dependencies],
        }


@dataclass(frozen=True, slots=True)
class ManifestGate:
    rule_id: str
    gate_id: str
    dependency_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ruleId": self.rule_id,
            "gateId": self.gate_id,
            "dependencyPaths": list(self.dependency_paths),
        }


@dataclass(frozen=True, slots=True)
class EvaluationManifest:
    compiler_version: str
    policy_version: str
    environment_fingerprint: str
    observation_hash: str
    gates: tuple[ManifestGate, ...]
    allowed_execution_regions: tuple[str, ...]
    required_input_fields: tuple[str, ...]
    activation_owner_urn: str
    seller_safe_payload: dict[str, Any]
    manifest_hash: str

    def hash_payload(self) -> dict[str, Any]:
        return {
            "compilerVersion": self.compiler_version,
            "policyVersion": self.policy_version,
            "environmentFingerprint": self.environment_fingerprint,
            "observationHash": self.observation_hash,
            "gates": [gate.to_dict() for gate in self.gates],
            "allowedExecutionRegions": list(self.allowed_execution_regions),
            "requiredInputFields": list(self.required_input_fields),
            "activationOwnerUrn": self.activation_owner_urn,
            "sellerSafePayload": self.seller_safe_payload,
        }


@dataclass(frozen=True, slots=True)
class CandidateVerdict:
    adapter_id: str
    eligible: bool
    failed_gate_ids: tuple[str, ...]
    declared_price: str
    result_hash: str
    artifact_digest: str


@dataclass(frozen=True, slots=True)
class CampaignDecision:
    manifest_hash: str
    winner_adapter_id: str
    verdicts: tuple[CandidateVerdict, ...]
    decision_graph_selected_plan_id: str
    decision_graph_evaluation_hash: str
    decision_hash: str


class ProofContractError(RuntimeError):
    """A required causal proof invariant was absent or ambiguous."""
