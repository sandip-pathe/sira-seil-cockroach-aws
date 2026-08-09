"""Typed operator contract for the DataHub-causal proof workspace."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ProofContextView(BaseModel):
    status: Literal["VERIFIED"]
    datahub_status: Literal["LIVE_CAUSAL_AUTHORITY"]
    environment_fingerprint: str
    observation_hash: str
    manifest_hash: str
    decisive_fact: str
    decisive_fact_state: str
    causal_sequence: list[str]
    requirements: list[str]


class ProofCandidateView(BaseModel):
    adapter_id: str
    seller_organization_id: str
    artifact_digest: str
    projection_hash: str
    price: str
    eligible: bool
    selected: bool
    gate_results: dict[str, bool]


class ProofRunView(BaseModel):
    status: Literal["VERIFIED"]
    winner_adapter_id: str
    decision_hash: str
    decision_graph_evaluation_hash: str
    negative_control_passed: bool
    candidates: list[ProofCandidateView]


class ProofAuthorityView(BaseModel):
    status: Literal["CONSUMED"]
    actor_role: str
    datahub_owner_urn: str
    approval_subject_hash: str
    approved_adapter_digest: str
    pre_effect_reread_matched: bool


class ProofActivationView(BaseModel):
    status: Literal["ACTIVE_VERIFIED"]
    tested_adapter_digest: str
    selected_adapter_digest: str
    healthy_adapter_digest: str
    active_adapter_digest: str
    prior_adapter_digest: str
    prior_route_version: int
    verified_route_version: int
    routed_traffic_result_hash: str
    routed_adapter_id: str


class ProofReceiptView(BaseModel):
    status: Literal["REREAD_VERIFIED"]
    core_hash: str
    datahub_anchor_urn: str
    datahub_projection_hash: str
    reread_matched: bool
    historical_route_state: str


class ProofFailureRecoveryView(BaseModel):
    status: Literal["ROLLBACK_VERIFIED"]
    safe_error_code: str
    receipt_issued: bool
    restored_adapter_digest: str


class ProofRecoveryView(BaseModel):
    status: Literal["RESTORED"]
    pii_present: bool
    control_tag_absent: bool
    current_adapter_digest: str
    writeback_failure: ProofFailureRecoveryView | None = None


class ProofTraceItemView(BaseModel):
    label: str
    value: str


class ProofWorkspaceView(BaseModel):
    schema_version: Literal["ProofWorkspace/v0"]
    run_id: str
    overall_status: Literal["COMPLETE"]
    context: ProofContextView
    proof_run: ProofRunView
    authority: ProofAuthorityView
    activation: ProofActivationView
    receipt: ProofReceiptView
    recovery: ProofRecoveryView
    trace: list[ProofTraceItemView]
    summary: str


class ProofRunnerView(BaseModel):
    status: Literal["IDLE", "RUNNING", "COMPLETE", "FAILED"]
    run_id: str | None = None
    safe_error_code: str | None = None
    artifact_path: str
    next_command: str | None = None
