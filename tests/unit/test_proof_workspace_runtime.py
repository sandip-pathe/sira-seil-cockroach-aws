from __future__ import annotations

import json
from pathlib import Path

import pytest
from sira_api.errors import ApiProblem
from sira_api.proof_runtime import ProofWorkspaceRuntime


def _workspace() -> dict[str, object]:
    digest = "sha256:" + "a" * 64
    return {
        "schema_version": "ProofWorkspace/v0",
        "run_id": "proof-test",
        "overall_status": "COMPLETE",
        "context": {
            "status": "VERIFIED",
            "datahub_status": "LIVE_CAUSAL_AUTHORITY",
            "environment_fingerprint": digest,
            "observation_hash": digest,
            "manifest_hash": digest,
            "decisive_fact": "PII tag",
            "decisive_fact_state": "ABSENT",
            "causal_sequence": ["adapter-b", "adapter-a", "adapter-b"],
            "requirements": ["RAW_PII_EGRESS_FORBIDDEN"],
        },
        "proof_run": {
            "status": "VERIFIED",
            "winner_adapter_id": "adapter-a",
            "decision_hash": digest,
            "decision_graph_evaluation_hash": digest,
            "negative_control_passed": True,
            "candidates": [],
        },
        "authority": {
            "status": "CONSUMED",
            "actor_role": "DATA_OWNER",
            "datahub_owner_urn": "urn:li:corpGroup:support-data-owners",
            "approval_subject_hash": digest,
            "approved_adapter_digest": digest,
            "pre_effect_reread_matched": True,
        },
        "activation": {
            "status": "ACTIVE_VERIFIED",
            "tested_adapter_digest": digest,
            "selected_adapter_digest": digest,
            "healthy_adapter_digest": digest,
            "active_adapter_digest": digest,
            "prior_adapter_digest": "sha256:" + "b" * 64,
            "prior_route_version": 1,
            "verified_route_version": 2,
            "routed_traffic_result_hash": digest,
            "routed_adapter_id": "adapter-a",
        },
        "receipt": {
            "status": "REREAD_VERIFIED",
            "core_hash": digest,
            "datahub_anchor_urn": "urn:li:document:proof-test",
            "datahub_projection_hash": digest,
            "reread_matched": True,
            "historical_route_state": "ACTIVE_VERIFIED",
        },
        "recovery": {
            "status": "RESTORED",
            "pii_present": True,
            "control_tag_absent": True,
            "current_adapter_digest": "sha256:" + "b" * 64,
            "writeback_failure": None,
        },
        "trace": [{"label": "Receipt", "value": digest}],
        "summary": "Verified and restored.",
    }


def test_runtime_reads_only_a_typed_complete_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "workspace.json"
    artifact.write_text(json.dumps(_workspace()), encoding="utf-8")
    monkeypatch.setenv("SIRA_PROOF_WORKSPACE_ARTIFACT", str(artifact))
    runtime = ProofWorkspaceRuntime(tmp_path)

    workspace = runtime.workspace()

    assert workspace.overall_status == "COMPLETE"
    assert runtime.runner()["status"] == "COMPLETE"


def test_runtime_fails_closed_when_artifact_is_missing(tmp_path: Path) -> None:
    runtime = ProofWorkspaceRuntime(tmp_path)

    with pytest.raises(ApiProblem, match="PROOF_RUN_NOT_FOUND"):
        runtime.workspace()
