"""Repositories and guarded lifecycle writes.

All methods expect a transaction created by :class:`persistence.Database` so
domain state and its outbox event commit atomically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from fractions import Fraction
from typing import Any
from uuid import uuid4

from sqlalchemy import Select, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from domain import content_hash

from .models import (
    ActionRun,
    ApprovalEvent,
    ApprovalRequest,
    CandidateFeedback,
    CandidateSetMember,
    CounterfactualRecordModel,
    DecisionGateResult,
    DecisionRecord,
    DiscoveryRun,
    Engagement,
    Entitlement,
    EvaluationPipelineVersion,
    EvaluationRun,
    EvaluationSolutionPlan,
    EvidenceAssessmentRecord,
    IdempotencyRecord,
    IdentityMerge,
    MerchantOrder,
    OutboxEvent,
    PaymentSession,
    PurchaseIntent,
    PurchaseRequest,
    Receipt,
    RequirementBriefVersion,
    ResultArtifact,
    RobustnessFrontier,
    ScoreBound,
    ScoreComponentRecord,
    SolutionPlanComponent,
    StackPatch,
    StackSnapshot,
    TransactionTransition,
)


class PersistenceConflict(RuntimeError):
    """A compare-and-set, exact-hash, or uniqueness guard rejected a write."""


class IdempotencyConflict(PersistenceConflict):
    """The same idempotency key was reused with a different request body."""


class RecordNotFound(LookupError):
    """The requested tenant-owned aggregate does not exist."""


@dataclass(frozen=True, slots=True)
class IdempotencyClaim:
    record: IdempotencyRecord
    replay: bool


@dataclass(frozen=True, slots=True)
class EvaluationGraphWrite:
    """Complete normalized child set for one immutable evaluation run."""

    evaluation_run: EvaluationRun
    discovery_run: DiscoveryRun
    solution_plans: tuple[EvaluationSolutionPlan, ...]
    candidate_set_members: tuple[CandidateSetMember, ...] = ()
    identity_merges: tuple[IdentityMerge, ...] = ()
    decision_gate_results: tuple[DecisionGateResult, ...] = ()
    evidence_assessments: tuple[EvidenceAssessmentRecord, ...] = ()
    solution_plan_components: tuple[SolutionPlanComponent, ...] = ()
    score_components: tuple[ScoreComponentRecord, ...] = ()
    score_bounds: tuple[ScoreBound, ...] = ()
    robustness_frontiers: tuple[RobustnessFrontier, ...] = ()


@dataclass(frozen=True, slots=True)
class EvaluationGraphSnapshot:
    evaluation_run: EvaluationRun
    discovery_run: DiscoveryRun
    solution_plans: tuple[EvaluationSolutionPlan, ...]
    candidate_set_members: tuple[CandidateSetMember, ...]
    identity_merges: tuple[IdentityMerge, ...]
    decision_gate_results: tuple[DecisionGateResult, ...]
    evidence_assessments: tuple[EvidenceAssessmentRecord, ...]
    solution_plan_components: tuple[SolutionPlanComponent, ...]
    score_components: tuple[ScoreComponentRecord, ...]
    score_bounds: tuple[ScoreBound, ...]
    robustness_frontiers: tuple[RobustnessFrontier, ...]


@dataclass(frozen=True, slots=True)
class ActionRunSnapshot:
    action_run: ActionRun
    result_artifacts: tuple[ResultArtifact, ...]


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


async def _one_or_missing[T](session: AsyncSession, statement: Select[tuple[T]]) -> T:
    value = (await session.execute(statement)).scalar_one_or_none()
    if value is None:
        raise RecordNotFound("Tenant-owned record was not found")
    return value


class WorkflowRepository:
    """Canonical vertical-workflow repository."""

    def __init__(self, session: AsyncSession, organization_id: str) -> None:
        self.session = session
        self.organization_id = organization_id

    async def get_purchase_request(self, request_id: str, *, lock: bool = False) -> PurchaseRequest:
        statement = select(PurchaseRequest).where(
            PurchaseRequest.id == request_id,
            PurchaseRequest.organization_id == self.organization_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await _one_or_missing(self.session, statement)

    async def add_purchase_request(self, record: PurchaseRequest) -> PurchaseRequest:
        self._assert_tenant(record.organization_id)
        self.session.add(record)
        await self.add_outbox(
            aggregate_type="purchase_request",
            aggregate_id=record.id,
            event_type="purchase_request.created",
            event_key=f"purchase-request-created:{record.id}:{record.version}",
            payload={"request_id": record.id, "version": record.version},
        )
        return record

    async def get_requirement_brief(self, brief_id: str) -> RequirementBriefVersion:
        return await _one_or_missing(
            self.session,
            select(RequirementBriefVersion).where(
                RequirementBriefVersion.id == brief_id,
                RequirementBriefVersion.organization_id == self.organization_id,
            ),
        )

    async def get_decision(self, decision_id: str) -> DecisionRecord:
        return await _one_or_missing(
            self.session,
            select(DecisionRecord).where(
                DecisionRecord.id == decision_id,
                DecisionRecord.organization_id == self.organization_id,
            ),
        )

    async def add_evaluation_pipeline_version(
        self, record: EvaluationPipelineVersion
    ) -> EvaluationPipelineVersion:
        """Stage an immutable pipeline definition in the caller's transaction."""

        self._assert_tenant(record.organization_id)
        self._assert_payload_hash(record.payload, record.content_hash, "pipeline")
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_evaluation_pipeline_version(
        self, pipeline_version_id: str
    ) -> EvaluationPipelineVersion:
        return await _one_or_missing(
            self.session,
            select(EvaluationPipelineVersion).where(
                EvaluationPipelineVersion.id == pipeline_version_id,
                EvaluationPipelineVersion.organization_id == self.organization_id,
            ),
        )

    async def add_evaluation_graph(self, graph: EvaluationGraphWrite) -> EvaluationRun:
        """Write one complete Decision Graph evaluation as a single aggregate.

        The method never commits. Callers use :meth:`Database.transaction`, so
        the normalized rows and outbox record either all commit or all roll back.
        """

        evaluation = graph.evaluation_run
        self._assert_tenant(evaluation.organization_id)
        self._assert_payload_hash(
            evaluation.input_payload, evaluation.input_payload_hash, "evaluation input"
        )
        self._assert_payload_hash(
            evaluation.evaluation_payload,
            evaluation.evaluation_payload_hash,
            "evaluation payload",
        )
        pipeline = await self.get_evaluation_pipeline_version(
            evaluation.evaluation_pipeline_version_id
        )
        expected_versions = (
            (pipeline.pipeline_version, evaluation.pipeline_version, "pipeline"),
            (pipeline.engine_version, evaluation.engine_version, "engine"),
            (pipeline.taxonomy_version, evaluation.taxonomy_version, "taxonomy"),
            (
                pipeline.normalization_version,
                evaluation.normalization_version,
                "normalization",
            ),
            (pipeline.policy_version, evaluation.policy_version, "policy"),
        )
        for pipeline_value, run_value, label in expected_versions:
            if pipeline_value != run_value:
                raise PersistenceConflict(
                    f"Evaluation {label} version does not match its frozen pipeline"
                )

        records: tuple[object, ...] = (
            evaluation,
            graph.discovery_run,
            *graph.solution_plans,
            *graph.candidate_set_members,
            *graph.identity_merges,
            *graph.decision_gate_results,
            *graph.evidence_assessments,
            *graph.solution_plan_components,
            *graph.score_components,
            *graph.score_bounds,
            *graph.robustness_frontiers,
        )
        for record in records:
            self._assert_tenant(getattr(record, "organization_id", None))

        if graph.discovery_run.evaluation_run_id != evaluation.id:
            raise PersistenceConflict("Discovery run is not bound to the evaluation")
        for record in graph.candidate_set_members:
            if record.discovery_run_id != graph.discovery_run.id:
                raise PersistenceConflict("Candidate member is not bound to the discovery run")
        for record in graph.identity_merges:
            if record.discovery_run_id != graph.discovery_run.id:
                raise PersistenceConflict("Identity merge is not bound to the discovery run")

        plan_records = {plan.id: plan for plan in graph.solution_plans}
        if len(plan_records) != len(graph.solution_plans):
            raise PersistenceConflict("Solution Plan record IDs must be unique")
        stable_plan_ids = {plan.solution_plan_id for plan in graph.solution_plans}
        if len(stable_plan_ids) != len(graph.solution_plans):
            raise PersistenceConflict("Solution Plan IDs must be unique within an evaluation")
        if (
            evaluation.selected_solution_plan_id is not None
            and evaluation.selected_solution_plan_id not in stable_plan_ids
        ):
            raise PersistenceConflict("Selected Solution Plan is absent from the evaluation")
        selected_plans = [plan for plan in graph.solution_plans if plan.selected]
        if evaluation.selected_solution_plan_id is None:
            if selected_plans:
                raise PersistenceConflict("An unselected evaluation contains a selected plan")
        elif (
            len(selected_plans) != 1
            or selected_plans[0].solution_plan_id != evaluation.selected_solution_plan_id
        ):
            raise PersistenceConflict("Evaluation selection and selected plan row do not match")
        rank_positions = [
            plan.rank_position for plan in graph.solution_plans if plan.rank_position is not None
        ]
        if len(rank_positions) != len(set(rank_positions)):
            raise PersistenceConflict("Rank positions must be unique within an evaluation")
        for plan in graph.solution_plans:
            if plan.evaluation_run_id != evaluation.id:
                raise PersistenceConflict("Solution Plan is not bound to the evaluation")
            self._assert_payload_hash(plan.payload, plan.plan_hash, "Solution Plan")

        plan_children = (
            *graph.decision_gate_results,
            *graph.solution_plan_components,
            *graph.score_components,
            *graph.score_bounds,
            *graph.robustness_frontiers,
        )
        for record in plan_children:
            if getattr(record, "evaluation_run_id", None) != evaluation.id:
                raise PersistenceConflict("Plan child is not bound to the evaluation")
            bound_plan = plan_records.get(str(getattr(record, "solution_plan_record_id", "")))
            if bound_plan is None:
                raise PersistenceConflict("Plan child references an unknown Solution Plan")

        for assessment in graph.evidence_assessments:
            if assessment.evaluation_run_id != evaluation.id:
                raise PersistenceConflict("Evidence assessment is not bound to the evaluation")
        for bound in graph.score_bounds:
            if bound.bound_status != "AVAILABLE":
                continue
            assert bound.lower_numerator is not None
            assert bound.lower_denominator is not None
            assert bound.base_numerator is not None
            assert bound.base_denominator is not None
            assert bound.upper_numerator is not None
            assert bound.upper_denominator is not None
            lower = Fraction(bound.lower_numerator, bound.lower_denominator)
            base = Fraction(bound.base_numerator, bound.base_denominator)
            upper = Fraction(bound.upper_numerator, bound.upper_denominator)
            if not lower <= base <= upper:
                raise PersistenceConflict("Score bound lower/base/upper values are reversed")
        for component in graph.score_components:
            conservative = Fraction(
                component.conservative_satisfaction_numerator,
                component.conservative_satisfaction_denominator,
            )
            optimistic = Fraction(
                component.optimistic_satisfaction_numerator,
                component.optimistic_satisfaction_denominator,
            )
            if not Fraction(0) <= conservative <= optimistic <= Fraction(1):
                raise PersistenceConflict("Score satisfaction bounds must be ordered within [0,1]")

        self.session.add_all(records)
        await self.add_outbox(
            aggregate_type="evaluation_run",
            aggregate_id=evaluation.id,
            event_type="evaluation_run.persisted",
            event_key=f"evaluation-run-persisted:{evaluation.evaluation_payload_hash}",
            payload={
                "evaluation_run_id": evaluation.id,
                "evaluation_payload_hash": evaluation.evaluation_payload_hash,
                "run_kind": evaluation.run_kind,
            },
        )
        await self.session.flush()
        return evaluation

    async def get_evaluation_by_payload_hash(self, payload_hash: str) -> EvaluationRun:
        return await _one_or_missing(
            self.session,
            select(EvaluationRun).where(
                EvaluationRun.organization_id == self.organization_id,
                EvaluationRun.evaluation_payload_hash == payload_hash,
            ),
        )

    async def get_selected_solution_plan(
        self, decision_id: str, solution_plan_id: str
    ) -> EvaluationSolutionPlan:
        return await _one_or_missing(
            self.session,
            select(EvaluationSolutionPlan)
            .join(EvaluationRun, EvaluationRun.id == EvaluationSolutionPlan.evaluation_run_id)
            .where(
                EvaluationSolutionPlan.organization_id == self.organization_id,
                EvaluationSolutionPlan.solution_plan_id == solution_plan_id,
                EvaluationSolutionPlan.selected.is_(True),
                EvaluationRun.organization_id == self.organization_id,
                EvaluationRun.decision_id == decision_id,
                EvaluationRun.run_kind == "BASE",
            ),
        )

    async def get_evaluation_graph(self, evaluation_run_id: str) -> EvaluationGraphSnapshot:
        evaluation = await _one_or_missing(
            self.session,
            select(EvaluationRun).where(
                EvaluationRun.id == evaluation_run_id,
                EvaluationRun.organization_id == self.organization_id,
            ),
        )
        discovery = await _one_or_missing(
            self.session,
            select(DiscoveryRun).where(
                DiscoveryRun.evaluation_run_id == evaluation_run_id,
                DiscoveryRun.organization_id == self.organization_id,
            ),
        )

        async def rows[T](statement: Select[tuple[T]]) -> tuple[T, ...]:
            return tuple((await self.session.execute(statement)).scalars().all())

        plans = await rows(
            select(EvaluationSolutionPlan)
            .where(
                EvaluationSolutionPlan.evaluation_run_id == evaluation_run_id,
                EvaluationSolutionPlan.organization_id == self.organization_id,
            )
            .order_by(
                EvaluationSolutionPlan.rank_position.asc().nulls_last(),
                EvaluationSolutionPlan.solution_plan_id,
            )
        )
        candidates = await rows(
            select(CandidateSetMember)
            .where(
                CandidateSetMember.discovery_run_id == discovery.id,
                CandidateSetMember.organization_id == self.organization_id,
            )
            .order_by(CandidateSetMember.ordinal, CandidateSetMember.id)
        )
        merges = await rows(
            select(IdentityMerge)
            .where(
                IdentityMerge.discovery_run_id == discovery.id,
                IdentityMerge.organization_id == self.organization_id,
            )
            .order_by(IdentityMerge.canonical_identity_id, IdentityMerge.merged_record_id)
        )
        gates = await rows(
            select(DecisionGateResult)
            .where(
                DecisionGateResult.evaluation_run_id == evaluation_run_id,
                DecisionGateResult.organization_id == self.organization_id,
            )
            .order_by(DecisionGateResult.solution_plan_record_id, DecisionGateResult.gate_id)
        )
        evidence = await rows(
            select(EvidenceAssessmentRecord)
            .where(
                EvidenceAssessmentRecord.evaluation_run_id == evaluation_run_id,
                EvidenceAssessmentRecord.organization_id == self.organization_id,
            )
            .order_by(EvidenceAssessmentRecord.evidence_id, EvidenceAssessmentRecord.field)
        )
        components = await rows(
            select(SolutionPlanComponent)
            .where(
                SolutionPlanComponent.evaluation_run_id == evaluation_run_id,
                SolutionPlanComponent.organization_id == self.organization_id,
            )
            .order_by(SolutionPlanComponent.solution_plan_record_id, SolutionPlanComponent.ordinal)
        )
        score_components = await rows(
            select(ScoreComponentRecord)
            .where(
                ScoreComponentRecord.evaluation_run_id == evaluation_run_id,
                ScoreComponentRecord.organization_id == self.organization_id,
            )
            .order_by(
                ScoreComponentRecord.solution_plan_record_id, ScoreComponentRecord.criterion_id
            )
        )
        bounds = await rows(
            select(ScoreBound)
            .where(
                ScoreBound.evaluation_run_id == evaluation_run_id,
                ScoreBound.organization_id == self.organization_id,
            )
            .order_by(ScoreBound.solution_plan_record_id, ScoreBound.dimension)
        )
        frontiers = await rows(
            select(RobustnessFrontier)
            .where(
                RobustnessFrontier.evaluation_run_id == evaluation_run_id,
                RobustnessFrontier.organization_id == self.organization_id,
            )
            .order_by(RobustnessFrontier.solution_plan_record_id, RobustnessFrontier.frontier_kind)
        )
        return EvaluationGraphSnapshot(
            evaluation_run=evaluation,
            discovery_run=discovery,
            solution_plans=plans,
            candidate_set_members=candidates,
            identity_merges=merges,
            decision_gate_results=gates,
            evidence_assessments=evidence,
            solution_plan_components=components,
            score_components=score_components,
            score_bounds=bounds,
            robustness_frontiers=frontiers,
        )

    async def add_counterfactual_record(
        self, record: CounterfactualRecordModel
    ) -> CounterfactualRecordModel:
        """Persist a non-circular counterfactual edge after resolving every hash."""

        self._assert_tenant(record.organization_id)
        self._assert_payload_hash(record.payload, record.record_hash, "counterfactual")
        references = {
            record.base_evaluation_payload_hash,
            record.generic_evaluation_payload_hash,
        }
        if record.alternate_evaluation_payload_hash is not None:
            references.add(record.alternate_evaluation_payload_hash)
        found = set(
            (
                await self.session.execute(
                    select(EvaluationRun.evaluation_payload_hash).where(
                        EvaluationRun.organization_id == self.organization_id,
                        EvaluationRun.evaluation_payload_hash.in_(references),
                    )
                )
            ).scalars()
        )
        if found != references:
            raise PersistenceConflict(
                "Counterfactual references an unknown tenant evaluation payload hash"
            )
        if record.record_hash in references:
            raise PersistenceConflict("Counterfactual record hash cannot reference itself")
        self.session.add(record)
        await self.add_outbox(
            aggregate_type="counterfactual_record",
            aggregate_id=record.id,
            event_type="counterfactual_record.persisted",
            event_key=f"counterfactual-record-persisted:{record.record_hash}",
            payload={
                "counterfactual_record_id": record.id,
                "record_hash": record.record_hash,
                "base_evaluation_payload_hash": record.base_evaluation_payload_hash,
            },
        )
        await self.session.flush()
        return record

    async def get_counterfactual_record(self, record_hash: str) -> CounterfactualRecordModel:
        return await _one_or_missing(
            self.session,
            select(CounterfactualRecordModel).where(
                CounterfactualRecordModel.organization_id == self.organization_id,
                CounterfactualRecordModel.record_hash == record_hash,
            ),
        )

    async def add_action_run(self, record: ActionRun) -> ActionRun:
        self._assert_tenant(record.organization_id)
        plan = await _one_or_missing(
            self.session,
            select(EvaluationSolutionPlan).where(
                EvaluationSolutionPlan.id == record.solution_plan_record_id,
                EvaluationSolutionPlan.organization_id == self.organization_id,
            ),
        )
        if plan.solution_plan_id != record.solution_plan_id:
            raise PersistenceConflict("Action run does not bind the exact Solution Plan")
        if plan.action != record.action:
            raise PersistenceConflict("Action run action does not match the frozen Solution Plan")
        evaluation = await _one_or_missing(
            self.session,
            select(EvaluationRun).where(
                EvaluationRun.id == plan.evaluation_run_id,
                EvaluationRun.organization_id == self.organization_id,
            ),
        )
        if evaluation.decision_id != record.decision_id:
            selected_decision = await _one_or_missing(
                self.session,
                select(DecisionRecord).where(
                    DecisionRecord.id == record.decision_id,
                    DecisionRecord.organization_id == self.organization_id,
                ),
            )
            if (
                selected_decision.supersedes_id != evaluation.decision_id
                or selected_decision.selected_solution_plan_id != record.solution_plan_id
                or selected_decision.payload.get("evaluation_payload_hash")
                != evaluation.evaluation_payload_hash
            ):
                raise PersistenceConflict("Action run plan does not belong to its Decision")
        if record.purchase_intent_id is not None:
            intent = await self.get_purchase_intent(record.purchase_intent_id)
            if (
                intent.decision_id != record.decision_id
                or intent.solution_plan_id != record.solution_plan_id
            ):
                raise PersistenceConflict("Action run Purchase Intent binding does not match")
        self._assert_payload_hash(record.payload, record.run_hash, "action run")
        self.session.add(record)
        await self.add_outbox(
            aggregate_type="action_run",
            aggregate_id=record.id,
            event_type="action_run.created",
            event_key=f"action-run-created:{record.run_hash}",
            payload={"action_run_id": record.id, "decision_id": record.decision_id},
        )
        await self.session.flush()
        return record

    async def add_result_artifact(self, record: ResultArtifact) -> ResultArtifact:
        self._assert_tenant(record.organization_id)
        await _one_or_missing(
            self.session,
            select(ActionRun.id).where(
                ActionRun.id == record.action_run_id,
                ActionRun.organization_id == self.organization_id,
            ),
        )
        if record.stack_patch_id is not None:
            await _one_or_missing(
                self.session,
                select(StackPatch.id).where(
                    StackPatch.id == record.stack_patch_id,
                    StackPatch.organization_id == self.organization_id,
                ),
            )
        if record.receipt_id is not None:
            await _one_or_missing(
                self.session,
                select(Receipt.id).where(
                    Receipt.id == record.receipt_id,
                    Receipt.organization_id == self.organization_id,
                ),
            )
        self._assert_payload_hash(record.payload, record.artifact_hash, "result artifact")
        self.session.add(record)
        await self.add_outbox(
            aggregate_type="action_run",
            aggregate_id=record.action_run_id,
            event_type="action_run.result_artifact.recorded",
            event_key=f"result-artifact-recorded:{record.artifact_hash}",
            payload={
                "action_run_id": record.action_run_id,
                "result_artifact_id": record.id,
                "artifact_type": record.artifact_type,
            },
        )
        await self.session.flush()
        return record

    async def get_action_run_snapshot(self, action_run_id: str) -> ActionRunSnapshot:
        action_run = await _one_or_missing(
            self.session,
            select(ActionRun).where(
                ActionRun.id == action_run_id,
                ActionRun.organization_id == self.organization_id,
            ),
        )
        artifacts = tuple(
            (
                await self.session.execute(
                    select(ResultArtifact)
                    .where(
                        ResultArtifact.action_run_id == action_run_id,
                        ResultArtifact.organization_id == self.organization_id,
                    )
                    .order_by(ResultArtifact.occurred_at, ResultArtifact.id)
                )
            )
            .scalars()
            .all()
        )
        return ActionRunSnapshot(action_run=action_run, result_artifacts=artifacts)

    async def get_purchase_intent(self, intent_id: str, *, lock: bool = False) -> PurchaseIntent:
        statement = select(PurchaseIntent).where(
            PurchaseIntent.id == intent_id,
            PurchaseIntent.organization_id == self.organization_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await _one_or_missing(self.session, statement)

    async def add_purchase_intent(self, record: PurchaseIntent) -> PurchaseIntent:
        self._assert_tenant(record.organization_id)
        self.session.add(record)
        await self.add_outbox(
            aggregate_type="purchase_intent",
            aggregate_id=record.id,
            event_type="purchase_intent.locked",
            event_key=f"purchase-intent-locked:{record.id}:{record.intent_hash}",
            payload={"purchase_intent_id": record.id, "intent_hash": record.intent_hash},
        )
        return record

    async def transition_purchase_intent(
        self,
        *,
        intent_id: str,
        state_field: str,
        allowed_from: set[str],
        to_state: str,
        event_key: str,
        actor_type: str,
        actor_id: str,
        reason_code: str,
        payload_hash: str,
        attempt_id: str | None = None,
        provider_event_ref: str | None = None,
    ) -> PurchaseIntent:
        if state_field not in {"approval_status", "payment_status", "fulfillment_status"}:
            raise ValueError("Unsupported state field")

        intent = await self.get_purchase_intent(intent_id, lock=True)
        current = str(getattr(intent, state_field))
        duplicate = (
            await self.session.execute(
                select(TransactionTransition).where(
                    TransactionTransition.organization_id == self.organization_id,
                    TransactionTransition.purchase_intent_id == intent_id,
                    TransactionTransition.event_key == event_key,
                )
            )
        ).scalar_one_or_none()
        if duplicate is not None:
            if duplicate.to_state != to_state or duplicate.payload_hash != payload_hash:
                raise PersistenceConflict(
                    "A transition event key was replayed with different semantics"
                )
            return intent

        if current not in allowed_from:
            raise PersistenceConflict(
                f"Transition {state_field} {current!r} -> {to_state!r} is not allowed"
            )

        setattr(intent, state_field, to_state)
        transition = TransactionTransition(
            id=new_id("tr"),
            organization_id=self.organization_id,
            purchase_intent_id=intent_id,
            from_state=current,
            to_state=to_state,
            attempt_id=attempt_id,
            actor_type=actor_type,
            actor_id=actor_id,
            reason_code=reason_code,
            event_key=event_key,
            provider_event_ref=provider_event_ref,
            payload_hash=payload_hash,
        )
        self.session.add(transition)
        await self.add_outbox(
            aggregate_type="purchase_intent",
            aggregate_id=intent_id,
            event_type=f"purchase_intent.{state_field}.changed",
            event_key=f"outbox:{event_key}",
            payload={
                "purchase_intent_id": intent_id,
                "state_field": state_field,
                "from": current,
                "to": to_state,
                "transition_id": transition.id,
            },
        )
        return intent

    async def supersede_approval_for_mutation(
        self, *, intent_id: str, current_intent_hash: str, mutation_event_key: str
    ) -> None:
        intent = await self.get_purchase_intent(intent_id, lock=True)
        if intent.intent_hash == current_intent_hash:
            return
        if intent.approval_status in {"PENDING", "APPROVED"}:
            intent.approval_status = "SUPERSEDED"
            await self.session.execute(
                update(ApprovalRequest)
                .where(
                    ApprovalRequest.organization_id == self.organization_id,
                    ApprovalRequest.purchase_intent_id == intent_id,
                    ApprovalRequest.status.in_(["PENDING", "APPROVED"]),
                )
                .values(status="SUPERSEDED")
            )
            await self.add_outbox(
                aggregate_type="purchase_intent",
                aggregate_id=intent_id,
                event_type="approval.superseded",
                event_key=mutation_event_key,
                payload={"purchase_intent_id": intent_id, "reason": "BOUND_INPUT_CHANGED"},
            )

    async def supersede_intents_for_decision_change(
        self,
        *,
        purchase_request_id: str,
        current_decision_id: str,
        proposal_id: str,
    ) -> int:
        """Invalidate executable state bound to older Decision versions atomically."""

        intents = (
            await self.session.execute(
                select(PurchaseIntent)
                .join(DecisionRecord, DecisionRecord.id == PurchaseIntent.decision_id)
                .where(
                    PurchaseIntent.organization_id == self.organization_id,
                    DecisionRecord.organization_id == self.organization_id,
                    DecisionRecord.purchase_request_id == purchase_request_id,
                    DecisionRecord.id != current_decision_id,
                )
                .with_for_update()
            )
        ).scalars()
        superseded = 0
        safe_pre_checkout_states = {
            "NOT_STARTED",
            "SESSION_CREATED",
            "CARDHOLDER_PENDING",
            "DECLINED",
            "EXPIRED",
            "FAILED",
        }
        for intent in intents:
            if intent.payment_status not in safe_pre_checkout_states:
                raise PersistenceConflict(
                    "A Decision cannot change while an older intent has an in-flight, paid, "
                    "or uncertain checkout."
                )
            changed = intent.approval_status in {"NOT_REQUESTED", "PENDING", "APPROVED"}
            if changed:
                intent.approval_status = "SUPERSEDED"
                await self.session.execute(
                    update(ApprovalRequest)
                    .where(
                        ApprovalRequest.organization_id == self.organization_id,
                        ApprovalRequest.purchase_intent_id == intent.id,
                        ApprovalRequest.status.in_(["PENDING", "APPROVED"]),
                    )
                    .values(status="SUPERSEDED")
                )
            if intent.payment_status in {"SESSION_CREATED", "CARDHOLDER_PENDING"}:
                intent.payment_status = "EXPIRED"
                await self.session.execute(
                    update(PaymentSession)
                    .where(
                        PaymentSession.organization_id == self.organization_id,
                        PaymentSession.purchase_intent_id == intent.id,
                        PaymentSession.status.in_(["SESSION_CREATED", "CARDHOLDER_PENDING"]),
                    )
                    .values(status="EXPIRED")
                )
                changed = True
            if not changed:
                continue
            await self.add_outbox(
                aggregate_type="purchase_intent",
                aggregate_id=intent.id,
                event_type="approval.superseded",
                event_key=f"decision-change:{proposal_id}:{intent.id}",
                payload={
                    "purchase_intent_id": intent.id,
                    "superseded_decision_id": intent.decision_id,
                    "current_decision_id": current_decision_id,
                    "reason": "DECISION_VERSION_CHANGED",
                },
            )
            superseded += 1
        return superseded

    async def record_approval_event(
        self,
        *,
        approval_request_id: str,
        intent_hash: str,
        actor_id: str,
        actor_role: str,
        action: str,
        event_key: str,
        reason: str | None = None,
    ) -> ApprovalEvent:
        approval = await _one_or_missing(
            self.session,
            select(ApprovalRequest)
            .where(
                ApprovalRequest.id == approval_request_id,
                ApprovalRequest.organization_id == self.organization_id,
            )
            .with_for_update(),
        )
        intent = await self.get_purchase_intent(approval.purchase_intent_id, lock=True)
        if intent_hash != approval.intent_hash or intent_hash != intent.intent_hash:
            raise PersistenceConflict("Approval does not bind the current exact intent hash")
        if approval.status not in {"PENDING", "APPROVED"}:
            raise PersistenceConflict(f"Approval request is {approval.status}")

        existing = (
            await self.session.execute(
                select(ApprovalEvent).where(
                    ApprovalEvent.organization_id == self.organization_id,
                    ApprovalEvent.event_key == event_key,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        event = ApprovalEvent(
            id=new_id("ape"),
            organization_id=self.organization_id,
            approval_request_id=approval_request_id,
            intent_hash=intent_hash,
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            event_key=event_key,
            reason=reason,
        )
        self.session.add(event)
        return event

    async def add_feedback(self, feedback: CandidateFeedback) -> CandidateFeedback:
        self._assert_tenant(feedback.organization_id)
        self.session.add(feedback)
        return feedback

    async def get_engagement(self, engagement_id: str, *, lock: bool = False) -> Engagement:
        statement = select(Engagement).where(
            Engagement.id == engagement_id,
            Engagement.organization_id == self.organization_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await _one_or_missing(self.session, statement)

    async def add_merchant_order(self, order: MerchantOrder) -> MerchantOrder:
        self._assert_tenant(order.organization_id)
        self.session.add(order)
        return order

    async def add_entitlement(self, entitlement: Entitlement) -> Entitlement:
        self._assert_tenant(entitlement.organization_id)
        self.session.add(entitlement)
        return entitlement

    async def get_receipt(self, receipt_id: str) -> Receipt:
        return await _one_or_missing(
            self.session,
            select(Receipt).where(
                Receipt.id == receipt_id,
                Receipt.organization_id == self.organization_id,
            ),
        )

    async def get_stack_snapshot(self, *, version: int | None = None) -> StackSnapshot:
        statement = select(StackSnapshot).where(
            StackSnapshot.organization_id == self.organization_id
        )
        if version is not None:
            statement = statement.where(StackSnapshot.version == version)
        else:
            statement = statement.order_by(StackSnapshot.version.desc()).limit(1)
        return await _one_or_missing(self.session, statement)

    async def add_stack_patch(self, patch: StackPatch) -> StackPatch:
        self._assert_tenant(patch.organization_id)
        snapshot = await self.get_stack_snapshot()
        if patch.base_version != snapshot.version or patch.base_snapshot_id != snapshot.id:
            patch.state = "CONFLICT"
        self.session.add(patch)
        return patch

    async def claim_idempotency(
        self,
        *,
        actor_id: str,
        operation: str,
        idempotency_key: str,
        request_hash: str,
    ) -> IdempotencyClaim:
        statement = (
            select(IdempotencyRecord)
            .where(
                IdempotencyRecord.organization_id == self.organization_id,
                IdempotencyRecord.actor_id == actor_id,
                IdempotencyRecord.operation == operation,
                IdempotencyRecord.idempotency_key == idempotency_key,
            )
            .with_for_update()
        )
        existing = (await self.session.execute(statement)).scalar_one_or_none()
        if existing is not None:
            if existing.request_hash != request_hash:
                raise IdempotencyConflict(
                    "Idempotency key was already used with a different request body"
                )
            return IdempotencyClaim(existing, replay=existing.state == "COMPLETED")

        record = IdempotencyRecord(
            id=new_id("idem"),
            organization_id=self.organization_id,
            actor_id=actor_id,
            operation=operation,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            state="STARTED",
            response_status=None,
            response_payload=None,
            response_reference=None,
        )
        try:
            async with self.session.begin_nested():
                self.session.add(record)
                await self.session.flush()
        except IntegrityError:
            existing = (await self.session.execute(statement)).scalar_one_or_none()
            if existing is None:
                raise PersistenceConflict(
                    "An idempotency claim raced and must be retried"
                ) from None
            if existing.request_hash != request_hash:
                raise IdempotencyConflict(
                    "Idempotency key was already used with a different request body"
                ) from None
            return IdempotencyClaim(existing, replay=existing.state == "COMPLETED")
        return IdempotencyClaim(record, replay=False)

    async def complete_idempotency(
        self,
        record: IdempotencyRecord,
        *,
        response_status: int,
        response_payload: dict[str, Any],
        response_reference: str | None = None,
    ) -> None:
        self._assert_tenant(record.organization_id)
        record.state = "COMPLETED"
        record.response_status = response_status
        record.response_payload = response_payload
        record.response_reference = response_reference

    async def add_outbox(
        self,
        *,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        event_key: str,
        payload: dict[str, Any],
    ) -> OutboxEvent:
        existing = (
            await self.session.execute(
                select(OutboxEvent).where(
                    OutboxEvent.organization_id == self.organization_id,
                    OutboxEvent.event_key == event_key,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        event = OutboxEvent(
            id=new_id("out"),
            organization_id=self.organization_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            event_key=event_key,
            payload=payload,
            occurred_at=datetime.now(UTC),
        )
        self.session.add(event)
        return event

    def _assert_tenant(self, organization_id: object) -> None:
        if organization_id != self.organization_id:
            raise PersistenceConflict("Cross-tenant write rejected")

    @staticmethod
    def _assert_payload_hash(payload: object, expected_hash: str, label: str) -> None:
        if content_hash(payload) != expected_hash:
            raise PersistenceConflict(f"{label.capitalize()} hash does not match its payload")
