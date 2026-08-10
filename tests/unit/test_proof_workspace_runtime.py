from __future__ import annotations

import json
from pathlib import Path

import pytest
from sira_api.errors import ApiProblem
from sira_api.proof_runtime import ProofWorkspaceRuntime

from domain.hashing import content_hash


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


def _digest(character: str) -> str:
    return "sha256:" + character * 64


def _run(
    *,
    label: str,
    pii_present: bool,
    winner: str,
    decision_hash: str,
    observation_hash: str,
    environment_fingerprint: str,
    manifest_hash: str,
) -> dict[str, object]:
    root_urn = "urn:li:dataset:(urn:li:dataPlatform:postgres,support_summary,PROD)"
    profile_urn = "urn:li:dataset:(urn:li:dataPlatform:postgres,customer_profile,PROD)"
    safe_context = {
        "rootUrn": root_urn,
        "profileUrn": profile_urn,
        "rootFields": ["ticket_id", "summary"],
        "profileFields": ["customer_email"],
        "upstreamUrns": [profile_urn],
        "ownerUrns": ["urn:li:corpGroup:support-data-owners"],
        "allowedRegions": ["EU"],
        "piiPresent": pii_present,
        "dependencies": [],
    }
    source_details = [
        {
            "urn": root_urn,
            "label": "Support schema",
            "fact": "schemaFields",
            "value": ["ticket_id", "summary"],
        },
        {
            "urn": root_urn,
            "label": "Support lineage",
            "fact": "upstreamDatasets",
            "value": [profile_urn],
        },
        {
            "urn": root_urn,
            "label": "Data owners",
            "fact": "ownerUrns",
            "value": ["urn:li:corpGroup:support-data-owners"],
        },
        {
            "urn": profile_urn,
            "label": "Profile schema",
            "fact": "schemaFields",
            "value": ["customer_email"],
        },
        {"urn": profile_urn, "label": "Allowed regions", "fact": "allowedRegions", "value": ["EU"]},
        {
            "urn": profile_urn,
            "label": "Email classification",
            "fact": "emailPiiTagged",
            "value": pii_present,
        },
    ]
    gate_ids = ["EXECUTION_REGION_ALLOWED", "REQUIRED_SCHEMA_SUPPORTED"]
    if pii_present:
        gate_ids.insert(0, "RAW_PII_EGRESS_FORBIDDEN")
    a_eligible = not pii_present
    return {
        "label": label,
        "piiPresent": pii_present,
        "environmentFingerprint": environment_fingerprint,
        "observationHash": observation_hash,
        "environmentObservation": {
            "schemaVersion": "EnvironmentObservationSafe/v0",
            "safeContext": safe_context,
            "sourceDetails": source_details,
            "semanticHash": observation_hash,
            "environmentFingerprint": environment_fingerprint,
            "readAttempts": 2,
        },
        "manifestHash": manifest_hash,
        "emittedGateIds": gate_ids,
        "winnerAdapterId": winner,
        "decisionHash": decision_hash,
        "decisionGraphSelectedPlanId": f"plan-{winner}",
        "decisionGraphEvaluationHash": _digest("e" if pii_present else "f"),
        "verdicts": [
            {
                "adapter_id": "adapter-a",
                "artifact_digest": _digest("1"),
                "eligible": a_eligible,
                "failed_gate_ids": [] if a_eligible else ["RAW_PII_EGRESS_FORBIDDEN"],
                "result_hash": _digest("3" if pii_present else "4"),
            },
            {
                "adapter_id": "adapter-b",
                "artifact_digest": _digest("2"),
                "eligible": True,
                "failed_gate_ids": [],
                "result_hash": _digest("5" if pii_present else "6"),
            },
        ],
    }


