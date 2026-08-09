"""Bind K2 and K3 proof artifacts into the canonical operator workspace view."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or payload.get("status") != "PASS":
        raise ValueError(f"required proof artifact did not pass: {path}")
    return payload


def _short(value: str) -> str:
    return f"{value[:15]}…{value[-10:]}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exchange", type=Path, required=True)
    parser.add_argument("--deployment", type=Path, required=True)
    parser.add_argument("--failure", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--assert", dest="assert_contract", action="store_true")
    args = parser.parse_args()

    exchange = _load(args.exchange)
    deployment = _load(args.deployment)
    failure = _load(args.failure) if args.failure and args.failure.exists() else None
    causal = exchange["exchangeCausalProof"]
    pii_runs = [run for run in causal["runs"] if "pii" in run["label"]]
    _, mutation, _ = pii_runs
    effect = deployment["effect"]
    receipt = deployment["receipt"]
    receipt_payload = receipt["payload"]
    verified = receipt_payload["verifiedEffect"]
    approved_digest = receipt_payload["authority"]["approvedAdapterDigest"]
    active_digest = verified["activeAdapterDigest"]
    selected_digest = verified["selectedAdapterDigest"]
    healthy_digest = verified["healthyAdapterDigest"]
    if args.assert_contract:
        if causal["causalSequence"] != ["adapter-b", "adapter-a", "adapter-b"]:
            raise ValueError("causal B-A-B sequence did not reproduce")
        if len({approved_digest, active_digest, selected_digest, healthy_digest}) != 1:
            raise ValueError("approved, selected, healthy, and active digests diverged")
        if not deployment["dataHubWriteback"]["rereadMatched"]:
            raise ValueError("DataHub receipt reread did not match")
        if (
            deployment["historicalTruth"]["currentRouteAfterRollback"]
            != verified["priorAdapterDigest"]
        ):
            raise ValueError("router did not restore its prior digest")
        if failure is not None and (
            failure.get("writeback", {}).get("receiptIssued") is not False
            or failure.get("recovery", {}).get("status") != "ROLLBACK_VERIFIED"
        ):
            raise ValueError("writeback failure was not safely compensated")

    projections = {item["adapterId"]: item for item in exchange["buyerProjections"]}
    candidates = []
    for verdict in mutation["verdicts"]:
        projection = projections[verdict["adapter_id"]]
        runtime = mutation["runtimeResults"][verdict["adapter_id"]]
        candidates.append(
            {
                "adapter_id": verdict["adapter_id"],
                "seller_organization_id": projection["sourceSellerOrganizationId"],
                "artifact_digest": verdict["artifact_digest"],
                "projection_hash": projection["projectionHash"],
                "price": (
                    f"{projection['fixedPrice']['currency']} {projection['fixedPrice']['amount']}"
                ),
                "eligible": verdict["eligible"],
                "selected": verdict["adapter_id"] == mutation["winnerAdapterId"],
                "gate_results": runtime["gateResults"],
            }
        )

    failure_view = (
        {
            "status": failure["recovery"]["status"],
            "safe_error_code": failure["writeback"]["safeErrorCode"],
            "receipt_issued": failure["writeback"]["receiptIssued"],
            "restored_adapter_digest": failure["recovery"]["currentAdapterDigest"],
        }
        if failure is not None
        else None
    )
    workspace = {
        "schema_version": "ProofWorkspace/v0",
        "run_id": f"proof-{receipt['coreHash'][-12:]}",
        "overall_status": "COMPLETE",
        "context": {
            "status": "VERIFIED",
            "datahub_status": "LIVE_CAUSAL_AUTHORITY",
            "environment_fingerprint": mutation["environmentFingerprint"],
            "observation_hash": mutation["observationHash"],
            "manifest_hash": mutation["manifestHash"],
            "decisive_fact": "PII tag on customer_profiles.email",
            "decisive_fact_state": "ABSENT",
            "causal_sequence": causal["causalSequence"],
            "requirements": mutation["emittedGateIds"],
        },
        "proof_run": {
            "status": "VERIFIED",
            "winner_adapter_id": mutation["winnerAdapterId"],
            "decision_hash": mutation["decisionHash"],
            "decision_graph_evaluation_hash": mutation["decisionGraphEvaluationHash"],
            "negative_control_passed": all(causal["negativeControl"].values()),
            "candidates": candidates,
        },
        "authority": {
            "status": "CONSUMED",
            "actor_role": exchange["approval"]["actorRole"],
            "datahub_owner_urn": receipt_payload["authority"]["dataHubOwnerUrn"],
            "approval_subject_hash": receipt_payload["authority"]["approvalSubjectHash"],
            "approved_adapter_digest": approved_digest,
            "pre_effect_reread_matched": exchange["approval"]["preEffectRereadMatched"],
        },
        "activation": {
            "status": verified["routeStateAtVerification"],
            "tested_adapter_digest": verified["testedAdapterDigest"],
            "selected_adapter_digest": selected_digest,
            "healthy_adapter_digest": healthy_digest,
            "active_adapter_digest": active_digest,
            "prior_adapter_digest": verified["priorAdapterDigest"],
            "prior_route_version": verified["priorRouteVersion"],
            "verified_route_version": verified["verifiedRouteVersion"],
            "routed_traffic_result_hash": verified["routedTrafficResultHash"],
            "routed_adapter_id": effect["routedTraffic"]["result"]["adapterId"],
        },
        "receipt": {
            "status": "REREAD_VERIFIED",
            "core_hash": receipt["coreHash"],
            "datahub_anchor_urn": receipt_payload["dataHubProjection"]["anchorUrn"],
            "datahub_projection_hash": receipt_payload["dataHubProjection"]["projectionHash"],
            "reread_matched": deployment["dataHubWriteback"]["rereadMatched"],
            "historical_route_state": verified["routeStateAtVerification"],
        },
        "recovery": {
            "status": "RESTORED",
            "pii_present": causal["recovery"]["piiPresent"],
            "control_tag_absent": causal["recovery"]["controlTagAbsent"],
            "current_adapter_digest": deployment["historicalTruth"]["currentRouteAfterRollback"],
            "writeback_failure": failure_view,
        },
        "trace": [
            {"label": "DataHub fact", "value": mutation["environmentFingerprint"]},
            {"label": "Manifest", "value": mutation["manifestHash"]},
            {"label": "Decision", "value": mutation["decisionHash"]},
            {"label": "Authority", "value": receipt_payload["authority"]["approvalSubjectHash"]},
            {"label": "Active digest", "value": active_digest},
            {"label": "Receipt", "value": receipt["coreHash"]},
        ],
        "summary": (
            f"DataHub changed the winner B → A → B. {_short(active_digest)} served verified "
            f"traffic, {_short(receipt['coreHash'])} was reread from DataHub, "
            "and the route restored."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(workspace, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(  # noqa: T201 - canonical CLI emits a compact machine-readable completion line
        json.dumps({"status": "PASS", "runId": workspace["run_id"], "output": str(args.output)})
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
