"""Persist K2 proof evidence through characterized existing immutable records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from decision_engine.graph_v1 import evaluate_decision_graph
from domain.hashing import content_hash
from persistence.models import AgentExperiment, DecisionSourceSnapshot
from persistence.repositories import RecordNotFound, WorkflowRepository, new_id
from proof.decision_bridge import EVALUATED_AT, build_decision_graph_input
from proof.models import CampaignDecision, EnvironmentObservation, EvaluationManifest

from .graph_ledger import DecisionLedgerMetadata, build_decision_ledger
from .graph_persistence import (
    EvaluationPersistenceMetadata,
    build_evaluation_graph_write,
    ensure_evaluation_pipeline_version,
)


@dataclass(frozen=True, slots=True)
class ProofPersistenceBindings:
    organization_id: str
    purchase_request_id: str
    purchase_brief_id: str
    purchase_brief_version: int
    requirement_brief_id: str
    requirement_brief_version: int
    company_profile_version: int
    stack_snapshot_id: str
    stack_snapshot_version: int
    mission_id: str
    accepted_by_actor_id: str
    decision_id: str
    decision_version: int
    source_version: int = 1


@dataclass(frozen=True, slots=True)
class PersistedProofEvidence:
    decision_source_snapshot_id: str
    experiment_ids: tuple[str, ...]
    evaluation_run_id: str


def _accepted_source_payload(
    observation: EnvironmentObservation,
    manifest: EvaluationManifest,
    decision: CampaignDecision,
) -> dict[str, Any]:
    return {
        "schemaVersion": "DataHubProofSource/v0",
        "observation": observation.semantic_payload(),
        "environmentFingerprint": observation.environment_fingerprint,
        "observationHash": observation.semantic_hash,
        "manifest": {**manifest.hash_payload(), "manifestHash": manifest.manifest_hash},
        "decisionHash": decision.decision_hash,
        "decisionGraphEvaluationHash": decision.decision_graph_evaluation_hash,
    }


async def persist_proof_evidence(
    session: AsyncSession,
    *,
    bindings: ProofPersistenceBindings,
    observation: EnvironmentObservation,
    manifest: EvaluationManifest,
    decision: CampaignDecision,
    runtime_results: dict[str, dict[str, Any]],
) -> PersistedProofEvidence:
    repository = WorkflowRepository(session, bindings.organization_id)
    source_payload = _accepted_source_payload(observation, manifest, decision)
    source_hash = content_hash(source_payload)
    existing_source = (
        await session.execute(
            select(DecisionSourceSnapshot).where(
                DecisionSourceSnapshot.organization_id == bindings.organization_id,
                DecisionSourceSnapshot.purchase_request_id == bindings.purchase_request_id,
                DecisionSourceSnapshot.content_hash == source_hash,
            )
        )
    ).scalar_one_or_none()
    if existing_source is None:
        latest_source_version = (
            await session.execute(
                select(func.max(DecisionSourceSnapshot.version)).where(
                    DecisionSourceSnapshot.organization_id == bindings.organization_id,
                    DecisionSourceSnapshot.purchase_request_id == bindings.purchase_request_id,
                )
            )
        ).scalar_one()
        existing_source = await repository.add_decision_source_snapshot(
            DecisionSourceSnapshot(
                id=new_id("dss"),
                organization_id=bindings.organization_id,
                purchase_request_id=bindings.purchase_request_id,
                purchase_brief_id=bindings.purchase_brief_id,
                stack_snapshot_id=bindings.stack_snapshot_id,
                version=max(bindings.source_version, int(latest_source_version or 0) + 1),
                source_kind="MANUAL_VERIFIED",
                payload=source_payload,
                content_hash=source_hash,
                accepted_by_actor_id=bindings.accepted_by_actor_id,
                accepted_at=EVALUATED_AT,
            )
        )

    experiments: list[AgentExperiment] = []
    for verdict in decision.verdicts:
        runtime = runtime_results[verdict.adapter_id]
        payload = {
            "candidateId": verdict.adapter_id,
            "manifestHash": manifest.manifest_hash,
            "environmentFingerprint": observation.environment_fingerprint,
            "artifactDigest": verdict.artifact_digest,
            "runtimeResultHash": verdict.result_hash,
            "gateResults": runtime["gateResults"],
            "eligible": verdict.eligible,
            "failedGateIds": list(verdict.failed_gate_ids),
        }
        experiment_hash = content_hash(payload)
        experiment = (
            await session.execute(
                select(AgentExperiment).where(
                    AgentExperiment.organization_id == bindings.organization_id,
                    AgentExperiment.mission_id == bindings.mission_id,
                    AgentExperiment.content_hash == experiment_hash,
                )
            )
        ).scalar_one_or_none()
        if experiment is None:
            experiment = AgentExperiment(
                id=new_id("aexp"),
                organization_id=bindings.organization_id,
                mission_id=bindings.mission_id,
                task_id=None,
                candidate_id=verdict.adapter_id,
                status="COMPLETED",
                procedure={
                    "protocolVersion": "TrialCase/v0",
                    "sellerSafeManifest": manifest.seller_safe_payload,
                },
                environment={
                    "environmentFingerprint": observation.environment_fingerprint,
                    "manifestHash": manifest.manifest_hash,
                },
                success_signals=[
                    {"gateId": gate_id, "passed": passed}
                    for gate_id, passed in sorted(runtime["gateResults"].items())
                ],
                observations=[payload],
                limitations=["Synthetic exact-marker canary; no real customer data."],
                replay_spec={
                    "artifactDigest": verdict.artifact_digest,
                    "resultHash": verdict.result_hash,
                },
                cost={"amount": verdict.declared_price, "currency": "USD"},
                result_artifact_id=None,
                content_hash=experiment_hash,
                started_at=EVALUATED_AT,
                completed_at=EVALUATED_AT,
            )
            session.add(experiment)
            await session.flush()
        experiments.append(experiment)

    graph_input = build_decision_graph_input(manifest, decision.verdicts)
    graph_decision = evaluate_decision_graph(
        graph_input,
        evaluation_id=f"proof_eval_{manifest.manifest_hash[-16:]}",
        generated_at=EVALUATED_AT,
    )
    if graph_decision.base.evaluation_payload_hash != decision.decision_graph_evaluation_hash:
        raise ValueError("persisted Decision Graph replay does not match the campaign decision")
    created_at = datetime.now(UTC)
    ledger_metadata = DecisionLedgerMetadata(
        decision_id=bindings.decision_id,
        decision_version=bindings.decision_version,
        supersedes_decision_id=None,
        request_id=bindings.purchase_request_id,
        purchase_brief_id=bindings.purchase_brief_id,
        purchase_brief_version=bindings.purchase_brief_version,
        requirement_brief_id=bindings.requirement_brief_id,
        requirement_brief_version=bindings.requirement_brief_version,
        company_profile_version=bindings.company_profile_version,
        stack_snapshot=bindings.stack_snapshot_version,
        policy_version=1,
        created_at=created_at,
    )
    ledger = build_decision_ledger(graph_decision, graph_input, ledger_metadata)
    persistence_metadata = EvaluationPersistenceMetadata(
        organization_id=bindings.organization_id,
        purchase_request_id=bindings.purchase_request_id,
        purchase_brief_id=bindings.purchase_brief_id,
        decision_id=None,
        candidate_set_version="proof-projections/v0",
        quote_set_version="proof-fixed-prices/v0",
        risk_rule_set_version="proof-risk/v0",
        valuation_currency="USD",
    )
    await ensure_evaluation_pipeline_version(repository, graph_input, persistence_metadata)
    graph_write = build_evaluation_graph_write(
        graph_decision,
        graph_input,
        ledger,
        persistence_metadata,
    )
    try:
        evaluation = await repository.get_evaluation_by_payload_hash(
            graph_write.evaluation_run.evaluation_payload_hash
        )
    except RecordNotFound:
        evaluation = await repository.add_evaluation_graph(graph_write)
    return PersistedProofEvidence(
        decision_source_snapshot_id=existing_source.id,
        experiment_ids=tuple(experiment.id for experiment in experiments),
        evaluation_run_id=evaluation.id,
    )
