"""Package one bounded, redacted proof run for evaluator inspection."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from domain.hashing import content_hash


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"artifact is not an object: {path}")
    return payload


def _git(*arguments: str) -> str:
    git = shutil.which("git")
    if git is None:
        raise ValueError("git is required to build the submission bundle")
    completed = subprocess.run(  # noqa: S603 - resolved executable and fixed local arguments
        [git, *arguments], text=True, capture_output=True, timeout=10, check=True
    )
    return completed.stdout.strip()


def _image_digest(image: str) -> str:
    docker = shutil.which("docker")
    if docker is None:
        raise ValueError("Docker is required to build the submission bundle")
    completed = subprocess.run(  # noqa: S603 - resolved executable and fixed image inspection
        [docker, "image", "inspect", "--format", "{{.Id}}", image],
        text=True,
        capture_output=True,
        timeout=10,
        check=True,
    )
    digest = completed.stdout.strip()
    if not digest.startswith("sha256:"):
        raise ValueError(f"image identity is unavailable: {image}")
    return digest


def _buyer_decision_state(exchange: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    receipt = exchange.get("buyerDecisionReceipt")
    causal = exchange.get("exchangeCausalProof")
    if not isinstance(receipt, dict) or not isinstance(causal, dict):
        raise ValueError("buyer decision receipt is missing")
    runs = causal.get("runs")
    if not isinstance(runs, list):
        raise ValueError("causal runs are missing")
    restored_runs = [
        run for run in runs if isinstance(run, dict) and run.get("label") == "pii-restored"
    ]
    if len(restored_runs) != 1:
        raise ValueError("exactly one restored buyer decision is required")
    payload = receipt.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("buyer decision receipt payload is missing")
    return receipt, restored_runs[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--assert", dest="assert_contract", action="store_true")
    args = parser.parse_args()
    root = args.artifacts.resolve()
    workspace = _load(root / "workspace.json")
    exchange = _load(root / "exchange-proof.json")
    deployment = _load(root / "deployment-proof.json")
    failure = _load(root / "writeback-failure-proof.json") if args.assert_contract else None
    timings = _load(root / "timings.json")
    receipt = deployment["receipt"]
    recovery = workspace["recovery"]

    buyer_receipt, restored_decision = _buyer_decision_state(exchange)
    buyer_payload = buyer_receipt["payload"]
    buyer_writeback = buyer_receipt.get("dataHubWriteback", {})
    buyer_recommendation = buyer_payload.get("recommendation", {})
    buyer_counterfactual = buyer_payload.get("counterfactual", {})
    buyer_core_bound = (
        buyer_receipt.get("schemaVersion") == "BuyerDecisionReceipt/v0"
        and buyer_payload.get("schemaVersion") == "BuyerDecisionEvidenceCore/v0"
        and content_hash(buyer_payload) == buyer_receipt.get("coreHash")
        and buyer_receipt.get("decisionHash") == restored_decision.get("decisionHash")
        and buyer_payload.get("decisionHash") == restored_decision.get("decisionHash")
        and buyer_recommendation.get("adapterId") == restored_decision.get("winnerAdapterId")
    )
    buyer_reread_verified = (
        isinstance(buyer_writeback, dict)
        and buyer_writeback.get("status") == "REREAD_VERIFIED"
        and buyer_writeback.get("rereadMatched") is True
    )

    release_safety = (
        recovery["status"] == "RESTORED"
        and failure is not None
        and failure["writeback"]["receiptIssued"] is False
        and failure["recovery"]["status"] == "ROLLBACK_VERIFIED"
        and timings["warmBudgetPassed"] is True
    )

    gates = {
        "G1_DATAHUB_RUNTIME": exchange["status"] == "PASS",
        "G2_CAUSAL_FLIP": workspace["context"]["causal_sequence"]
        == ["adapter-b", "adapter-a", "adapter-b"],
        "G3_SELLER_EVIDENCE_BOUNDARY": len(exchange["buyerProjections"]) == 2,
        "G4_BUYER_DECISION_BOUND": buyer_core_bound,
        "G5_BUYER_RECEIPT_REREAD": buyer_reread_verified,
        "G6_CONTEXT_RESTORED": recovery["status"] == "RESTORED"
        and restored_decision.get("winnerAdapterId") == "adapter-b",
        "G7_RELEASE_SAFETY": release_safety,
    }
    if args.assert_contract and not all(gates.values()):
        raise ValueError(f"submission bundle gates failed: {gates}")

    application_commit = _git("rev-parse", "HEAD")
    candidates = workspace["proof_run"]["candidates"]
    manifest = {
        "schemaVersion": "ProofBuildManifest/v0",
        "applicationCommit": application_commit,
        "workingTreeClean": _git("status", "--porcelain") == "",
        "dataHubCoreVersion": "1.7.0",
        "dataHubMcpVersion": "0.6.0",
        "protocolVersion": "TrialCase/v0",
        "workspaceSchemaVersion": workspace["schema_version"],
        "seedVersion": "datahub-k0-v1",
        "adapterImages": {
            candidate["adapter_id"]: candidate["artifact_digest"] for candidate in candidates
        },
        "routerImage": _image_digest("sira-proof-router:k0"),
        "pendingReconciliation": False,
        "semanticResultHash": content_hash(
            {
                "causalSequence": workspace["context"]["causal_sequence"],
                "currentWinner": restored_decision["winnerAdapterId"],
                "currentDecisionHash": restored_decision["decisionHash"],
                "buyerDecisionCoreHash": buyer_receipt["coreHash"],
                "counterfactualWinner": buyer_counterfactual["alternativeAdapterId"],
                "counterfactualDecisionHash": buyer_counterfactual["decisionHash"],
                "candidateDigests": sorted(
                    candidate["artifact_digest"] for candidate in candidates
                ),
                "gateResults": {
                    candidate["adapter_id"]: candidate["gate_results"] for candidate in candidates
                },
                "recovery": {
                    "piiPresent": recovery["pii_present"],
                    "controlTagAbsent": recovery["control_tag_absent"],
                    "routeRestored": recovery["current_adapter_digest"]
                    == workspace["activation"]["prior_adapter_digest"],
                },
            }
        ),
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (root / "gates.json").write_text(
        json.dumps(gates, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (root / "receipt-core.json").write_text(
        json.dumps(
            {
                **receipt,
                "projectionHash": workspace["receipt"]["datahub_projection_hash"],
                "rereadMatched": workspace["receipt"]["reread_matched"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "recovery.json").write_text(
        json.dumps(recovery, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    timeline = [
        "DATAHUB_BUYER_CONTEXT_READ",
        "BUYER_REQUIREMENTS_COMPILED",
        "SEIL_SELLER_EVIDENCE_BOUND",
        "BUYER_SPECIFIC_TRIALS_VERIFIED",
        "COUNTERFACTUAL_RECOMMENDATION_CHANGED",
        "CURRENT_CONTEXT_RESTORED",
        "BUYER_DECISION_RECEIPT_WRITTEN",
        "BUYER_DECISION_RECEIPT_REREAD",
    ]
    (root / "timeline.jsonl").write_text(
        "".join(
            json.dumps({"sequence": index, "event": event}) + "\n"
            for index, event in enumerate(timeline, start=1)
        ),
        encoding="utf-8",
    )
    (root / "summary.md").write_text(
        "# SIRA DataHub-grounded buying decision\n\n"
        f"- Status: **{exchange['status']}**\n"
        f"- Causal result: `{' -> '.join(workspace['context']['causal_sequence'])}`\n"
        f"- Current recommendation: `{restored_decision['winnerAdapterId']}`\n"
        f"- Counterfactual recommendation: `{buyer_counterfactual['alternativeAdapterId']}`\n"
        f"- Decision receipt: `{buyer_receipt['coreHash']}`\n"
        f"- DataHub receipt anchor: `{buyer_writeback['anchorUrn']}`\n"
        f"- DataHub reread: `{buyer_writeback['rereadMatched']}`\n"
        f"- Recovery: `{workspace['recovery']['status']}`\n"
        f"- Warm demo duration: `{timings['warmDemoSeconds']}s`\n"
        "- Environment preparation: "
        f"`{timings['totalSeconds'] - timings['warmDemoSeconds']:.3f}s`\n",
        encoding="utf-8",
    )
    evidence = root / "evidence"
    evidence.mkdir(exist_ok=True)
    for name in ("exchange-proof.json", "deployment-proof.json", "writeback-failure-proof.json"):
        source = root / name
        if source.exists():
            shutil.copy2(source, evidence / name)
    print(  # noqa: T201 - release packager emits a bounded completion record
        json.dumps({"status": "PASS", "commit": application_commit, "artifacts": str(root)})
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
