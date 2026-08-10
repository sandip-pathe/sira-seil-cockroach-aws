"""Local proof runner and artifact reader for the operator workspace."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Any

from domain.hashing import content_hash

from .errors import ApiProblem
from .proof_schemas import ProofWorkspaceView

_CAUSAL_SEQUENCE = ["adapter-b", "adapter-a", "adapter-b"]
_SAFE_CONTEXT_KEYS = {
    "rootUrn",
    "profileUrn",
    "rootFields",
    "profileFields",
    "upstreamUrns",
    "ownerUrns",
    "allowedRegions",
    "piiPresent",
    "dependencies",
}
_SAFE_SOURCE_FACTS = {
    "schemaFields",
    "upstreamDatasets",
    "ownerUrns",
    "allowedRegions",
    "emailPiiTagged",
}


class ProofWorkspaceRuntime:
    def __init__(self, root: Path) -> None:
        self.root = root
        configured = os.getenv("SIRA_PROOF_WORKSPACE_ARTIFACT", "").strip()
        self.artifact_path = (
            Path(configured).expanduser().resolve()
            if configured
            else root / ".artifacts" / "proof" / "workspace.json"
        )
        self.exchange_artifact_path = self.artifact_path.with_name("exchange-proof.json")
        self._task: asyncio.Task[None] | None = None
        self._status = "IDLE"
        self._run_id: str | None = None
        self._safe_error_code: str | None = None

    def workspace(self) -> ProofWorkspaceView:
        try:
            payload: Any = json.loads(self.artifact_path.read_text(encoding="utf-8-sig"))
            workspace = ProofWorkspaceView.model_validate(payload)
        except FileNotFoundError as exc:
            raise ApiProblem(
                code="PROOF_RUN_NOT_FOUND",
                message="No verified proof run is available yet.",
                status_code=404,
                next_action="run_proof_demo",
                details={"next_command": "scripts\\proof.cmd demo -Assert"},
            ) from exc
        except (OSError, ValueError) as exc:
            raise ApiProblem(
                code="PROOF_ARTIFACT_INVALID",
                message="The latest proof artifact could not be verified.",
                status_code=409,
                next_action="rerun_proof_demo",
                details={"next_command": "scripts\\proof.cmd demo -Assert"},
            ) from exc
        self._run_id = workspace.run_id
        if self._status != "RUNNING":
            self._status = "COMPLETE"
            self._safe_error_code = None
        return workspace

    def buyer_decision(self) -> dict[str, Any]:
        """Return a buyer-safe decision only when the full DataHub proof is bound."""

        try:
            raw: Any = json.loads(self.exchange_artifact_path.read_text(encoding="utf-8-sig"))
        except FileNotFoundError as exc:
            raise ApiProblem(
                code="DATAHUB_DECISION_NOT_FOUND",
                message="No verified DataHub buying decision is available yet.",
                status_code=404,
                next_action="run_proof_demo",
                details={"next_command": "scripts\\proof.cmd exchange -Assert"},
            ) from exc
        except (OSError, ValueError) as exc:
            raise self._invalid_buyer_decision() from exc

        try:
            return self._project_buyer_decision(self._mapping(raw, "exchange artifact"))
        except ApiProblem:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise self._invalid_buyer_decision() from exc

    @staticmethod
    def _invalid_buyer_decision() -> ApiProblem:
        return ApiProblem(
            code="DATAHUB_DECISION_INVALID",
            message="The DataHub buying decision failed verification.",
            status_code=409,
            next_action="rerun_proof_demo",
            details={"next_command": "scripts\\proof.cmd exchange -Assert"},
        )

    @staticmethod
    def _mapping(value: Any, label: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError(f"{label} must be an object")
        return value

    @staticmethod
    def _items(value: Any, label: str) -> list[Any]:
        if not isinstance(value, list):
            raise ValueError(f"{label} must be a list")
        return value

    @staticmethod
    def _hash(value: Any, label: str) -> str:
        if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
            raise ValueError(f"{label} must be a sha256 digest")
        return value

    @classmethod
    def _safe_observation(cls, run: dict[str, Any]) -> dict[str, Any]:
        observation = cls._mapping(run.get("environmentObservation"), "environment observation")
        if observation.get("schemaVersion") != "EnvironmentObservationSafe/v0":
            raise ValueError("environment observation schema is invalid")
        if observation.get("semanticHash") != run.get("observationHash"):
            raise ValueError("environment observation hash is unbound")
        if observation.get("environmentFingerprint") != run.get("environmentFingerprint"):
            raise ValueError("environment fingerprint is unbound")
        if (
            not isinstance(observation.get("readAttempts"), int)
            or int(observation["readAttempts"]) < 2
        ):
            raise ValueError("environment observation was not stably reread")

        safe_context = cls._mapping(observation.get("safeContext"), "safe context")
        if set(safe_context) != _SAFE_CONTEXT_KEYS:
            raise ValueError("safe context contains an unexpected field")
        if safe_context.get("piiPresent") is not run.get("piiPresent"):
            raise ValueError("safe context PII state is unbound")
        for key in (
            "rootFields",
            "profileFields",
            "upstreamUrns",
            "ownerUrns",
            "allowedRegions",
            "dependencies",
        ):
            cls._items(safe_context.get(key), f"safe context {key}")
        for key in ("rootUrn", "profileUrn"):
            if not isinstance(safe_context.get(key), str):
                raise ValueError(f"safe context {key} is invalid")

        source_details = cls._items(observation.get("sourceDetails"), "DataHub source details")
        if len(source_details) != 6:
            raise ValueError("DataHub source details are incomplete")
        normalized_sources: list[dict[str, Any]] = []
        for item in source_details:
            source = cls._mapping(item, "DataHub source detail")
            if (
                not isinstance(source.get("urn"), str)
                or not isinstance(source.get("label"), str)
                or source.get("fact") not in _SAFE_SOURCE_FACTS
                or not isinstance(source.get("value"), (bool, list))
            ):
                raise ValueError("DataHub source detail is invalid")
            normalized_sources.append(
                {
                    "urn": source["urn"],
                    "label": source["label"],
                    "fact": source["fact"],
                    "value": source["value"],
                }
            )
        return {
            "safe_context": safe_context,
            "source_details": normalized_sources,
            "semantic_hash": observation["semanticHash"],
            "environment_fingerprint": observation["environmentFingerprint"],
            "read_attempts": observation["readAttempts"],
        }

    @classmethod
    def _project_buyer_decision(cls, artifact: dict[str, Any]) -> dict[str, Any]:
        if artifact.get("status") != "PASS":
            raise ValueError("exchange proof did not pass")
        causal = cls._mapping(artifact.get("exchangeCausalProof"), "causal proof")
        if causal.get("status") != "PASS" or causal.get("causalSequence") != _CAUSAL_SEQUENCE:
            raise ValueError("causal proof is not an exact passing B-A-B sequence")

        run_items = cls._items(causal.get("runs"), "causal runs")
        runs: dict[str, dict[str, Any]] = {}
        for item in run_items:
            run = cls._mapping(item, "causal run")
            label = run.get("label")
            if isinstance(label, str):
                if label in runs:
                    raise ValueError("causal run labels must be unique")
                runs[label] = run
        required_runs = {
            "baseline-pii-present": ("adapter-b", True),
            "unrelated-governed-change": ("adapter-b", True),
            "pii-removed": ("adapter-a", False),
            "pii-restored": ("adapter-b", True),
        }
        for label, (winner, pii_present) in required_runs.items():
            required_run = runs.get(label)
            if (
                required_run is None
                or required_run.get("winnerAdapterId") != winner
                or required_run.get("piiPresent") is not pii_present
            ):
                raise ValueError(f"{label} is invalid")
            cls._hash(required_run.get("decisionHash"), f"{label} decision hash")
            cls._safe_observation(required_run)

        baseline = runs["baseline-pii-present"]
        unrelated = runs["unrelated-governed-change"]
        counterfactual = runs["pii-removed"]
        current = runs["pii-restored"]
        for field in (
            "observationHash",
            "environmentFingerprint",
            "manifestHash",
            "decisionHash",
        ):
            if baseline.get(field) != current.get(field):
                raise ValueError("restored run does not reproduce the baseline")
        if counterfactual.get("decisionHash") == current.get("decisionHash"):
            raise ValueError("counterfactual did not change the decision")
        for field in ("observationHash", "environmentFingerprint", "manifestHash", "decisionHash"):
            if unrelated.get(field) != baseline.get(field):
                raise ValueError("negative control changed an accepted decision input")

        negative_control = cls._mapping(causal.get("negativeControl"), "negative control")
        for field in (
            "tagObservedBeforeEvaluation",
            "acceptedFingerprintUnchanged",
            "manifestHashUnchanged",
            "decisionHashUnchanged",
        ):
            if negative_control.get(field) is not True:
                raise ValueError("negative control did not pass")
        recovery = cls._mapping(causal.get("recovery"), "causal recovery")
        if recovery.get("piiPresent") is not True or recovery.get("controlTagAbsent") is not True:
            raise ValueError("DataHub context was not restored")

        projections = cls._items(artifact.get("buyerProjections"), "seller projections")
        projections_by_id = {
            item.get("adapterId"): item
            for raw_item in projections
            if isinstance(raw_item, dict)
            for item in [raw_item]
            if isinstance(item.get("adapterId"), str)
        }
        if set(projections_by_id) != {"adapter-a", "adapter-b"}:
            raise ValueError("exactly two seller projections are required")
        for adapter_id, projection in projections_by_id.items():
            cls._hash(projection.get("artifactDigest"), f"{adapter_id} artifact digest")
            cls._hash(projection.get("projectionHash"), f"{adapter_id} projection hash")
            cls._items(projection.get("capabilities"), f"{adapter_id} capabilities")
            cls._mapping(projection.get("fixedPrice"), f"{adapter_id} fixed price")

        current_verdicts = {
            item.get("adapter_id"): item
            for item in cls._items(current.get("verdicts"), "current verdicts")
            if isinstance(item, dict) and isinstance(item.get("adapter_id"), str)
        }
        counterfactual_verdicts = {
            item.get("adapter_id"): item
            for item in cls._items(counterfactual.get("verdicts"), "counterfactual verdicts")
            if isinstance(item, dict) and isinstance(item.get("adapter_id"), str)
        }
        if (
            set(current_verdicts) != {"adapter-a", "adapter-b"}
            or current_verdicts["adapter-a"].get("eligible") is not False
            or current_verdicts["adapter-b"].get("eligible") is not True
            or set(counterfactual_verdicts) != {"adapter-a", "adapter-b"}
            or counterfactual_verdicts["adapter-a"].get("eligible") is not True
        ):
            raise ValueError("candidate verdicts do not support the causal winners")
        for adapter_id, verdict in current_verdicts.items():
            if verdict.get("artifact_digest") != projections_by_id[adapter_id].get(
                "artifactDigest"
            ):
                raise ValueError("candidate verdict is not bound to seller evidence")

        receipt = cls._mapping(artifact.get("buyerDecisionReceipt"), "buyer receipt")
        if receipt.get("schemaVersion") != "BuyerDecisionReceipt/v0":
            raise ValueError("buyer receipt schema is invalid")
        core_hash = cls._hash(receipt.get("coreHash"), "buyer receipt core hash")
        decision_hash = cls._hash(receipt.get("decisionHash"), "buyer decision hash")
        if decision_hash != current.get("decisionHash"):
            raise ValueError("buyer receipt is not bound to the current decision")
        payload = cls._mapping(receipt.get("payload"), "buyer receipt payload")
        if (
            payload.get("schemaVersion") != "BuyerDecisionEvidenceCore/v0"
            or payload.get("decisionHash") != decision_hash
            or content_hash(payload) != core_hash
        ):
            raise ValueError("buyer receipt core is invalid")

        recommendation = cls._mapping(payload.get("recommendation"), "buyer recommendation")
        if recommendation.get("adapterId") != "adapter-b":
            raise ValueError("current buyer recommendation is invalid")
        for payload_field, run_field in (
            ("manifestHash", "manifestHash"),
            ("observationHash", "observationHash"),
            ("environmentFingerprint", "environmentFingerprint"),
            ("decisionGraphSelectedPlanId", "decisionGraphSelectedPlanId"),
            ("decisionGraphEvaluationHash", "decisionGraphEvaluationHash"),
        ):
            if recommendation.get(payload_field) != current.get(run_field):
                raise ValueError("buyer recommendation is not bound to the restored run")
        required_gate_ids = cls._items(recommendation.get("requiredGateIds"), "buyer requirements")
        if required_gate_ids != current.get("emittedGateIds"):
            raise ValueError("buyer requirements are not bound to the restored run")

        observation = cls._safe_observation(current)
        receipt_context = cls._mapping(payload.get("dataHubContext"), "receipt DataHub context")
        if (
            receipt_context.get("safeContext") != observation["safe_context"]
            or receipt_context.get("sourceDetails") != observation["source_details"]
        ):
            raise ValueError("receipt DataHub context is unbound")

        seller_evidence = cls._items(payload.get("sellerEvidence"), "seller evidence")
        seller_evidence_by_id = {
            item.get("adapterId"): item
            for raw_item in seller_evidence
            if isinstance(raw_item, dict)
            for item in [raw_item]
            if isinstance(item.get("adapterId"), str)
        }
        if set(seller_evidence_by_id) != {"adapter-a", "adapter-b"}:
            raise ValueError("receipt seller evidence is incomplete")
        for adapter_id, evidence in seller_evidence_by_id.items():
            projection = projections_by_id[adapter_id]
            for field in (
                "sourceSellerOrganizationId",
                "sourcePackVersionId",
                "projectionHash",
                "artifactDigest",
                "capabilities",
                "fixedPrice",
            ):
                if evidence.get(field) != projection.get(field):
                    raise ValueError("receipt seller evidence is unbound")
            verdict = current_verdicts[adapter_id]
            if (
                evidence.get("eligible") is not verdict.get("eligible")
                or evidence.get("failedGateIds") != verdict.get("failed_gate_ids")
                or evidence.get("trialResultHash") != verdict.get("result_hash")
            ):
                raise ValueError("receipt seller evidence is not bound to trial results")

        counterfactual_receipt = cls._mapping(payload.get("counterfactual"), "buyer counterfactual")
        if (
            counterfactual_receipt.get("alternativeAdapterId") != "adapter-a"
            or counterfactual_receipt.get("from") is not True
            or counterfactual_receipt.get("to") is not False
            or counterfactual_receipt.get("decisionHash") != counterfactual.get("decisionHash")
            or counterfactual_receipt.get("manifestHash") != counterfactual.get("manifestHash")
            or counterfactual_receipt.get("environmentFingerprint")
            != counterfactual.get("environmentFingerprint")
        ):
            raise ValueError("buyer counterfactual is invalid")

        verification = cls._mapping(payload.get("causalVerification"), "causal verification")
        if (
            verification.get("sequence") != _CAUSAL_SEQUENCE
            or verification.get("baselineDecisionHash") != baseline.get("decisionHash")
            or verification.get("restoredDecisionHash") != current.get("decisionHash")
            or verification.get("restoredBaselineMatched") is not True
            or verification.get("negativeControlPassed") is not True
        ):
            raise ValueError("receipt causal verification is invalid")

        writeback = cls._mapping(receipt.get("dataHubWriteback"), "DataHub writeback")
        if (
            writeback.get("status") != "REREAD_VERIFIED"
            or writeback.get("rereadMatched") is not True
            or not isinstance(writeback.get("anchorUrn"), str)
        ):
            raise ValueError("DataHub writeback was not reread")
        cls._hash(writeback.get("projectionHash"), "DataHub projection hash")

        return {
            "status": "PASS",
            "run_id": core_hash.removeprefix("sha256:")[-12:],
            "decision_hash": decision_hash,
            "input_hash": recommendation["manifestHash"],
            "selected_adapter_id": "adapter-b",
            "counterfactual_adapter_id": "adapter-a",
            "requirements": required_gate_ids,
            "datahub_context": observation,
            "seller_projections": [
                seller_evidence_by_id["adapter-a"],
                seller_evidence_by_id["adapter-b"],
            ],
            "negative_control": {
                "mutation": negative_control.get("mutation"),
                "decision_unchanged": True,
                "context_fingerprint_unchanged": True,
            },
            "counterfactual": {
                "fact": counterfactual_receipt.get("fact"),
                "source_urn": counterfactual_receipt.get("sourceUrn"),
                "from": True,
                "to": False,
                "decision_hash": counterfactual_receipt["decisionHash"],
            },
            "receipt": {
                "core_hash": core_hash,
                "decision_hash": decision_hash,
                "anchor_urn": writeback["anchorUrn"],
                "projection_hash": writeback["projectionHash"],
                "writeback_status": "REREAD_VERIFIED",
                "reread_matched": True,
            },
        }

    def runner(self) -> dict[str, str | None]:
        return {
            "status": self._status,
            "run_id": self._run_id,
            "safe_error_code": self._safe_error_code,
            "artifact_path": str(self.artifact_path.relative_to(self.root)),
            "next_command": (
                "scripts\\proof.cmd demo -Assert" if self._status == "FAILED" else None
            ),
        }

    async def start(self) -> dict[str, str | None]:
        if self._task is not None and not self._task.done():
            return self.runner()
        shell = shutil.which("powershell.exe") or shutil.which("pwsh")
        if shell is None:
            raise ApiProblem(
                code="PROOF_RUNNER_UNAVAILABLE",
                message="The local proof runner is unavailable in this API process.",
                status_code=503,
                next_action="run_proof_demo",
                details={"next_command": "scripts\\proof.cmd demo -Assert"},
            )
        self._status = "RUNNING"
        self._safe_error_code = None
        self._task = asyncio.create_task(self._execute(shell))
        return self.runner()

    async def _execute(self, shell: str) -> None:
        try:
            process = await asyncio.create_subprocess_exec(
                shell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.root / "scripts" / "proof.ps1"),
                "demo",
                "-Assert",
                "-Artifacts",
                ".artifacts/proof",
                cwd=self.root,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            return_code = await process.wait()
            if return_code != 0:
                self._status = "FAILED"
                self._safe_error_code = "PROOF_DEMO_FAILED"
                return
            workspace = self.workspace()
            self._run_id = workspace.run_id
            self._status = "COMPLETE"
        except Exception:
            self._status = "FAILED"
            self._safe_error_code = "PROOF_DEMO_FAILED"

    async def close(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