def _exchange() -> dict[str, object]:
    baseline = _run(
        label="baseline-pii-present",
        pii_present=True,
        winner="adapter-b",
        decision_hash=_digest("b"),
        observation_hash=_digest("7"),
        environment_fingerprint=_digest("8"),
        manifest_hash=_digest("9"),
    )
    unrelated = _run(
        label="unrelated-governed-change",
        pii_present=True,
        winner="adapter-b",
        decision_hash=_digest("b"),
        observation_hash=_digest("7"),
        environment_fingerprint=_digest("8"),
        manifest_hash=_digest("9"),
    )
    counterfactual = _run(
        label="pii-removed",
        pii_present=False,
        winner="adapter-a",
        decision_hash=_digest("c"),
        observation_hash=_digest("a"),
        environment_fingerprint=_digest("d"),
        manifest_hash=_digest("0"),
    )
    restored = _run(
        label="pii-restored",
        pii_present=True,
        winner="adapter-b",
        decision_hash=_digest("b"),
        observation_hash=_digest("7"),
        environment_fingerprint=_digest("8"),
        manifest_hash=_digest("9"),
    )
    projections = [
        {
            "adapterId": "adapter-a",
            "sourceSellerOrganizationId": "org-a",
            "sourcePackVersionId": "pack-a-v1",
            "projectionHash": _digest("a"),
            "artifactDigest": _digest("1"),
            "capabilities": ["SUPPORT_SUMMARIZATION"],
            "fixedPrice": {"currency": "USD", "amount": "0.02"},
        },
        {
            "adapterId": "adapter-b",
            "sourceSellerOrganizationId": "org-b",
            "sourcePackVersionId": "pack-b-v1",
            "projectionHash": _digest("f"),
            "artifactDigest": _digest("2"),
            "capabilities": ["SUPPORT_SUMMARIZATION", "PII_REDACTION"],
            "fixedPrice": {"currency": "USD", "amount": "0.05"},
        },
    ]
    restored_observation = restored["environmentObservation"]
    assert isinstance(restored_observation, dict)
    seller_evidence = []
    restored_verdicts = restored["verdicts"]
    assert isinstance(restored_verdicts, list)
    for projection, verdict in zip(projections, restored_verdicts, strict=True):
        seller_evidence.append(
            {
                **projection,
                "eligible": verdict["eligible"],
                "failedGateIds": verdict["failed_gate_ids"],
                "trialResultHash": verdict["result_hash"],
            }
        )
    payload = {
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
            "safeContext": restored_observation["safeContext"],
            "sourceDetails": restored_observation["sourceDetails"],
        },
        "sellerEvidence": seller_evidence,
        "counterfactual": {
            "sourceUrn": restored_observation["safeContext"]["profileUrn"],
            "fact": "customer_profile.email PII tag",
            "from": True,
            "to": False,
            "alternativeAdapterId": "adapter-a",
            "decisionHash": counterfactual["decisionHash"],
            "manifestHash": counterfactual["manifestHash"],
            "environmentFingerprint": counterfactual["environmentFingerprint"],
        },
        "causalVerification": {
            "sequence": ["adapter-b", "adapter-a", "adapter-b"],
            "baselineDecisionHash": baseline["decisionHash"],
            "restoredDecisionHash": restored["decisionHash"],
            "restoredBaselineMatched": True,
            "negativeControlPassed": True,
        },
    }
    return {
        "status": "PASS",
        "exchangeCausalProof": {
            "status": "PASS",
            "causalSequence": ["adapter-b", "adapter-a", "adapter-b"],
            "runs": [baseline, unrelated, counterfactual, restored],
            "negativeControl": {
                "mutation": "unrelated tag",
                "tagObservedBeforeEvaluation": True,
                "acceptedFingerprintUnchanged": True,
                "manifestHashUnchanged": True,
                "decisionHashUnchanged": True,
            },
            "recovery": {"piiPresent": True, "controlTagAbsent": True},
        },
        "buyerProjections": projections,
        "buyerDecisionReceipt": {
            "schemaVersion": "BuyerDecisionReceipt/v0",
            "coreHash": content_hash(payload),
            "decisionHash": restored["decisionHash"],
            "payload": payload,
            "dataHubWriteback": {
                "status": "REREAD_VERIFIED",
                "anchorUrn": "urn:li:document:sira-buyer-decision",
                "projectionHash": _digest("6"),
                "rereadMatched": True,
            },
        },
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


def test_runtime_projects_only_a_fully_bound_buyer_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace.json"
    workspace.write_text(json.dumps(_workspace()), encoding="utf-8")
    workspace.with_name("exchange-proof.json").write_text(json.dumps(_exchange()), encoding="utf-8")
    monkeypatch.setenv("SIRA_PROOF_WORKSPACE_ARTIFACT", str(workspace))

    decision = ProofWorkspaceRuntime(tmp_path).buyer_decision()

    assert decision["selected_adapter_id"] == "adapter-b"
    assert decision["counterfactual_adapter_id"] == "adapter-a"
    assert decision["receipt"]["reread_matched"] is True
    assert len(decision["datahub_context"]["source_details"]) == 6


def test_runtime_fails_closed_when_receipt_is_not_bound_to_current_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace.json"
    workspace.write_text(json.dumps(_workspace()), encoding="utf-8")
    exchange = _exchange()
    receipt = exchange["buyerDecisionReceipt"]
    assert isinstance(receipt, dict)
    receipt["decisionHash"] = _digest("f")
    workspace.with_name("exchange-proof.json").write_text(json.dumps(exchange), encoding="utf-8")
    monkeypatch.setenv("SIRA_PROOF_WORKSPACE_ARTIFACT", str(workspace))

    with pytest.raises(ApiProblem) as raised:
        ProofWorkspaceRuntime(tmp_path).buyer_decision()

    assert raised.value.code == "DATAHUB_DECISION_INVALID"
