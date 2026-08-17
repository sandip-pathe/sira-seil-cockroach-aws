"""Application service backed by PostgreSQL repositories and frozen fixtures."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import delete, func, select

from decision_engine import (
    DecisionGraphDecision,
    DecisionGraphInput,
    DecisionSourceBundle,
    compile_decision_graph_input,
    evaluate_decision_graph,
    load_demo_decision_source,
)
from domain import (
    DomainValidationError,
    InvalidTransitionError,
    Money,
    PaymentHandoffStatus,
    PaymentHandoffTransitionService,
)
from domain import (
    PaymentHandoff as DomainPaymentHandoff,
)
from persistence.database import Database
from persistence.mission_repository import MissionRepository
from persistence.models import (
    ActionRun,
    ApprovalEvent,
    ApprovalRequest,
    CalibrationRun,
    CandidateFeedback,
    CandidateSetMember,
    CounterfactualRecordModel,
    DecisionGateResult,
    DecisionRecord,
    DecisionSimulation,
    DecisionSourceSnapshot,
    DiscoveryRun,
    Engagement,
    EvaluationPipelineVersion,
    EvaluationRun,
    EvaluationSolutionPlan,
    EvidenceAssessmentRecord,
    IdempotencyRecord,
    IdentityMerge,
    Organization,
    OutboxEvent,
    OutcomeCheckpoint,
    PaymentHandoff,
    PurchaseBriefVersion,
    PurchaseIntent,
    PurchaseRequest,
    RequirementBriefVersion,
    ResultArtifact,
    RobustnessFrontier,
    ScoreBound,
    ScoreComponentRecord,
    SellerActivityEvent,
    SellerEvidenceAttachment,
    SellerPackDraft,
    SellerPackDraftRevision,
    SellerPackExportArtifact,
    SellerPackSuspension,
    SellerPackVersion,
    SellerProduct,
    SellerProductClaim,
    SellerReviewDecisionRecord,
    SellerReviewSubmission,
    SolutionPlanComponent,
    StackPatch,
    StackSnapshot,
    WorkflowRun,
)
from persistence.repositories import (
    IdempotencyConflict,
    PersistenceConflict,
    RecordNotFound,
    WorkflowRepository,
    new_id,
)

from .commercial_terms import (
    CommercialTermsConflict,
    build_demo_plan_commercial_terms,
    build_purchase_intent_payload,
)
from .decision_room_projection import project_decision_room
from .errors import ApiProblem, SetupBlocked
from .fixtures import (
    DEMO,
    DEMO_FIXTURE_LABEL,
    DEMO_SCENARIO_ID,
    DemoFixtureBundle,
    content_hash,
)
from .graph_ledger import DecisionLedgerMetadata, build_decision_ledger
from .graph_persistence import (
    EvaluationPersistenceMetadata,
    build_evaluation_graph_write,
    ensure_evaluation_pipeline_version,
)
from .marketplace import SellerOrganizationDirectory

DEMO_ORGANIZATION_ID = "org_consultco"
DEMO_ACTOR_ID = "usr_demo_requester"
_DECISION_MAKER_ROLES = frozenset({"can_view_context", "can_select_recommendation"})


class WorkflowService:
    """Use canonical database state for the complete first vertical."""

    def __init__(
        self,
        database: Database,
        fixtures: DemoFixtureBundle | None,
        *,
        allow_development_tenant_bootstrap: bool = False,
        seller_directory: SellerOrganizationDirectory | None = None,
        clock: Callable[[], datetime] | None = None,
        quote_clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.database = database
        self.fixtures = fixtures
        self.allow_development_tenant_bootstrap = allow_development_tenant_bootstrap
        self.seller_directory = seller_directory
        self._clock = clock or (lambda: datetime.now(UTC))
        self._quote_clock = quote_clock or self._clock

    def _now(self) -> datetime:
        return self._as_utc(self._clock())

    def _quote_now(self) -> datetime:
        """Return the as-of time for quote-bound fixture operations only."""

        return self._as_utc(self._quote_clock())

    def _fixture_bundle(self) -> DemoFixtureBundle:
        if self.fixtures is None:
            raise SetupBlocked(
                "production_decision_pipeline",
                ["EVIDENCE_PROVIDER_CONFIGURATION", "AGENT_RUNTIME_CONFIGURATION"],
            )
        return self.fixtures

    def _request_evaluation_metadata(self, request: PurchaseRequest) -> dict[str, Any]:
        scenario_id = request.payload.get("scenario_id")
        if self.fixtures is None:
            return {
                "evaluation_mode": "PROVIDER_CONFIGURATION_REQUIRED",
                "scenario_id": scenario_id,
                "fixture_label": None,
            }
        if scenario_id == DEMO_SCENARIO_ID:
            return {
                "evaluation_mode": DEMO_FIXTURE_LABEL,
                "scenario_id": DEMO_SCENARIO_ID,
                "fixture_label": DEMO_FIXTURE_LABEL,
            }
        return {
            "evaluation_mode": "SCENARIO_SELECTION_REQUIRED",
            "scenario_id": scenario_id,
            "fixture_label": None,
        }

    @staticmethod
    def _bind_graph_input(
        graph_input: DecisionGraphInput,
        *,
        purchase_brief_id: str,
        purchase_brief_version: int,
        preference_weights: dict[str, int] | None = None,
    ) -> DecisionGraphInput:
        return replace(
            graph_input,
            versions=replace(
                graph_input.versions,
                request_version=f"{purchase_brief_id}:v{purchase_brief_version}",
                policy_version=f"consultco_policy_v{purchase_brief_version}",
            ),
            preferences=tuple(
                replace(
                    item,
                    weight=(preference_weights or {}).get(item.criterion_id, item.weight),
                )
                for item in graph_input.preferences
            ),
        )

    @classmethod
    def _demo_graph_input(
        cls,
        *,
        purchase_brief_id: str,
        purchase_brief_version: int,
        preference_weights: dict[str, int] | None = None,
    ) -> DecisionGraphInput:
        return cls._bind_graph_input(
            compile_decision_graph_input(load_demo_decision_source(DEMO)),
            purchase_brief_id=purchase_brief_id,
            purchase_brief_version=purchase_brief_version,
            preference_weights=preference_weights,
        )

    @staticmethod
    def _ledger_preference_weights(ledger: dict[str, Any]) -> dict[str, int]:
        return {
            str(component["criterion_id"]): int(component["weight"])
            for plan in ledger["solution_plans"]
            for component in plan["score_components"]
        }

    def _verified_demo_replay_source(
        self, run: EvaluationRun, ledger: dict[str, Any]
    ) -> tuple[DecisionGraphInput, DecisionGraphDecision]:
        """Reconstruct a demo input only when its persisted hashes prove exact identity."""

        graph_input = self._demo_graph_input(
            purchase_brief_id=str(ledger["purchase_brief_id"]),
            purchase_brief_version=int(ledger["purchase_brief_version"]),
            preference_weights=self._ledger_preference_weights(ledger),
        )
        created_at = datetime.fromisoformat(str(ledger["created_at"]).replace("Z", "+00:00"))
        replay = evaluate_decision_graph(
            graph_input,
            evaluation_id=str(ledger["evaluation"]["evaluation_id"]),
            generated_at=created_at,
        )
        payload = run.input_payload
        mismatch: list[str] = []
        if content_hash(payload) != run.input_payload_hash:
            mismatch.append("input_payload_hash")
        if payload.get("schema_version") != "decision_graph_input_hashes_v1":
            mismatch.append("input_schema")
        if payload.get("run_kind") != "BASE" or run.run_kind != "BASE":
            mismatch.append("run_kind")
        if content_hash(payload.get("versions")) != content_hash(asdict(graph_input.versions)):
            mismatch.append("versions")
        run_versions = {field: getattr(run, field) for field in asdict(graph_input.versions)}
        if run_versions != asdict(graph_input.versions):
            mismatch.append("version_columns")
        if (
            payload.get("candidate_set_version") != run.candidate_set_version
            or payload.get("quote_set_version") != run.quote_set_version
            or payload.get("risk_rule_set_version") != "demo_risk_rules_v1"
        ):
            mismatch.append("source_set_versions")
        try:
            stored_evaluated_at = datetime.fromisoformat(
                str(payload.get("evaluated_at")).replace("Z", "+00:00")
            )
        except ValueError:
            stored_evaluated_at = None
        run_evaluated_at = run.evaluated_at
        if run_evaluated_at.tzinfo is None:
            run_evaluated_at = run_evaluated_at.replace(tzinfo=UTC)
        if (
            stored_evaluated_at != graph_input.evaluated_at
            or run_evaluated_at != graph_input.evaluated_at
        ):
            mismatch.append("evaluated_at")
        try:
            stored_frozen_hashes = dict(payload.get("frozen_input_hashes", []))
        except (TypeError, ValueError):
            stored_frozen_hashes = {}
        if stored_frozen_hashes != dict(replay.base.frozen_input_hashes):
            mismatch.append("frozen_input_hashes")
        stored_removed_ids = payload.get("removed_private_fact_ids", [])
        if not isinstance(stored_removed_ids, list) or stored_removed_ids != list(
            replay.base.removed_private_fact_ids
        ):
            mismatch.append("removed_private_fact_ids")
        if (
            replay.base.evaluation_payload_hash != run.evaluation_payload_hash
            or content_hash(run.evaluation_payload) != run.evaluation_payload_hash
        ):
            mismatch.append("evaluation_payload_hash")
        if (
            run.purchase_request_id != ledger["request_id"]
            or run.purchase_brief_id != ledger["purchase_brief_id"]
            or run.decision_id != ledger["decision_id"]
        ):
            mismatch.append("aggregate_binding")
        if mismatch:
            raise ApiProblem(
                code="REPLAY_INPUT_UNAVAILABLE",
                message=(
                    "The exact frozen evaluation input is unavailable; replay was not run "
                    "against a substitute fixture."
                ),
                status_code=409,
                details={"evaluation_run_id": run.id, "mismatches": sorted(set(mismatch))},
            )
        return graph_input, replay

    def _demo_graph_artifacts(
        self,
        *,
        organization_id: str,
        request_id: str,
        decision_id: str,
        decision_version: int,
        supersedes_decision_id: str | None,
        purchase_brief_id: str,
        purchase_brief_version: int,
        requirement_brief_id: str,
        requirement_brief_version: int,
        stack_patch_id: str,
        preference_weights: dict[str, int] | None = None,
        created_at: datetime | None = None,
        source_input: DecisionGraphInput | None = None,
    ) -> tuple[
        DecisionGraphInput,
        DecisionGraphDecision,
        dict[str, Any],
        dict[str, Any],
        dict[str, dict[str, Any]],
    ]:
        """Run the deterministic graph and bind DB-owned artifact identifiers."""

        fixtures = self._fixture_bundle()
        graph_input = (
            self._demo_graph_input(
                purchase_brief_id=purchase_brief_id,
                purchase_brief_version=purchase_brief_version,
                preference_weights=preference_weights,
            )
            if source_input is None
            else self._bind_graph_input(
                source_input,
                purchase_brief_id=purchase_brief_id,
                purchase_brief_version=purchase_brief_version,
                preference_weights=preference_weights,
            )
        )
        artifact_created_at = created_at or graph_input.evaluated_at
        graph_decision = evaluate_decision_graph(
            graph_input,
            evaluation_id=f"eval_{decision_id}",
            generated_at=artifact_created_at,
        )
        component_names = {
            pack_id: str(pack["identity"]["product_name"])
            for pack_id, pack in fixtures.packs.items()
        }
        ledger = build_decision_ledger(
            graph_decision,
            graph_input,
            DecisionLedgerMetadata(
                decision_id=decision_id,
                decision_version=decision_version,
                supersedes_decision_id=supersedes_decision_id,
                request_id=request_id,
                purchase_brief_id=purchase_brief_id,
                purchase_brief_version=purchase_brief_version,
                requirement_brief_id=requirement_brief_id,
                requirement_brief_version=requirement_brief_version,
                company_profile_version=int(fixtures.buyer_passport["version"]),
                stack_snapshot=int(fixtures.stack_lock["snapshot"]),
                policy_version=purchase_brief_version,
                created_at=artifact_created_at,
                selected_stack_patch_id=stack_patch_id,
            ),
            component_names=component_names,
        )
        patch = fixtures.stack_patch()
        patch.update(
            {
                "patch_id": stack_patch_id,
                "organization_id": organization_id,
                "decision_id": decision_id,
                "solution_plan_id": graph_decision.base.selected_plan_id,
                "created_at": artifact_created_at.isoformat().replace("+00:00", "Z"),
            }
        )
        patch["content_hash"] = content_hash(
            {key: value for key, value in patch.items() if key != "content_hash"}
        )
        commercial_terms = build_demo_plan_commercial_terms(
            fixtures,
            graph_input,
            graph_decision,
            stack_patch_id=stack_patch_id,
        )
        return graph_input, graph_decision, ledger, patch, commercial_terms

    async def _persist_base_graph(
        self,
        *,
        repository: WorkflowRepository,
        organization_id: str,
        request_id: str,
        purchase_brief_id: str,
        decision_id: str,
        graph_input: DecisionGraphInput,
        graph_decision: DecisionGraphDecision,
        ledger: dict[str, Any],
        commercial_terms_by_plan_id: dict[str, dict[str, Any]],
    ) -> str:
        metadata = EvaluationPersistenceMetadata(
            organization_id=organization_id,
            purchase_request_id=request_id,
            purchase_brief_id=purchase_brief_id,
            decision_id=decision_id,
            candidate_set_version="demo_candidate_set_v1",
            quote_set_version="demo_quote_set_v1",
            risk_rule_set_version="demo_risk_rules_v1",
            valuation_currency="USD",
        )
        await ensure_evaluation_pipeline_version(repository, graph_input, metadata)
        graph_write = build_evaluation_graph_write(
            graph_decision,
            graph_input,
            ledger,
            metadata,
            commercial_terms_by_plan_id=commercial_terms_by_plan_id,
        )
        await repository.add_evaluation_graph(graph_write)
        return graph_write.evaluation_run.id

    async def health(self) -> str:
        return "configured" if await self.database.is_ready() else "unavailable"

    async def reset_demo(self, organization_id: str) -> dict[str, Any]:
        fixtures = self._fixture_bundle()
        if organization_id != DEMO_ORGANIZATION_ID:
            raise ApiProblem(
                code="DEMO_TENANT_REQUIRED",
                message="The deterministic reset is scoped to the fictional demo tenant.",
                status_code=403,
            )

        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            # Reset is deliberately destructive only inside the explicit development tenant.
            for model in (
                SellerReviewDecisionRecord,
                SellerPackExportArtifact,
                SellerPackSuspension,
                SellerReviewSubmission,
                SellerEvidenceAttachment,
                SellerPackVersion,
                SellerPackDraftRevision,
                SellerProductClaim,
                SellerPackDraft,
                SellerActivityEvent,
                SellerProduct,
                ResultArtifact,
                ActionRun,
                RobustnessFrontier,
                ScoreBound,
                ScoreComponentRecord,
                SolutionPlanComponent,
                DecisionGateResult,
                EvidenceAssessmentRecord,
                EvaluationSolutionPlan,
                IdentityMerge,
                CandidateSetMember,
                DiscoveryRun,
                CounterfactualRecordModel,
                EvaluationRun,
                EvaluationPipelineVersion,
                ApprovalEvent,
                PaymentHandoff,
                ApprovalRequest,
                OutcomeCheckpoint,
                PurchaseIntent,
                CandidateFeedback,
                Engagement,
                CalibrationRun,
                DecisionSimulation,
                DecisionRecord,
                DecisionSourceSnapshot,
                RequirementBriefVersion,
                PurchaseBriefVersion,
                StackPatch,
                StackSnapshot,
                WorkflowRun,
                OutboxEvent,
                IdempotencyRecord,
                PurchaseRequest,
            ):
                await session.execute(delete(model).where(model.organization_id == organization_id))

            organization = await session.get(Organization, organization_id)
            if organization is None:
                session.add(
                    Organization(
                        id=organization_id, name="ConsultCo (fictional fixture)", version=1
                    )
                )
                # PostgreSQL enforces the tenant-root foreign key during the
                # autoflushes performed while building the evaluation graph.
                await session.flush()

            brief = deepcopy(fixtures.purchase_brief)
            requirement = deepcopy(fixtures.requirement_brief)
            graph_input, graph_decision, ledger, patch, commercial_terms = (
                self._demo_graph_artifacts(
                    organization_id=organization_id,
                    request_id="req_demo",
                    decision_id="dec_consultco_v1",
                    decision_version=1,
                    supersedes_decision_id=None,
                    purchase_brief_id=str(brief["purchase_brief_id"]),
                    purchase_brief_version=int(brief["version"]),
                    requirement_brief_id=str(requirement["requirement_brief_id"]),
                    requirement_brief_version=int(requirement["version"]),
                    stack_patch_id="patch_consultco_fixture_d",
                )
            )
            request = PurchaseRequest(
                id="req_demo",
                organization_id=organization_id,
                intent="Find meeting intelligence for ten consultants",
                status="DECISION_READY",
                visibility="SELECTIVE",
                version=1,
                payload={
                    "intent": "Find meeting intelligence for ten consultants",
                    "jtbd_id": "capture_meeting_decisions",
                    "scenario_id": DEMO_SCENARIO_ID,
                    "evaluation_mode": DEMO_FIXTURE_LABEL,
                    "fixture_label": DEMO_FIXTURE_LABEL,
                },
                request_hash=content_hash({"request_id": "req_demo", "version": 1}),
                created_at=graph_input.evaluated_at,
                updated_at=graph_input.evaluated_at,
            )
            session.add(request)
            await session.flush()
            brief_record = PurchaseBriefVersion(
                id=brief["purchase_brief_id"],
                organization_id=organization_id,
                purchase_request_id=request.id,
                version=brief["version"],
                status=brief["status"],
                payload=brief,
                content_hash=brief["content_hash"],
                supersedes_id=None,
            )
            session.add(brief_record)
            await session.flush()
            requirement_record = RequirementBriefVersion(
                id=requirement["requirement_brief_id"],
                organization_id=organization_id,
                purchase_request_id=request.id,
                purchase_brief_id=brief["purchase_brief_id"],
                version=requirement["version"],
                payload=requirement,
                content_hash=requirement["content_hash"],
            )
            session.add(requirement_record)
            await session.flush()
            decision_record = DecisionRecord(
                id=ledger["decision_id"],
                organization_id=organization_id,
                purchase_request_id=request.id,
                purchase_brief_id=brief["purchase_brief_id"],
                version=1,
                supersedes_id=None,
                decision_hash=ledger["decision_hash"],
                selected_solution_plan_id=ledger["selected_solution_plan_id"],
                payload={
                    "ledger": ledger,
                    "graph": {
                        "evaluation_id": graph_decision.base.evaluation_id,
                        "evaluation_payload_hash": (graph_decision.base.evaluation_payload_hash),
                        "graph_decision_hash": graph_decision.decision_hash,
                        "frozen_input_hashes": dict(graph_decision.base.frozen_input_hashes),
                        "evaluated_at": graph_input.evaluated_at.isoformat().replace("+00:00", "Z"),
                    },
                },
                created_at=graph_input.evaluated_at,
                updated_at=graph_input.evaluated_at,
            )
            decision_record.payload = {
                **decision_record.payload,
                "decision_view": project_decision_room(
                    request=request,
                    decision=decision_record,
                    fixtures=fixtures,
                    roles=_DECISION_MAKER_ROLES,
                    party="BUYER",
                    intent=None,
                    approval=None,
                    handoff=None,
                    superseded_by=None,
                ),
            }
            session.add(decision_record)
            await session.flush()
            evaluation_run_id = await self._persist_base_graph(
                repository=repository,
                organization_id=organization_id,
                request_id=request.id,
                purchase_brief_id=str(brief["purchase_brief_id"]),
                decision_id=decision_record.id,
                graph_input=graph_input,
                graph_decision=graph_decision,
                ledger=ledger,
                commercial_terms_by_plan_id=commercial_terms,
            )
            decision_record.payload = {
                **decision_record.payload,
                "graph": {
                    **decision_record.payload["graph"],
                    "evaluation_run_id": evaluation_run_id,
                },
            }
            stack_snapshot = StackSnapshot(
                id="stack_consultco_v1",
                organization_id=organization_id,
                version=1,
                manifest=fixtures.stack_manifest,
                lock=fixtures.stack_lock,
                lock_hash=fixtures.stack_lock["content_hash"],
            )
            session.add(stack_snapshot)
            await session.flush()
            await self._add_demo_decision_source(
                repository=repository,
                organization_id=organization_id,
                actor_id=DEMO_ACTOR_ID,
                request=request,
                brief=brief_record,
                requirement=requirement_record,
                stack_snapshot=stack_snapshot,
            )
            await session.flush()
            session.add(
                StackPatch(
                    id=patch["patch_id"],
                    organization_id=organization_id,
                    base_snapshot_id="stack_consultco_v1",
                    base_version=patch["base_snapshot"],
                    state=patch["status"],
                    payload=patch,
                    patch_hash=patch["content_hash"],
                )
            )
        return {
            "organization_id": organization_id,
            "request_id": "req_demo",
            "decision_id": ledger["decision_id"],
            "fixture_label": "DEVELOPMENT_FIXTURE_NON_PRODUCTION",
        }

    async def create_purchase_request(
        self,
        *,
        organization_id: str,
        actor_id: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        scenario_id = body.get("scenario_id")
        if (
            self.fixtures is not None
            and scenario_id is not None
            and scenario_id != DEMO_SCENARIO_ID
        ):
            raise ApiProblem(
                code="DEMO_SCENARIO_UNSUPPORTED",
                message="Only the declared meeting-intelligence demo scenario can be evaluated.",
                status_code=422,
                next_action="select_supported_demo_scenario",
                details={"supported_scenario_id": DEMO_SCENARIO_ID},
            )
        payload = deepcopy(body)
        if self.fixtures is None:
            payload.update(
                {
                    "evaluation_mode": "PROVIDER_CONFIGURATION_REQUIRED",
                    "fixture_label": None,
                }
            )
        elif scenario_id == DEMO_SCENARIO_ID:
            payload.update(
                {
                    "evaluation_mode": DEMO_FIXTURE_LABEL,
                    "fixture_label": DEMO_FIXTURE_LABEL,
                }
            )
        else:
            payload.update(
                {
                    "evaluation_mode": "SCENARIO_SELECTION_REQUIRED",
                    "fixture_label": None,
                }
            )
        request_hash = content_hash(body)
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            await self._ensure_organization(session, organization_id)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation="purchase_requests.create",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if claim.replay:
                return int(claim.record.response_status or 201), dict(
                    claim.record.response_payload or {}
                )

            request_id = new_id("req")
            record = PurchaseRequest(
                id=request_id,
                organization_id=organization_id,
                intent=body["intent"],
                status="DRAFT",
                visibility=body.get("visibility", "SELECTIVE"),
                version=1,
                payload=payload,
                request_hash=request_hash,
            )
            await repository.add_purchase_request(record)
            mission_id = body.get("mission_id")
            if mission_id:
                mission_repository = MissionRepository(session, organization_id)
                try:
                    mission = await mission_repository.get_for_actor(
                        str(mission_id), actor_id, lock=True
                    )
                except RecordNotFound as error:
                    raise ApiProblem(
                        code="MISSION_NOT_FOUND",
                        message="The originating mission is unavailable.",
                        status_code=404,
                        next_action="restore_mission",
                    ) from error
                await mission_repository.append_event(
                    mission,
                    event_type="authority.decision.created",
                    event_key=f"decision-created:{request_id}",
                    actor_type="SYSTEM",
                    actor_id="authority-kernel",
                    payload={
                        "summary": "Created a governed buying decision",
                        "details": {
                            "request_id": request_id,
                            "status": "DRAFT",
                            "next": "evaluation",
                        },
                    },
                )
                await mission_repository.add_artifact(
                    mission,
                    kind="purchase_proposal",
                    title="Governed buying decision",
                    authority="VERIFIED",
                    payload={
                        "request_id": request_id,
                        "intent": body["intent"],
                        "status": "DRAFT",
                        "authority_path": [
                            "evaluation",
                            "exact approval",
                            "human-operated payment handoff",
                            "outcome measurement",
                        ],
                    },
                    source_refs=[{"type": "decision_request", "id": request_id}],
                    created_by="authority-kernel",
                )
                await mission_repository.checkpoint(mission)
            if self.fixtures is not None and scenario_id == DEMO_SCENARIO_ID:
                # These records are referenced by the frozen decision-source snapshot below.
                # Flush explicitly because the models do not declare ORM relationships that
                # would otherwise give SQLAlchemy a dependency order for the inserts.
                await session.flush()
                brief, requirement = await self._add_request_briefs(
                    session, organization_id, record
                )
                stack_snapshot = await self._ensure_demo_stack_snapshot(session, organization_id)
                await session.flush()
                await self._add_demo_decision_source(
                    repository=repository,
                    organization_id=organization_id,
                    actor_id=actor_id,
                    request=record,
                    brief=brief,
                    requirement=requirement,
                    stack_snapshot=stack_snapshot,
                )
            response = self._request_view(record)
            await repository.complete_idempotency(
                claim.record,
                response_status=201,
                response_payload=response,
                response_reference=request_id,
            )
            return 201, response

    async def get_purchase_request(self, organization_id: str, request_id: str) -> dict[str, Any]:
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            record = await self._not_found(
                repository.get_purchase_request(request_id), "PURCHASE_REQUEST"
            )
            decision_id = (
                await session.execute(
                    select(DecisionRecord.id)
                    .where(
                        DecisionRecord.organization_id == organization_id,
                        DecisionRecord.purchase_request_id == request_id,
                    )
                    .order_by(DecisionRecord.version.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            result = self._request_view(record)
            result["decision_id"] = decision_id
            workflow = (
                await session.execute(
                    select(WorkflowRun.id)
                    .where(
                        WorkflowRun.organization_id == organization_id,
                        WorkflowRun.aggregate_id == request_id,
                    )
                    .order_by(WorkflowRun.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            result["workflow_id"] = workflow
            return result

    async def discover(
        self,
        *,
        organization_id: str,
        actor_id: str,
        request_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        fixtures = self._fixture_bundle()
        body_hash = content_hash({"request_id": request_id, "operation": "discover"})
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation="purchase_requests.discover",
                idempotency_key=idempotency_key,
                request_hash=body_hash,
            )
            if claim.replay:
                return dict(claim.record.response_payload or {})
            request = await self._not_found(
                repository.get_purchase_request(request_id, lock=True), "PURCHASE_REQUEST"
            )
            evaluation = self._request_evaluation_metadata(request)
            if evaluation["evaluation_mode"] != DEMO_FIXTURE_LABEL:
                raise ApiProblem(
                    code="DEMO_SCENARIO_REQUIRED",
                    message=(
                        "This build only evaluates the declared meeting-intelligence demo "
                        "scenario; arbitrary request text remains an unevaluated draft."
                    ),
                    status_code=409,
                    next_action="select_supported_demo_scenario",
                    details={"supported_scenario_id": DEMO_SCENARIO_ID},
                )
            brief = (
                await session.execute(
                    select(PurchaseBriefVersion)
                    .where(
                        PurchaseBriefVersion.organization_id == organization_id,
                        PurchaseBriefVersion.purchase_request_id == request_id,
                    )
                    .order_by(PurchaseBriefVersion.version.desc())
                    .limit(1)
                )
            ).scalar_one()
            requirement = (
                await session.execute(
                    select(RequirementBriefVersion)
                    .where(
                        RequirementBriefVersion.organization_id == organization_id,
                        RequirementBriefVersion.purchase_request_id == request_id,
                        RequirementBriefVersion.purchase_brief_id == brief.id,
                    )
                    .order_by(RequirementBriefVersion.version.desc())
                    .limit(1)
                )
            ).scalar_one()
            try:
                source_snapshot = await repository.get_decision_source_snapshot(
                    request_id, purchase_brief_id=brief.id
                )
                source_input = compile_decision_graph_input(
                    DecisionSourceBundle.from_payload(source_snapshot.payload)
                )
            except (PersistenceConflict, RecordNotFound, ValueError) as exc:
                raise ApiProblem(
                    code="DECISION_SOURCE_UNAVAILABLE",
                    message=(
                        "The accepted Buyer Passport, Stackfile, brief, Pack, evidence, and "
                        "offer bundle is missing or invalid."
                    ),
                    status_code=409,
                    next_action="compile_decision_source",
                ) from exc
            previous_decision = (
                await session.execute(
                    select(DecisionRecord)
                    .where(
                        DecisionRecord.organization_id == organization_id,
                        DecisionRecord.purchase_request_id == request_id,
                    )
                    .order_by(DecisionRecord.version.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            decision_version = 1 if previous_decision is None else previous_decision.version + 1

            decision_id = new_id("dec")
            stack_patch_id = f"patch_{decision_id}"
            graph_input, graph_decision, ledger, stack_patch, commercial_terms = (
                self._demo_graph_artifacts(
                    organization_id=organization_id,
                    request_id=request_id,
                    decision_id=decision_id,
                    decision_version=decision_version,
                    supersedes_decision_id=(
                        previous_decision.id if previous_decision is not None else None
                    ),
                    purchase_brief_id=brief.id,
                    purchase_brief_version=brief.version,
                    requirement_brief_id=requirement.id,
                    requirement_brief_version=requirement.version,
                    stack_patch_id=stack_patch_id,
                    source_input=source_input,
                )
            )
            decision_record = DecisionRecord(
                id=decision_id,
                organization_id=organization_id,
                purchase_request_id=request_id,
                purchase_brief_id=brief.id,
                version=decision_version,
                supersedes_id=previous_decision.id if previous_decision is not None else None,
                decision_hash=ledger["decision_hash"],
                selected_solution_plan_id=ledger["selected_solution_plan_id"],
                payload={
                    "ledger": ledger,
                    "graph": {
                        "evaluation_id": graph_decision.base.evaluation_id,
                        "evaluation_payload_hash": (graph_decision.base.evaluation_payload_hash),
                        "graph_decision_hash": graph_decision.decision_hash,
                        "frozen_input_hashes": dict(graph_decision.base.frozen_input_hashes),
                        "evaluated_at": graph_input.evaluated_at.isoformat().replace("+00:00", "Z"),
                    },
                },
                created_at=graph_input.evaluated_at,
                updated_at=graph_input.evaluated_at,
            )
            decision_record.payload = {
                **decision_record.payload,
                "decision_view": project_decision_room(
                    request=request,
                    decision=decision_record,
                    fixtures=fixtures,
                    roles=_DECISION_MAKER_ROLES,
                    party="BUYER",
                    intent=None,
                    approval=None,
                    handoff=None,
                    superseded_by=None,
                ),
            }
            session.add(decision_record)
            snapshot = (
                await session.execute(
                    select(StackSnapshot).where(
                        StackSnapshot.organization_id == organization_id,
                        StackSnapshot.id == source_snapshot.stack_snapshot_id,
                    )
                )
            ).scalar_one_or_none()
            if snapshot is None:
                raise ApiProblem(
                    code="DECISION_SOURCE_UNAVAILABLE",
                    message="The exact Stackfile snapshot bound to the decision source is absent.",
                    status_code=409,
                    next_action="compile_decision_source",
                )
            session.add(
                StackPatch(
                    id=stack_patch_id,
                    organization_id=organization_id,
                    base_snapshot_id=snapshot.id,
                    base_version=int(stack_patch["base_snapshot"]),
                    state=str(stack_patch["status"]),
                    payload=stack_patch,
                    patch_hash=str(stack_patch["content_hash"]),
                )
            )
            evaluation_run_id = await self._persist_base_graph(
                repository=repository,
                organization_id=organization_id,
                request_id=request_id,
                purchase_brief_id=brief.id,
                decision_id=decision_id,
                graph_input=graph_input,
                graph_decision=graph_decision,
                ledger=ledger,
                commercial_terms_by_plan_id=commercial_terms,
            )
            decision_record.payload = {
                **decision_record.payload,
                "graph": {
                    **decision_record.payload["graph"],
                    "evaluation_run_id": evaluation_run_id,
                },
            }
            request.status = "DECISION_READY"
            workflow_id = (
                f"wf_discover_{request_id}"
                if decision_version == 1
                else f"wf_discover_{request_id}_v{decision_version}"
            )
            session.add(
                WorkflowRun(
                    id=workflow_id,
                    organization_id=organization_id,
                    aggregate_type="purchase_request",
                    aggregate_id=request_id,
                    operation="discover",
                    status="COMPLETED",
                    result_reference=f"/v1/decisions/{decision_id}",
                    safe_error_code=None,
                    event_log=[
                        {"id": "1", "status": "RUNNING", "message": "Evaluating four Packs"},
                        {"id": "2", "status": "COMPLETED", "message": "Decision ready"},
                    ],
                )
            )
            response = self._workflow_urls(workflow_id)
            await repository.complete_idempotency(
                claim.record,
                response_status=202,
                response_payload=response,
                response_reference=workflow_id,
            )
            return response

    async def decision_view(self, organization_id: str, request_id: str) -> dict[str, Any]:
        async with self.database.transaction(organization_id) as session:
            decision = (
                await session.execute(
                    select(DecisionRecord)
                    .where(
                        DecisionRecord.organization_id == organization_id,
                        DecisionRecord.purchase_request_id == request_id,
                    )
                    .order_by(DecisionRecord.version.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if decision is None:
                raise self._missing("DECISION")
            view = cast(dict[str, Any], deepcopy(decision.payload["decision_view"]))
            view.pop("payment", None)
            view.pop("fulfillment", None)
            view.pop("receipt", None)
            view["payment_handoff"] = None
            intent = (
                await session.execute(
                    select(PurchaseIntent)
                    .where(
                        PurchaseIntent.organization_id == organization_id,
                        PurchaseIntent.decision_id == decision.id,
                    )
                    .order_by(PurchaseIntent.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if intent is not None:
                view["approval"]["status"] = intent.approval_status
                view["approval"]["intent_hash"] = intent.intent_hash
                approval = (
                    await session.execute(
                        select(ApprovalRequest)
                        .where(
                            ApprovalRequest.organization_id == organization_id,
                            ApprovalRequest.purchase_intent_id == intent.id,
                        )
                        .order_by(ApprovalRequest.created_at.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if approval is not None:
                    view["approval"].update(
                        {
                            "approval_request_id": approval.id,
                        }
                    )
                handoff = (
                    await session.execute(
                        select(PaymentHandoff)
                        .where(
                            PaymentHandoff.organization_id == organization_id,
                            PaymentHandoff.purchase_intent_id == intent.id,
                        )
                        .order_by(PaymentHandoff.created_at.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if handoff is not None:
                    view["payment_handoff"] = {
                        **self._payment_handoff_view(handoff),
                        "href": f"/v1/payment-handoffs/{handoff.id}/open",
                    }
            return view

    async def get_purchase_brief(self, organization_id: str, request_id: str) -> dict[str, Any]:
        async with self.database.transaction(organization_id) as session:
            brief = (
                await session.execute(
                    select(PurchaseBriefVersion)
                    .where(
                        PurchaseBriefVersion.organization_id == organization_id,
                        PurchaseBriefVersion.purchase_request_id == request_id,
                    )
                    .order_by(PurchaseBriefVersion.version.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if brief is None:
                raise self._missing("PURCHASE_BRIEF")
            return self._purchase_brief_view(brief.payload)

    async def get_requirement_brief(
        self,
        organization_id: str,
        brief_id: str,
        *,
        actor_id: str,
        actor_party: str | None,
    ) -> dict[str, Any]:
        if actor_party == "SELLER":
            async with self.database.transaction(organization_id) as session:
                engagement = (
                    await session.execute(
                        select(Engagement).where(
                            Engagement.seller_organization_id == organization_id,
                            Engagement.requirement_brief_id == brief_id,
                            Engagement.expected_seller_actor_id == actor_id,
                            Engagement.grant_status == "ACTIVE",
                            Engagement.status.not_in(["DECLINED", "EXPIRED"]),
                        )
                    )
                ).scalar_one_or_none()
                if engagement is None:
                    raise ApiProblem(
                        code="REQUIREMENT_BRIEF_ENGAGEMENT_REQUIRED",
                        message=(
                            "The seller is not a participant in an active engagement for this "
                            "exact sanitized Requirement Brief."
                        ),
                        status_code=403,
                    )
                return deepcopy(engagement.seller_visible_requirement_brief)
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            brief = await self._not_found(
                repository.get_requirement_brief(brief_id), "REQUIREMENT_BRIEF"
            )
            return self._requirement_brief_view(brief.payload)

    async def run_calibration(
        self,
        *,
        organization_id: str,
        actor_id: str,
        request_id: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        request_hash = content_hash(body)
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation="calibration_runs.create",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if claim.replay:
                return int(claim.record.response_status or 201), dict(
                    claim.record.response_payload or {}
                )
            await self._not_found(repository.get_purchase_request(request_id), "PURCHASE_REQUEST")
            brief = (
                await session.execute(
                    select(PurchaseBriefVersion)
                    .where(
                        PurchaseBriefVersion.organization_id == organization_id,
                        PurchaseBriefVersion.purchase_request_id == request_id,
                    )
                    .order_by(PurchaseBriefVersion.version.desc())
                    .limit(1)
                )
            ).scalar_one()
            run_id = new_id("cal")
            try:
                source_snapshot = await repository.get_decision_source_snapshot(
                    request_id, purchase_brief_id=brief.id
                )
                graph_input = self._bind_graph_input(
                    compile_decision_graph_input(
                        DecisionSourceBundle.from_payload(source_snapshot.payload)
                    ),
                    purchase_brief_id=brief.id,
                    purchase_brief_version=brief.version,
                )
            except (PersistenceConflict, RecordNotFound, ValueError) as exc:
                raise ApiProblem(
                    code="DECISION_SOURCE_UNAVAILABLE",
                    message="Calibration requires the exact accepted decision source bundle.",
                    status_code=409,
                    next_action="compile_decision_source",
                ) from exc
            graph = evaluate_decision_graph(
                graph_input,
                evaluation_id=f"calibration_{run_id}",
                generated_at=graph_input.evaluated_at,
            )
            plan_by_product = {
                plan.components[-1].component_id: plan
                for plan in graph.base.plans
                if plan.components and plan.components[-1].source_type == "PACK"
            }
            status_by_candidate = {
                candidate.pack_id: plan_by_product[candidate.product_id].status.value
                for candidate in graph_input.candidates
                if candidate.product_id in plan_by_product
            }
            failure_actual = status_by_candidate.get(
                body["known_failure_candidate_id"], "UNAVAILABLE"
            )
            qualifier_actual = status_by_candidate.get(
                body["expected_qualifier_candidate_id"], "UNAVAILABLE"
            )
            known_alternatives = brief.payload.get("known_alternatives", [])
            current_actual = (
                "CURRENT_APPROACH"
                if body["current_approach_id"] in known_alternatives
                else "UNAVAILABLE"
            )
            results = [
                {
                    "candidate_id": body["known_failure_candidate_id"],
                    "expected": "FAIL",
                    "actual": failure_actual,
                    "matches": failure_actual == "SIRA_INELIGIBLE",
                },
                {
                    "candidate_id": body["current_approach_id"],
                    "expected": "CURRENT_APPROACH",
                    "actual": current_actual,
                    "matches": current_actual == "CURRENT_APPROACH",
                },
                {
                    "candidate_id": body["expected_qualifier_candidate_id"],
                    "expected": "QUALIFY",
                    "actual": qualifier_actual,
                    "matches": qualifier_actual in {"ELIGIBLE", "ELIGIBLE_WITH_EXCEPTION"},
                },
            ]
            proposal: dict[str, Any] | None = None
            if body.get("proposed_changes"):
                proposal_id = new_id("proposal")
                proposal = {
                    "proposal_id": proposal_id,
                    "base_purchase_brief_id": brief.id,
                    "proposed_purchase_brief_version": brief.version + 1,
                    "status": "PROPOSED",
                    "changes": deepcopy(body["proposed_changes"]),
                    "requires_authorized_acceptance": True,
                    "ranking_effect": False,
                }
            run = CalibrationRun(
                id=run_id,
                organization_id=organization_id,
                purchase_request_id=request_id,
                purchase_brief_id=brief.id,
                result={"results": results, "proposal": proposal},
                proposed_purchase_brief_id=None,
                accepted_at=None,
            )
            session.add(run)
            response = {
                "id": run_id,
                "purchase_request_id": request_id,
                "purchase_brief_version": brief.version,
                "results": results,
                "proposal": proposal,
                "proposal_effective": False,
            }
            await repository.complete_idempotency(
                claim.record,
                response_status=201,
                response_payload=response,
                response_reference=run_id,
            )
            return 201, response

    async def candidate_action(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_party: str | None,
        request_id: str,
        candidate_id: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        fixtures = self._fixture_bundle()
        request_hash = content_hash(
            {"request_id": request_id, "candidate_id": candidate_id, **body}
        )
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation="candidate_actions.create",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if claim.replay:
                return int(claim.record.response_status or 201), dict(
                    claim.record.response_payload or {}
                )
            request = await self._not_found(
                repository.get_purchase_request(request_id, lock=True), "PURCHASE_REQUEST"
            )
            current_brief_id = (
                await session.execute(
                    select(PurchaseBriefVersion.id)
                    .where(
                        PurchaseBriefVersion.organization_id == organization_id,
                        PurchaseBriefVersion.purchase_request_id == request_id,
                    )
                    .order_by(PurchaseBriefVersion.version.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if current_brief_id is None:
                raise self._missing("PURCHASE_BRIEF")
            requirement_brief = (
                await session.execute(
                    select(RequirementBriefVersion)
                    .where(
                        RequirementBriefVersion.organization_id == organization_id,
                        RequirementBriefVersion.purchase_request_id == request_id,
                        RequirementBriefVersion.purchase_brief_id == current_brief_id,
                    )
                    .order_by(RequirementBriefVersion.version.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if requirement_brief is None:
                raise self._missing("REQUIREMENT_BRIEF")
            if candidate_id not in fixtures.packs:
                raise self._missing("CANDIDATE")
            feedback_id = new_id("fb")
            proposed_change = body.get("proposed_criterion_change")
            proposal_id = new_id("proposal") if proposed_change is not None else None
            feedback = CandidateFeedback(
                id=feedback_id,
                organization_id=organization_id,
                purchase_request_id=request_id,
                candidate_id=candidate_id,
                action=body["action"],
                reason=body["reason"],
                actor_id=actor_id,
                proposed_change=(
                    {
                        "proposal_id": proposal_id,
                        "base_purchase_brief_id": current_brief_id,
                        "status": "PROPOSED",
                        "changes": [deepcopy(proposed_change)],
                        "ranking_effect": False,
                    }
                    if proposed_change is not None
                    else None
                ),
            )
            await repository.add_feedback(feedback)
            engagement_id: str | None = None
            if body["action"] == "REQUEST_OFFER":
                if request.visibility == "PRIVATE":
                    raise ApiProblem(
                        code="PRIVATE_REQUEST_OUTREACH_FORBIDDEN",
                        message="A private Decision request cannot initiate seller outreach.",
                        status_code=409,
                        next_action="change_request_visibility",
                    )
                if actor_party != "BUYER":
                    raise ApiProblem(
                        code="VERIFIED_BUYER_REQUIRED",
                        message="Only the verified buyer may open a seller engagement.",
                        status_code=403,
                        next_action="authenticate_party_identity",
                    )
                seller_actor_id = fixtures.packs[candidate_id].get("seller_id")
                if (
                    not isinstance(seller_actor_id, str)
                    or not seller_actor_id.strip()
                    or seller_actor_id == actor_id
                ):
                    raise ApiProblem(
                        code="ENGAGEMENT_PARTICIPANTS_INVALID",
                        message=(
                            "The selected candidate has no distinct authorized seller principal."
                        ),
                        status_code=409,
                    )
                binding = (
                    self.seller_directory.resolve(candidate_id)
                    if self.seller_directory is not None
                    else None
                )
                if binding is None or binding.seller_actor_id != seller_actor_id:
                    raise ApiProblem(
                        code="SELLER_ORGANIZATION_BINDING_REQUIRED",
                        message=("The candidate is not bound to a verified seller organization."),
                        status_code=409,
                        next_action="verify_seller_organization",
                    )
                seller_organization = await session.get(
                    Organization, binding.seller_organization_id
                )
                if seller_organization is None:
                    if not self.allow_development_tenant_bootstrap:
                        raise ApiProblem(
                            code="SELLER_ORGANIZATION_BINDING_REQUIRED",
                            message="The verified seller organization is unavailable.",
                            status_code=409,
                        )
                    session.add(
                        Organization(
                            id=binding.seller_organization_id,
                            name=f"{seller_actor_id} (fictional fixture)",
                            version=1,
                        )
                    )
                    await session.flush()
                engagement_id = new_id("eng")
                seller_visible_brief = self._requirement_brief_view(requirement_brief.payload)
                granted_at = self._now()
                grant_scope = "SANITIZED_BRIEF_AND_CONTACT_CONSENT"
                grant_hash = content_hash(
                    {
                        "engagement_id": engagement_id,
                        "buyer_organization_id": organization_id,
                        "seller_organization_id": binding.seller_organization_id,
                        "buyer_actor_id": actor_id,
                        "seller_actor_id": seller_actor_id,
                        "requirement_brief_hash": requirement_brief.content_hash,
                        "grant_scope": grant_scope,
                    }
                )
                session.add(
                    Engagement(
                        id=engagement_id,
                        organization_id=organization_id,
                        purchase_request_id=request_id,
                        requirement_brief_id=requirement_brief.id,
                        requirement_brief_version=requirement_brief.version,
                        requirement_brief_hash=requirement_brief.content_hash,
                        candidate_id=candidate_id,
                        seller_organization_id=binding.seller_organization_id,
                        expected_buyer_actor_id=actor_id,
                        expected_seller_actor_id=seller_actor_id,
                        grant_scope=grant_scope,
                        grant_status="ACTIVE",
                        grant_hash=grant_hash,
                        seller_visible_requirement_brief=seller_visible_brief,
                        granted_at=granted_at,
                        status="SELLER_REVIEWING",
                        buyer_consented=False,
                        seller_consented=False,
                        contact_exchange=None,
                    )
                )
            response = {
                "id": feedback_id,
                "request_id": request_id,
                "candidate_id": candidate_id,
                "action": body["action"],
                "reason": body["reason"],
                "engagement_id": engagement_id,
                "contact_details_revealed": False,
                "proposal_effective": False,
                "proposal_id": proposal_id,
            }
            await repository.complete_idempotency(
                claim.record,
                response_status=201,
                response_payload=response,
                response_reference=feedback_id,
            )
            return 201, response

    async def record_consent(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_party: str | None,
        engagement_id: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        if actor_party not in {"BUYER", "SELLER"}:
            raise ApiProblem(
                code="VERIFIED_PARTY_REQUIRED",
                message="Consent requires a verified buyer or seller identity.",
                status_code=403,
                next_action="authenticate_party_identity",
            )
        request_hash = content_hash({"engagement_id": engagement_id, **body})
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation="engagement_consent.create",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            engagement = await self._not_found(
                repository.get_engagement(engagement_id, lock=True), "ENGAGEMENT"
            )
            if claim.replay:
                # Consent projections are privacy-sensitive mutable state.  Returning
                # an old cached response could re-disclose contacts after either party
                # has since declined, so replays always project canonical state.
                return int(claim.record.response_status or 200), self._engagement_view(engagement)
            expected_actor_id = (
                engagement.expected_buyer_actor_id
                if actor_party == "BUYER"
                else engagement.expected_seller_actor_id
            )
            expected_organization_id = (
                engagement.organization_id
                if actor_party == "BUYER"
                else engagement.seller_organization_id
            )
            if (
                engagement.grant_status != "ACTIVE"
                or organization_id != expected_organization_id
                or actor_id != expected_actor_id
            ):
                raise ApiProblem(
                    code="CONSENT_ACTOR_MISMATCH",
                    message=(
                        "The verified actor is not an authorized participant in this engagement."
                    ),
                    status_code=403,
                )
            if not body["consent"]:
                if actor_party == "BUYER":
                    engagement.buyer_consented = False
                    engagement.buyer_consent_actor_id = None
                else:
                    engagement.seller_consented = False
                    engagement.seller_consent_actor_id = None
                engagement.status = "DECLINED"
                engagement.contact_exchange = None
            elif actor_party == "BUYER":
                if engagement.seller_consent_actor_id == actor_id:
                    raise ApiProblem(
                        code="CONSENT_SEPARATION_OF_PARTIES",
                        message="One actor cannot provide both buyer and seller consent.",
                        status_code=403,
                    )
                engagement.buyer_consented = True
                engagement.buyer_consent_actor_id = actor_id
                engagement.status = (
                    "INTRODUCTION_READY"
                    if engagement.seller_consented
                    else "SELLER_CONSENT_PENDING"
                )
            else:
                if engagement.buyer_consent_actor_id == actor_id:
                    raise ApiProblem(
                        code="CONSENT_SEPARATION_OF_PARTIES",
                        message="One actor cannot provide both buyer and seller consent.",
                        status_code=403,
                    )
                engagement.seller_consented = True
                engagement.seller_consent_actor_id = actor_id
                engagement.status = (
                    "INTRODUCTION_READY" if engagement.buyer_consented else "BUYER_CONSENT_PENDING"
                )
            if body["consent"] and engagement.buyer_consented and engagement.seller_consented:
                engagement.contact_exchange = {
                    "buyer": engagement.expected_buyer_actor_id,
                    "seller": engagement.expected_seller_actor_id,
                }
            response = self._engagement_view(engagement)
            await repository.complete_idempotency(
                claim.record,
                response_status=200,
                response_payload=response,
                response_reference=engagement.id,
            )
            return 200, response

    async def get_decision(self, organization_id: str, decision_id: str) -> dict[str, Any]:
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            decision = await self._not_found(repository.get_decision(decision_id), "DECISION")
            return deepcopy(decision.payload["ledger"])

    async def counterfactuals(self, organization_id: str, decision_id: str) -> dict[str, Any]:
        self._fixture_bundle()
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            decision = await self._not_found(repository.get_decision(decision_id), "DECISION")
            ledger = deepcopy(decision.payload["ledger"])
            run = await self._not_found(
                repository.get_evaluation_run(decision_id), "EVALUATION_RUN"
            )

        graph_input, replay = self._verified_demo_replay_source(run, ledger)
        if replay.generic.selected_plan_id is None or replay.base.selected_plan_id is None:
            raise ApiProblem(
                code="DECISION_SELECTION_UNAVAILABLE",
                message="The frozen counterfactual has no selected Solution Plan.",
                status_code=409,
            )
        plan_by_id = {plan.plan_id: plan for plan in replay.base.plans}
        generic_plan = plan_by_id[replay.generic.selected_plan_id]
        company_plan = plan_by_id[replay.base.selected_plan_id]
        pack_by_product = {
            candidate.product_id: candidate.pack_id for candidate in graph_input.candidates
        }
        generic_candidate = pack_by_product.get(
            generic_plan.components[-1].component_id,
            generic_plan.components[-1].component_id,
        )
        company_candidate = pack_by_product.get(
            company_plan.components[-1].component_id,
            company_plan.components[-1].component_id,
        )
        stored = ledger["counterfactuals"][0]
        return {
            "decision_id": decision_id,
            "generic_selected_candidate_id": generic_candidate,
            "company_aware_selected_candidate_id": company_candidate,
            "decisive_private_fact_ids": list(stored["removed_fact_ids"]),
            "generic_result_hash": replay.generic.evaluation_payload_hash,
            "company_aware_result_hash": replay.base.evaluation_payload_hash,
            "changed": generic_candidate != company_candidate,
            "explanation": (
                "Removing the smallest recorded set of private company facts changes the "
                "supported winner; the hashes bind both evaluations."
            ),
            "remaining_uncertainties": [
                "Live provider authorization and entitlement verification remain external."
            ],
        }

    async def simulate_decision(
        self,
        *,
        organization_id: str,
        actor_id: str,
        decision_id: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        self._fixture_bundle()
        request_hash = content_hash({"decision_id": decision_id, **body})
        overrides = body["preference_weight_overrides"]
        if any(
            isinstance(weight, bool) or not isinstance(weight, int) or not 1 <= weight <= 5
            for weight in overrides.values()
        ):
            raise ApiProblem(
                code="SIMULATION_WEIGHT_INVALID",
                message="Simulation preference weights must be integers from 1 to 5.",
                status_code=422,
            )

        async with self.database.transaction(organization_id) as session:
            source_repository = WorkflowRepository(session, organization_id)
            source_decision = await self._not_found(
                source_repository.get_decision(decision_id), "DECISION"
            )
            source_ledger = deepcopy(source_decision.payload["ledger"])
            source_run = await self._not_found(
                source_repository.get_evaluation_run(decision_id), "EVALUATION_RUN"
            )
        graph_input, _baseline_replay = self._verified_demo_replay_source(source_run, source_ledger)
        known_criteria = {item.criterion_id for item in graph_input.preferences}
        unknown = sorted(set(overrides).difference(known_criteria))
        if unknown:
            raise ApiProblem(
                code="SIMULATION_CRITERION_UNKNOWN",
                message="A simulation override referenced an unknown criterion.",
                status_code=422,
                details={"criterion_ids": unknown},
            )

        simulated_input = replace(
            graph_input,
            preferences=tuple(
                replace(item, weight=overrides.get(item.criterion_id, item.weight))
                for item in graph_input.preferences
            ),
        )
        simulated = evaluate_decision_graph(
            simulated_input,
            evaluation_id=f"sim_eval_{decision_id}",
            generated_at=simulated_input.evaluated_at,
        )
        evaluation = (
            simulated.generic if body["context_mode"] == "GENERIC_REQUEST_ONLY" else simulated.base
        )
        if evaluation.selected_plan_id is None:
            raise ApiProblem(
                code="SIMULATION_NO_EXECUTABLE_PLAN",
                message="The simulation produced no executable plan.",
                status_code=409,
            )

        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation="decision_simulations.create",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if claim.replay:
                return int(claim.record.response_status or 201), dict(
                    claim.record.response_payload or {}
                )
            decision = await self._not_found(repository.get_decision(decision_id), "DECISION")
            ledger = decision.payload["ledger"]

            result_payload = {
                "simulation_id": new_id("sim"),
                "decision_id": decision_id,
                "context_mode": body["context_mode"],
                "baseline_solution_plan_id": ledger["selected_solution_plan_id"],
                "simulated_solution_plan_id": evaluation.selected_plan_id,
                "simulated_order": list(evaluation.ranked_plan_ids),
                "input_hash": request_hash,
                "authoritative": False,
                "ranking_effect": False,
            }
            result_payload["result_hash"] = content_hash(result_payload)
            existing = (
                await session.execute(
                    select(DecisionSimulation).where(
                        DecisionSimulation.organization_id == organization_id,
                        DecisionSimulation.decision_id == decision_id,
                        DecisionSimulation.actor_id == actor_id,
                        DecisionSimulation.input_hash == request_hash,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                response = deepcopy(existing.result_payload)
            else:
                session.add(
                    DecisionSimulation(
                        id=result_payload["simulation_id"],
                        organization_id=organization_id,
                        decision_id=decision_id,
                        actor_id=actor_id,
                        input_hash=request_hash,
                        input_payload=deepcopy(body),
                        result_hash=result_payload["result_hash"],
                        result_payload=result_payload,
                        authoritative=False,
                    )
                )
                response = result_payload
            await repository.complete_idempotency(
                claim.record,
                response_status=201,
                response_payload=response,
                response_reference=response["simulation_id"],
            )
            return 201, response

    async def replay_evaluation(
        self, organization_id: str, evaluation_run_id: str
    ) -> dict[str, Any]:
        self._fixture_bundle()
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            run = await self._not_found(
                repository.get_evaluation_run(evaluation_run_id), "EVALUATION_RUN"
            )
            if run.decision_id is None:
                raise ApiProblem(
                    code="REPLAY_INPUT_UNAVAILABLE",
                    message="The frozen evaluation is not bound to a Decision Ledger.",
                    status_code=409,
                )
            decision = await self._not_found(repository.get_decision(run.decision_id), "DECISION")
            ledger = deepcopy(decision.payload["ledger"])

        self._verified_demo_replay_source(run, ledger)
        preference_weights = self._ledger_preference_weights(ledger)
        selected_plan = next(
            plan
            for plan in ledger["solution_plans"]
            if plan["solution_plan_id"] == ledger["selected_solution_plan_id"]
        )
        created_at = datetime.fromisoformat(str(ledger["created_at"]).replace("Z", "+00:00"))
        _graph_input, replay, replayed_ledger, _patch, _commercial_terms = (
            self._demo_graph_artifacts(
                organization_id=organization_id,
                request_id=str(ledger["request_id"]),
                decision_id=decision.id,
                decision_version=int(ledger["decision_version"]),
                supersedes_decision_id=ledger["supersedes_decision_id"],
                purchase_brief_id=str(ledger["purchase_brief_id"]),
                purchase_brief_version=int(ledger["purchase_brief_version"]),
                requirement_brief_id=str(ledger["requirement_brief_id"]),
                requirement_brief_version=int(ledger["requirement_brief_version"]),
                stack_patch_id=str(selected_plan["stack_patch_id"]),
                preference_weights=preference_weights,
                created_at=created_at,
            )
        )
        stored_statuses = {
            str(item["pack_id"]): str(item["status"]) for item in ledger["component_results"]
        }
        replayed_statuses = {
            str(item["pack_id"]): str(item["status"])
            for item in replayed_ledger["component_results"]
        }
        stored_order = list(ledger["evaluation"]["ranked_solution_plan_ids"])
        replayed_order = list(replay.base.ranked_plan_ids)
        counterfactual_matches = (
            ledger["counterfactuals"][0]["record_hash"] == replay.counterfactual.record_hash
        )
        stored_hash = str(ledger["decision_hash"])
        replayed_hash = str(replayed_ledger["decision_hash"])
        ordering_matches = stored_order == replayed_order
        statuses_match = stored_statuses == replayed_statuses
        return {
            "evaluation_run_id": run.id,
            "decision_id": decision.id,
            "stored_decision_hash": stored_hash,
            "replayed_decision_hash": replayed_hash,
            "ordering_matches": ordering_matches,
            "statuses_match": statuses_match,
            "counterfactual_matches": counterfactual_matches,
            "byte_stable": (
                stored_hash == replayed_hash
                and ordering_matches
                and statuses_match
                and counterfactual_matches
            ),
        }

    async def decide_proposal(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_roles: frozenset[str],
        step_up_verified: bool,
        brief_id: str,
        proposal_id: str,
        accept: bool,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        if not step_up_verified:
            raise ApiProblem(
                code="STEP_UP_REQUIRED",
                message="Recent step-up authentication is required to change decision policy.",
                status_code=403,
                next_action="authenticate",
            )
        if not actor_roles.intersection(
            {"operations_owner", "policy_owner", "security_privacy_owner"}
        ):
            raise ApiProblem(
                code="PROPOSAL_AUTHORITY_REQUIRED",
                message="The verified actor lacks authority to change the Purchase Brief.",
                status_code=403,
            )
        operation = "brief_proposals.accept" if accept else "brief_proposals.reject"
        request_hash = content_hash(
            {
                "brief_id": brief_id,
                "proposal_id": proposal_id,
                "decision": "ACCEPT" if accept else "REJECT",
                **body,
            }
        )
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation=operation,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if claim.replay:
                return int(claim.record.response_status or 200), dict(
                    claim.record.response_payload or {}
                )
            base = (
                await session.execute(
                    select(PurchaseBriefVersion)
                    .where(
                        PurchaseBriefVersion.id == brief_id,
                        PurchaseBriefVersion.organization_id == organization_id,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if base is None:
                raise self._missing("PURCHASE_BRIEF")
            owner, proposal = await self._find_proposal(
                session, organization_id, brief_id, proposal_id
            )
            if proposal.get("status") != "PROPOSED":
                raise ApiProblem(
                    code="PROPOSAL_ALREADY_DECIDED",
                    message="The proposal is no longer pending authorized acceptance.",
                    status_code=409,
                )
            if base.status != "APPROVED":
                raise ApiProblem(
                    code="PROPOSAL_BASE_SUPERSEDED",
                    message="The proposal targets a Purchase Brief that is no longer current.",
                    status_code=409,
                    next_action="review_current_decision",
                )

            resulting_id: str | None = None
            resulting_version: int | None = None
            resulting_decision_id: str | None = None
            resulting_decision_hash: str | None = None
            resulting_decision_version: int | None = None
            now = self._now()
            if accept:
                current_version = (
                    await session.execute(
                        select(func.max(PurchaseBriefVersion.version)).where(
                            PurchaseBriefVersion.organization_id == organization_id,
                            PurchaseBriefVersion.purchase_request_id == base.purchase_request_id,
                        )
                    )
                ).scalar_one()
                resulting_version = int(current_version or 0) + 1
                resulting_id = new_id("pb")
                payload = self._apply_proposal_changes(
                    deepcopy(base.payload), list(proposal.get("changes", []))
                )
                payload.update(
                    {
                        "purchase_brief_id": resulting_id,
                        "version": resulting_version,
                        "supersedes_version": base.version,
                        "status": "APPROVED",
                        "created_at": now.isoformat().replace("+00:00", "Z"),
                    }
                )
                payload["content_hash"] = content_hash(
                    {key: value for key, value in payload.items() if key != "content_hash"}
                )
                resulting_brief_record = PurchaseBriefVersion(
                    id=resulting_id,
                    organization_id=organization_id,
                    purchase_request_id=base.purchase_request_id,
                    version=resulting_version,
                    status="APPROVED",
                    payload=payload,
                    content_hash=payload["content_hash"],
                    supersedes_id=base.id,
                )
                session.add(resulting_brief_record)

                base_requirement = (
                    await session.execute(
                        select(RequirementBriefVersion)
                        .where(
                            RequirementBriefVersion.organization_id == organization_id,
                            RequirementBriefVersion.purchase_request_id == base.purchase_request_id,
                            RequirementBriefVersion.purchase_brief_id == base.id,
                        )
                        .order_by(RequirementBriefVersion.version.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if base_requirement is None:
                    raise ApiProblem(
                        code="REQUIREMENT_BRIEF_MISSING",
                        message="The current seller-safe Requirement Brief is unavailable.",
                        status_code=409,
                    )
                requirement_version = (
                    await session.execute(
                        select(func.max(RequirementBriefVersion.version)).where(
                            RequirementBriefVersion.organization_id == organization_id,
                            RequirementBriefVersion.purchase_request_id == base.purchase_request_id,
                        )
                    )
                ).scalar_one()
                requirement_id = new_id("rb")
                requirement_payload = deepcopy(base_requirement.payload)
                requirement_payload.update(
                    {
                        "requirement_brief_id": requirement_id,
                        "purchase_brief_id": resulting_id,
                        "purchase_brief_version": resulting_version,
                        "version": int(requirement_version or 0) + 1,
                        "expires_at": (now + timedelta(hours=24))
                        .isoformat()
                        .replace("+00:00", "Z"),
                    }
                )
                requirement_payload["content_hash"] = content_hash(
                    {
                        key: value
                        for key, value in requirement_payload.items()
                        if key != "content_hash"
                    }
                )
                resulting_requirement_record = RequirementBriefVersion(
                    id=requirement_id,
                    organization_id=organization_id,
                    purchase_request_id=base.purchase_request_id,
                    purchase_brief_id=resulting_id,
                    version=requirement_payload["version"],
                    payload=requirement_payload,
                    content_hash=requirement_payload["content_hash"],
                )
                session.add(resulting_requirement_record)

                previous_decision = (
                    await session.execute(
                        select(DecisionRecord)
                        .where(
                            DecisionRecord.organization_id == organization_id,
                            DecisionRecord.purchase_request_id == base.purchase_request_id,
                        )
                        .order_by(DecisionRecord.version.desc())
                        .limit(1)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                resulting_decision_version = (
                    1 if previous_decision is None else previous_decision.version + 1
                )
                resulting_decision_id = new_id("dec")
                stack_patch_id = f"patch_{resulting_decision_id}"
                preference_weights = {
                    str(item["criterion_id"]): int(item["weight"])
                    for item in payload["preferences"]
                }
                try:
                    base_source = await repository.get_decision_source_snapshot(
                        base.purchase_request_id, purchase_brief_id=base.id
                    )
                    source_payload = deepcopy(base_source.payload)
                    source_payload["purchase_brief"] = deepcopy(payload)
                    source_payload["requirement_brief"] = deepcopy(requirement_payload)
                    source_hash = content_hash(source_payload)
                    source_snapshot = await repository.add_decision_source_snapshot(
                        DecisionSourceSnapshot(
                            id=f"dss_{base.purchase_request_id}_v{resulting_version}",
                            organization_id=organization_id,
                            purchase_request_id=base.purchase_request_id,
                            purchase_brief_id=resulting_id,
                            stack_snapshot_id=base_source.stack_snapshot_id,
                            version=resulting_version,
                            source_kind=base_source.source_kind,
                            payload=source_payload,
                            content_hash=source_hash,
                            accepted_by_actor_id=actor_id,
                            accepted_at=now,
                        )
                    )
                    source_input = compile_decision_graph_input(
                        DecisionSourceBundle.from_payload(source_snapshot.payload)
                    )
                except (PersistenceConflict, RecordNotFound, ValueError) as exc:
                    raise ApiProblem(
                        code="DECISION_SOURCE_UNAVAILABLE",
                        message=(
                            "The accepted rule change could not be bound to its prior frozen "
                            "decision source."
                        ),
                        status_code=409,
                        next_action="compile_decision_source",
                    ) from exc
                (
                    graph_input,
                    graph_decision,
                    graph_ledger,
                    graph_patch,
                    commercial_terms,
                ) = self._demo_graph_artifacts(
                    organization_id=organization_id,
                    request_id=base.purchase_request_id,
                    decision_id=resulting_decision_id,
                    decision_version=resulting_decision_version,
                    supersedes_decision_id=(
                        previous_decision.id if previous_decision is not None else None
                    ),
                    purchase_brief_id=resulting_id,
                    purchase_brief_version=resulting_version,
                    requirement_brief_id=requirement_id,
                    requirement_brief_version=int(requirement_payload["version"]),
                    stack_patch_id=stack_patch_id,
                    preference_weights=preference_weights,
                    created_at=now,
                    source_input=source_input,
                )
                fixtures = self._fixture_bundle()
                request_record = await self._not_found(
                    repository.get_purchase_request(base.purchase_request_id),
                    "PURCHASE_REQUEST",
                )
                resulting_decision_hash = graph_ledger["decision_hash"]
                stack_snapshot = (
                    await session.execute(
                        select(StackSnapshot).where(
                            StackSnapshot.organization_id == organization_id,
                            StackSnapshot.id == source_snapshot.stack_snapshot_id,
                        )
                    )
                ).scalar_one_or_none()
                if stack_snapshot is None:
                    raise ApiProblem(
                        code="STACK_SNAPSHOT_MISSING",
                        message="The Decision cannot bind its proposed Stackfile change.",
                        status_code=409,
                    )
                session.add(
                    StackPatch(
                        id=graph_patch["patch_id"],
                        organization_id=organization_id,
                        base_snapshot_id=stack_snapshot.id,
                        base_version=graph_patch["base_snapshot"],
                        state=graph_patch["status"],
                        payload=graph_patch,
                        patch_hash=graph_patch["content_hash"],
                    )
                )
                decision_record = DecisionRecord(
                    id=resulting_decision_id,
                    organization_id=organization_id,
                    purchase_request_id=base.purchase_request_id,
                    purchase_brief_id=resulting_id,
                    version=resulting_decision_version,
                    supersedes_id=(previous_decision.id if previous_decision is not None else None),
                    decision_hash=resulting_decision_hash,
                    selected_solution_plan_id=graph_ledger["selected_solution_plan_id"],
                    payload={
                        "ledger": graph_ledger,
                        "graph": {
                            "evaluation_id": graph_decision.base.evaluation_id,
                            "evaluation_payload_hash": (
                                graph_decision.base.evaluation_payload_hash
                            ),
                            "graph_decision_hash": graph_decision.decision_hash,
                            "frozen_input_hashes": dict(graph_decision.base.frozen_input_hashes),
                            "evaluated_at": graph_input.evaluated_at.isoformat().replace(
                                "+00:00", "Z"
                            ),
                        },
                    },
                    created_at=graph_input.evaluated_at,
                    updated_at=graph_input.evaluated_at,
                )
                decision_record.payload = {
                    **decision_record.payload,
                    "decision_view": project_decision_room(
                        request=request_record,
                        decision=decision_record,
                        fixtures=fixtures,
                        roles=_DECISION_MAKER_ROLES,
                        party="BUYER",
                        intent=None,
                        approval=None,
                        handoff=None,
                        superseded_by=None,
                    ),
                }
                session.add(decision_record)
                evaluation_run_id = await self._persist_base_graph(
                    repository=repository,
                    organization_id=organization_id,
                    request_id=base.purchase_request_id,
                    purchase_brief_id=resulting_id,
                    decision_id=resulting_decision_id,
                    graph_input=graph_input,
                    graph_decision=graph_decision,
                    ledger=graph_ledger,
                    commercial_terms_by_plan_id=commercial_terms,
                )
                decision_record.payload = {
                    **decision_record.payload,
                    "graph": {
                        **decision_record.payload["graph"],
                        "evaluation_run_id": evaluation_run_id,
                    },
                }
                try:
                    await repository.supersede_intents_for_decision_change(
                        purchase_request_id=base.purchase_request_id,
                        current_decision_id=resulting_decision_id,
                        proposal_id=proposal_id,
                    )
                except PersistenceConflict as exc:
                    raise ApiProblem(
                        code="DECISION_CHANGE_BLOCKED_BY_EXECUTION",
                        message=(
                            "An older Decision has an in-flight, paid, or uncertain action and "
                            "must be reconciled before its rules can change."
                        ),
                        status_code=409,
                        next_action="reconcile_existing_action",
                    ) from exc
                base.status = "SUPERSEDED"

            decided = {
                **proposal,
                "status": "ACCEPTED" if accept else "REJECTED",
                "decided_by": actor_id,
                "decision_reason": body["reason"],
                "decided_at": now.isoformat().replace("+00:00", "Z"),
                "resulting_purchase_brief_id": resulting_id,
                "resulting_decision_id": resulting_decision_id,
                "ranking_effect": accept,
            }
            if isinstance(owner, CalibrationRun):
                owner.result = {**owner.result, "proposal": decided}
                owner.proposed_purchase_brief_id = resulting_id
                owner.accepted_at = now if accept else None
            else:
                owner.proposed_change = decided

            response = {
                "proposal_id": proposal_id,
                "base_purchase_brief_id": brief_id,
                "status": "ACCEPTED" if accept else "REJECTED",
                "resulting_purchase_brief_id": resulting_id,
                "resulting_version": resulting_version,
                "resulting_decision_id": resulting_decision_id,
                "resulting_decision_hash": resulting_decision_hash,
                "resulting_decision_version": resulting_decision_version,
                "ranking_effect": accept,
            }
            await repository.complete_idempotency(
                claim.record,
                response_status=200,
                response_payload=response,
                response_reference=resulting_id or proposal_id,
            )
            return 200, response

    async def _find_proposal(
        self,
        session: Any,
        organization_id: str,
        brief_id: str,
        proposal_id: str,
    ) -> tuple[CalibrationRun | CandidateFeedback, dict[str, Any]]:
        calibration_runs = (
            await session.execute(
                select(CalibrationRun).where(
                    CalibrationRun.organization_id == organization_id,
                    CalibrationRun.purchase_brief_id == brief_id,
                )
            )
        ).scalars()
        for run in calibration_runs:
            proposal = run.result.get("proposal")
            if isinstance(proposal, dict) and proposal.get("proposal_id") == proposal_id:
                return run, deepcopy(proposal)

        feedback_rows = (
            await session.execute(
                select(CandidateFeedback).where(
                    CandidateFeedback.organization_id == organization_id
                )
            )
        ).scalars()
        for feedback in feedback_rows:
            proposal = feedback.proposed_change
            if (
                isinstance(proposal, dict)
                and proposal.get("proposal_id") == proposal_id
                and proposal.get("base_purchase_brief_id") == brief_id
            ):
                return feedback, deepcopy(proposal)
        raise self._missing("PROPOSAL")

    @staticmethod
    def _apply_proposal_changes(
        payload: dict[str, Any], changes: list[dict[str, Any]]
    ) -> dict[str, Any]:
        preferences = payload.get("preferences")
        if not isinstance(preferences, list):
            raise ApiProblem(
                code="PROPOSAL_INVALID",
                message="The base Purchase Brief has no preference list.",
                status_code=409,
            )
        by_id = {item.get("criterion_id"): item for item in preferences if isinstance(item, dict)}
        for change in changes:
            if not isinstance(change, dict):
                raise ApiProblem(
                    code="PROPOSAL_CHANGE_UNSUPPORTED",
                    message="Only typed preference-weight proposals are supported.",
                    status_code=422,
                )
            criterion_id = change.get("criterion_id")
            proposed_weight = change.get("proposed_weight", change.get("weight"))
            if (
                not isinstance(criterion_id, str)
                or criterion_id not in by_id
                or isinstance(proposed_weight, bool)
                or not isinstance(proposed_weight, int)
                or not 1 <= proposed_weight <= 5
            ):
                raise ApiProblem(
                    code="PROPOSAL_CHANGE_UNSUPPORTED",
                    message=(
                        "A proposal must set a known preference criterion to weight 1 through 5."
                    ),
                    status_code=422,
                )
            by_id[criterion_id]["weight"] = proposed_weight
        return payload

    async def lock_purchase_intent(
        self,
        *,
        organization_id: str,
        actor_id: str,
        decision_id: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        request_hash = content_hash({"decision_id": decision_id, **body})
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation="purchase_intents.create",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if claim.replay:
                return int(claim.record.response_status or 201), dict(
                    claim.record.response_payload or {}
                )
            decision = await self._not_found(repository.get_decision(decision_id), "DECISION")
            await self._require_current_decision(session, organization_id, decision)
            selected_plan_id = decision.selected_solution_plan_id
            if not isinstance(selected_plan_id, str) or not selected_plan_id:
                raise ApiProblem(
                    code="NO_EXECUTABLE_SOLUTION_PLAN",
                    message="The Decision has no executable Solution Plan to lock.",
                    status_code=409,
                    next_action="refresh_decision",
                )
            if body.get("solution_plan_id") not in {None, selected_plan_id}:
                raise ApiProblem(
                    code="SOLUTION_PLAN_MISMATCH",
                    message=(
                        "The requested Solution Plan is not the selected exact decision output."
                    ),
                    status_code=409,
                    next_action="refresh_decision",
                )
            try:
                selected_plan = await repository.get_selected_solution_plan(
                    decision.supersedes_id or decision.id, selected_plan_id
                )
            except RecordNotFound:
                raise ApiProblem(
                    code="SOLUTION_PLAN_NOT_PERSISTED",
                    message="The selected Solution Plan is not bound to the canonical evaluation.",
                    status_code=409,
                    next_action="refresh_decision",
                ) from None
            if selected_plan.lifecycle != "EXECUTABLE" or selected_plan.candidate_status not in {
                "ELIGIBLE",
                "ELIGIBLE_WITH_EXCEPTION",
            }:
                raise ApiProblem(
                    code="SOLUTION_PLAN_NOT_EXECUTABLE",
                    message="The selected Solution Plan is not executable.",
                    status_code=409,
                    next_action="refresh_decision",
                )
            stack_patch_id = selected_plan.payload.get("stack_patch_id")
            if not isinstance(stack_patch_id, str) or not stack_patch_id:
                raise ApiProblem(
                    code="DECISION_STACK_PATCH_MISSING",
                    message="The selected Solution Plan has no immutable Stackfile patch.",
                    status_code=409,
                    next_action="refresh_decision",
                )
            linked_patch_id = await session.scalar(
                select(StackPatch.id).where(
                    StackPatch.id == stack_patch_id,
                    StackPatch.organization_id == organization_id,
                )
            )
            if linked_patch_id is None:
                raise ApiProblem(
                    code="DECISION_STACK_PATCH_UNAVAILABLE",
                    message="The selected Solution Plan's Stackfile patch is unavailable.",
                    status_code=409,
                    next_action="refresh_decision",
                )
            selection = decision.payload.get("selection")
            selection_id = (
                str(selection["selection_id"])
                if isinstance(selection, dict) and isinstance(selection.get("selection_id"), str)
                else f"selection_{decision.id}"
            )
            try:
                payload = build_purchase_intent_payload(
                    organization_id=organization_id,
                    decision_id=decision.id,
                    decision_version=decision.version,
                    decision_hash=decision.decision_hash,
                    selection_id=selection_id,
                    solution_plan_id=selected_plan_id,
                    stack_patch_id=stack_patch_id,
                    purchase_intent_id=new_id("pi"),
                    commercial_terms=selected_plan.payload.get("commercial_terms", {}),
                    locked_at=self._quote_now(),
                )
            except CommercialTermsConflict as error:
                raise ApiProblem(
                    code="PLAN_COMMERCIAL_TERMS_INVALID",
                    message="The selected Solution Plan has no valid immutable commercial terms.",
                    status_code=409,
                    next_action="refresh_quote",
                    details={"reason": str(error)},
                ) from None
            merchant = payload["merchant"]
            record = PurchaseIntent(
                id=payload["purchase_intent_id"],
                organization_id=organization_id,
                decision_id=decision.id,
                decision_hash=decision.decision_hash,
                solution_plan_id=selected_plan_id,
                stack_patch_id=stack_patch_id,
                intent_hash=payload["intent_hash"],
                merchant_id=merchant["merchant_id"],
                merchant_name=merchant["name"],
                merchant_url=merchant["url"],
                approved_merchant_chain_id=payload["approved_merchant_chain_id"],
                pack_id=payload["pack_id"],
                pack_version=payload["pack_version"],
                offer_id=payload["offer_id"],
                offer_version=payload["offer_version"],
                quote_id=payload["quote_id"],
                quote_version=payload["quote_version"],
                quote_expires_at=datetime.fromisoformat(
                    payload["quote_expires_at"].replace("Z", "+00:00")
                ),
                amount=Decimal(payload["amount"]),
                currency=payload["currency"],
                expected_fulfillments=payload["expected_fulfillments"],
                payload=payload,
                approval_status="NOT_REQUESTED",
                version=1,
            )
            await repository.add_purchase_intent(record)
            response = self._purchase_intent_view(record)
            await repository.complete_idempotency(
                claim.record,
                response_status=201,
                response_payload=response,
                response_reference=record.id,
            )
            return 201, response

    async def create_approval_request(
        self,
        *,
        organization_id: str,
        actor_id: str,
        intent_id: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        request_hash = content_hash({"intent_id": intent_id, **body})
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation="approval_requests.create",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if claim.replay:
                return int(claim.record.response_status or 201), dict(
                    claim.record.response_payload or {}
                )
            intent = await self._not_found(
                repository.get_purchase_intent(intent_id, lock=True), "PURCHASE_INTENT"
            )
            decision = await self._not_found(
                repository.get_decision(intent.decision_id), "DECISION"
            )
            await self._require_current_decision(session, organization_id, decision)
            if self._as_utc(intent.quote_expires_at) <= self._quote_now():
                raise ApiProblem(
                    code="QUOTE_EXPIRED",
                    message="The locked quote expired; create a new Purchase Intent and approval.",
                    status_code=409,
                    next_action="refresh_quote",
                )
            if intent.approval_status != "NOT_REQUESTED":
                raise ApiProblem(
                    code="APPROVAL_ALREADY_STARTED",
                    message="Approval already exists for this exact Purchase Intent.",
                    status_code=409,
                )
            brief = (
                await session.execute(
                    select(PurchaseBriefVersion).where(
                        PurchaseBriefVersion.id == decision.purchase_brief_id,
                        PurchaseBriefVersion.organization_id == organization_id,
                    )
                )
            ).scalar_one_or_none()
            if brief is None:
                raise self._missing("PURCHASE_BRIEF")
            requirements = brief.payload.get("approval_requirements")
            if not isinstance(requirements, list):
                raise ApiProblem(
                    code="APPROVAL_POLICY_INVALID",
                    message="The canonical Purchase Brief has no valid approval requirements.",
                    status_code=409,
                )
            roles = [
                str(requirement["role"])
                for requirement in requirements
                if isinstance(requirement, dict)
                and requirement.get("required") is True
                and isinstance(requirement.get("role"), str)
            ]
            if not roles or len(roles) != len(set(roles)):
                raise ApiProblem(
                    code="APPROVAL_POLICY_INVALID",
                    message="The canonical approval roles are empty or duplicated.",
                    status_code=409,
                )
            approval = ApprovalRequest(
                id=new_id("apr"),
                organization_id=organization_id,
                purchase_intent_id=intent.id,
                intent_hash=intent.intent_hash,
                policy_version=int(intent.payload["approval_policy_version"]),
                status="PENDING",
                required_roles=roles,
                approved_roles=[],
                expires_at=self._now() + timedelta(minutes=60),
            )
            session.add(approval)
            intent.approval_status = "PENDING"
            response = self._approval_view(approval)
            await repository.complete_idempotency(
                claim.record,
                response_status=201,
                response_payload=response,
                response_reference=approval.id,
            )
            return 201, response

    async def approve(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_roles: frozenset[str],
        step_up_verified: bool,
        approval_id: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        if not step_up_verified:
            raise ApiProblem(
                code="STEP_UP_REQUIRED",
                message="Recent step-up authentication is required to approve a purchase.",
                status_code=403,
                next_action="authenticate",
            )
        request_hash = content_hash({"approval_id": approval_id, **body})
        expiry_problem: ApiProblem | None = None
        result: tuple[int, dict[str, Any]] | None = None
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            approval = (
                await session.execute(
                    select(ApprovalRequest)
                    .where(
                        ApprovalRequest.id == approval_id,
                        ApprovalRequest.organization_id == organization_id,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if approval is None:
                raise self._missing("APPROVAL_REQUEST")
            intent = await repository.get_purchase_intent(approval.purchase_intent_id, lock=True)
            decision = await repository.get_decision(intent.decision_id)
            await self._require_current_decision(session, organization_id, decision)
            now = self._now()
            expiry_problem = self._approval_expiry_problem(approval, intent, now)
            if expiry_problem is not None:
                approval.status = "EXPIRED"
                intent.approval_status = "EXPIRED"
            else:
                claim = await repository.claim_idempotency(
                    actor_id=actor_id,
                    operation="approval_requests.approve",
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                )
                if claim.replay:
                    return int(claim.record.response_status or 200), dict(
                        claim.record.response_payload or {}
                    )
                role = body["actor_role"]
                self._require_approval_role(approval, actor_roles, role)
                existing_actor = (
                    await session.execute(
                        select(ApprovalEvent.id).where(
                            ApprovalEvent.organization_id == organization_id,
                            ApprovalEvent.approval_request_id == approval_id,
                            ApprovalEvent.actor_id == actor_id,
                            ApprovalEvent.action == "APPROVE",
                        )
                    )
                ).scalar_one_or_none()
                if existing_actor is not None and role not in approval.approved_roles:
                    raise ApiProblem(
                        code="SEPARATION_OF_DUTIES",
                        message="One actor cannot satisfy multiple roles for this approval policy.",
                        status_code=403,
                    )
                await repository.record_approval_event(
                    approval_request_id=approval_id,
                    intent_hash=body["intent_hash"],
                    actor_id=actor_id,
                    actor_role=role,
                    action="APPROVE",
                    event_key=f"approve:{approval_id}:{role}:{actor_id}",
                )
                if role not in approval.approved_roles:
                    approval.approved_roles = [*approval.approved_roles, role]
                if approval.approved_roles == approval.required_roles:
                    approval.status = "APPROVED"
                    intent.approval_status = "APPROVED"
                response = self._approval_view(approval)
                await repository.complete_idempotency(
                    claim.record,
                    response_status=200,
                    response_payload=response,
                    response_reference=approval.id,
                )
                result = (200, response)
        if expiry_problem is not None:
            raise expiry_problem
        if result is None:
            raise RuntimeError("approval transaction produced no result")
        return result

    async def reject_approval(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_roles: frozenset[str],
        step_up_verified: bool,
        approval_id: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        if not step_up_verified:
            raise ApiProblem(
                code="STEP_UP_REQUIRED",
                message="Recent step-up authentication is required to reject a purchase.",
                status_code=403,
                next_action="authenticate",
            )
        request_hash = content_hash({"approval_id": approval_id, **body})
        expiry_problem: ApiProblem | None = None
        result: tuple[int, dict[str, Any]] | None = None
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            approval = (
                await session.execute(
                    select(ApprovalRequest)
                    .where(
                        ApprovalRequest.id == approval_id,
                        ApprovalRequest.organization_id == organization_id,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if approval is None:
                raise self._missing("APPROVAL_REQUEST")
            intent = await repository.get_purchase_intent(approval.purchase_intent_id, lock=True)
            decision = await repository.get_decision(intent.decision_id)
            await self._require_current_decision(session, organization_id, decision)
            expiry_problem = self._approval_expiry_problem(approval, intent, self._now())
            if expiry_problem is not None:
                approval.status = "EXPIRED"
                intent.approval_status = "EXPIRED"
            else:
                claim = await repository.claim_idempotency(
                    actor_id=actor_id,
                    operation="approval_requests.reject",
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                )
                if claim.replay:
                    return int(claim.record.response_status or 200), dict(
                        claim.record.response_payload or {}
                    )
                role = body["actor_role"]
                self._require_approval_role(approval, actor_roles, role)
                await repository.record_approval_event(
                    approval_request_id=approval_id,
                    intent_hash=body["intent_hash"],
                    actor_id=actor_id,
                    actor_role=role,
                    action="REJECT",
                    event_key=f"reject:{approval_id}:{role}:{actor_id}",
                    reason=body["reason"],
                )
                approval.status = "REJECTED"
                intent.approval_status = "REJECTED"
                await repository.add_outbox(
                    aggregate_type="purchase_intent",
                    aggregate_id=intent.id,
                    event_type="approval.rejected",
                    event_key=f"approval-rejected:{approval.id}",
                    payload={
                        "purchase_intent_id": intent.id,
                        "approval_request_id": approval.id,
                        "actor_role": role,
                    },
                )
                response = self._approval_view(approval)
                await repository.complete_idempotency(
                    claim.record,
                    response_status=200,
                    response_payload=response,
                    response_reference=approval.id,
                )
                result = (200, response)
        if expiry_problem is not None:
            raise expiry_problem
        if result is None:
            raise RuntimeError("approval rejection transaction produced no result")
        return result

    async def revoke_approval(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_roles: frozenset[str],
        step_up_verified: bool,
        approval_id: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        if not step_up_verified:
            raise ApiProblem(
                code="STEP_UP_REQUIRED",
                message="Recent step-up authentication is required to revoke approval.",
                status_code=403,
                next_action="authenticate",
            )
        request_hash = content_hash({"approval_id": approval_id, **body})
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            approval = (
                await session.execute(
                    select(ApprovalRequest)
                    .where(
                        ApprovalRequest.id == approval_id,
                        ApprovalRequest.organization_id == organization_id,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if approval is None:
                raise self._missing("APPROVAL_REQUEST")
            intent = await repository.get_purchase_intent(approval.purchase_intent_id, lock=True)
            decision = await repository.get_decision(intent.decision_id)
            await self._require_current_decision(session, organization_id, decision)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation="approval_requests.revoke",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if claim.replay:
                return int(claim.record.response_status or 200), dict(
                    claim.record.response_payload or {}
                )
            if approval.status not in {"PENDING", "APPROVED"}:
                raise ApiProblem(
                    code="APPROVAL_NOT_REVOCABLE",
                    message=f"Approval request is already {approval.status}.",
                    status_code=409,
                    next_action="poll_purchase_status",
                )
            role = body["actor_role"]
            self._require_verified_approval_role(approval, actor_roles, role)
            await repository.record_approval_event(
                approval_request_id=approval_id,
                intent_hash=body["intent_hash"],
                actor_id=actor_id,
                actor_role=role,
                action="REVOKE",
                event_key=f"revoke:{approval_id}:{actor_id}",
                reason=body["reason"],
            )
            approval.status = "REVOKED"
            intent.approval_status = "REVOKED"
            handoff = (
                await session.execute(
                    select(PaymentHandoff)
                    .where(
                        PaymentHandoff.organization_id == organization_id,
                        PaymentHandoff.approval_request_id == approval.id,
                        PaymentHandoff.status == "READY",
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if handoff is not None:
                handoff.status = "CANCELLED"

            await repository.add_outbox(
                aggregate_type="purchase_intent",
                aggregate_id=intent.id,
                event_type="approval.revoked",
                event_key=f"approval-revoked:{approval.id}",
                payload={
                    "purchase_intent_id": intent.id,
                    "approval_request_id": approval.id,
                    "actor_role": role,
                },
            )
            response = self._approval_view(approval)
            await repository.complete_idempotency(
                claim.record,
                response_status=200,
                response_payload=response,
                response_reference=approval.id,
            )
            return 200, response

    def _approval_expiry_problem(
        self, approval: ApprovalRequest, intent: PurchaseIntent, now: datetime
    ) -> ApiProblem | None:
        if self._as_utc(approval.expires_at) <= now:
            return ApiProblem(
                code="APPROVAL_EXPIRED",
                message="This exact-hash approval request has expired.",
                status_code=409,
                next_action="create_approval_request",
            )
        if self._as_utc(intent.quote_expires_at) <= self._quote_now():
            return ApiProblem(
                code="QUOTE_EXPIRED",
                message="The quote expired before approval completed.",
                status_code=409,
                next_action="refresh_quote",
            )
        return None

    async def _expire_purchase_approval_if_needed(
        self, organization_id: str, intent_id: str
    ) -> ApiProblem | None:
        problem: ApiProblem | None = None
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            intent = await repository.get_purchase_intent(intent_id, lock=True)
            approval = (
                await session.execute(
                    select(ApprovalRequest)
                    .where(
                        ApprovalRequest.organization_id == organization_id,
                        ApprovalRequest.purchase_intent_id == intent.id,
                        ApprovalRequest.intent_hash == intent.intent_hash,
                    )
                    .order_by(ApprovalRequest.created_at.desc())
                    .limit(1)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if (
                approval is None
                or approval.status != "APPROVED"
                or intent.approval_status != "APPROVED"
            ):
                return None
            problem = self._approval_expiry_problem(approval, intent, self._now())
            if problem is not None:
                approval.status = "EXPIRED"
                intent.approval_status = "EXPIRED"
        return problem

    @staticmethod
    def _require_verified_approval_role(
        approval: ApprovalRequest, actor_roles: frozenset[str], role: str
    ) -> None:
        if role not in actor_roles:
            raise ApiProblem(
                code="APPROVER_ROLE_NOT_VERIFIED",
                message="The verified actor does not hold the requested approval role.",
                status_code=403,
            )
        if role not in approval.required_roles:
            raise ApiProblem(
                code="APPROVER_ROLE_NOT_REQUIRED",
                message="The authenticated actor does not satisfy a required approval role.",
                status_code=403,
            )

    @classmethod
    def _require_approval_role(
        cls, approval: ApprovalRequest, actor_roles: frozenset[str], role: str
    ) -> None:
        cls._require_verified_approval_role(approval, actor_roles, role)
        next_stage = len(approval.approved_roles)
        if next_stage >= len(approval.required_roles):
            raise ApiProblem(
                code="APPROVAL_ALREADY_FINAL",
                message="Every frozen approval stage is already complete.",
                status_code=409,
            )
        if approval.required_roles[next_stage] != role:
            raise ApiProblem(
                code="APPROVAL_STAGE_OUT_OF_ORDER",
                message="Approval stages must be completed in the frozen policy order.",
                status_code=409,
                next_action="complete_current_approval_stage",
                details={"required_role": approval.required_roles[next_stage]},
            )

    async def create_payment_handoff(
        self,
        *,
        organization_id: str,
        actor_id: str,
        intent_id: str,
        idempotency_key: str,
    ) -> tuple[int, dict[str, Any]]:
        """Prepare exact context for a human payment step without executing it."""

        approval_expiry = await self._expire_purchase_approval_if_needed(organization_id, intent_id)
        if approval_expiry is not None:
            raise approval_expiry
        request_hash = content_hash({"intent_id": intent_id, "operation": "payment_handoff"})
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation="payment_handoffs.create",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if claim.replay:
                return int(claim.record.response_status or 201), dict(
                    claim.record.response_payload or {}
                )
            intent = await self._not_found(
                repository.get_purchase_intent(intent_id, lock=True), "PURCHASE_INTENT"
            )
            decision = await repository.get_decision(intent.decision_id)
            await self._require_current_decision(session, organization_id, decision)
            approval = (
                await session.execute(
                    select(ApprovalRequest)
                    .where(
                        ApprovalRequest.organization_id == organization_id,
                        ApprovalRequest.purchase_intent_id == intent.id,
                        ApprovalRequest.intent_hash == intent.intent_hash,
                        ApprovalRequest.status == "APPROVED",
                    )
                    .order_by(ApprovalRequest.created_at.desc())
                    .limit(1)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if intent.approval_status != "APPROVED" or approval is None:
                raise ApiProblem(
                    code="APPROVAL_REQUIRED",
                    message="Approve the exact current purchase intent before continuing.",
                    status_code=409,
                    next_action="complete_approval",
                )
            now = self._now()
            expiry_problem = self._approval_expiry_problem(approval, intent, now)
            if expiry_problem is not None:
                raise expiry_problem
            existing = (
                await session.execute(
                    select(PaymentHandoff).where(
                        PaymentHandoff.organization_id == organization_id,
                        PaymentHandoff.purchase_intent_id == intent.id,
                        PaymentHandoff.approval_request_id == approval.id,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                response = self._payment_handoff_view(existing)
                await repository.complete_idempotency(
                    claim.record,
                    response_status=201,
                    response_payload=response,
                    response_reference=existing.id,
                )
                return 201, response

            expires_at = min(
                self._as_utc(approval.expires_at),
                now + (self._as_utc(intent.quote_expires_at) - self._quote_now()),
                now + timedelta(minutes=15),
            )
            domain_handoff = DomainPaymentHandoff(
                schema_version="1.0",
                handoff_id=new_id("phd"),
                organization_id=organization_id,
                purchase_intent_id=intent.id,
                approval_request_id=approval.id,
                intent_hash=intent.intent_hash,
                destination_url=intent.merchant_url,
                recipient=intent.merchant_name,
                amount=Money(intent.amount, intent.currency),
                reference=f"SIRA-{intent.id}",
                created_at=now,
                expires_at=expires_at,
            )
            record = PaymentHandoff(
                id=domain_handoff.handoff_id,
                organization_id=domain_handoff.organization_id,
                purchase_intent_id=domain_handoff.purchase_intent_id,
                approval_request_id=domain_handoff.approval_request_id,
                intent_hash=domain_handoff.intent_hash,
                handoff_hash=domain_handoff.handoff_hash,
                destination_url=domain_handoff.destination_url,
                recipient=domain_handoff.recipient,
                amount=domain_handoff.amount.amount,
                currency=domain_handoff.amount.currency,
                reference=domain_handoff.reference,
                status=domain_handoff.status.value,
                expires_at=domain_handoff.expires_at,
                opened_at=None,
                created_at=domain_handoff.created_at,
                updated_at=domain_handoff.created_at,
            )
            session.add(record)
            await session.flush()
            await repository.add_outbox(
                aggregate_type="payment_handoff",
                aggregate_id=record.id,
                event_type="payment_handoff.ready",
                event_key=f"payment-handoff-ready:{record.id}",
                payload={
                    "payment_handoff_id": record.id,
                    "purchase_intent_id": intent.id,
                    "handoff_hash": record.handoff_hash,
                },
            )
            response = self._payment_handoff_view(record)
            await repository.complete_idempotency(
                claim.record,
                response_status=201,
                response_payload=response,
                response_reference=record.id,
            )
            return 201, response

    async def open_payment_handoff(
        self,
        *,
        organization_id: str,
        actor_id: str,
        handoff_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Record the handoff; the authenticated browser performs navigation."""

        request_hash = content_hash({"handoff_id": handoff_id, "operation": "open"})
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation="payment_handoffs.open",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if claim.replay:
                return dict(claim.record.response_payload or {})
            record = (
                await session.execute(
                    select(PaymentHandoff)
                    .where(
                        PaymentHandoff.id == handoff_id,
                        PaymentHandoff.organization_id == organization_id,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if record is None:
                raise self._missing("PAYMENT_HANDOFF")
            intent = await repository.get_purchase_intent(record.purchase_intent_id, lock=True)
            approval = (
                await session.execute(
                    select(ApprovalRequest).where(
                        ApprovalRequest.id == record.approval_request_id,
                        ApprovalRequest.organization_id == organization_id,
                    )
                )
            ).scalar_one_or_none()
            if (
                approval is None
                or approval.status != "APPROVED"
                or intent.approval_status != "APPROVED"
                or approval.intent_hash != record.intent_hash
                or intent.intent_hash != record.intent_hash
            ):
                raise ApiProblem(
                    code="HANDOFF_AUTHORITY_INVALID",
                    message="This payment handoff is no longer authorized.",
                    status_code=409,
                    next_action="review_purchase_intent",
                )
            domain_handoff = DomainPaymentHandoff(
                schema_version="1.0",
                handoff_id=record.id,
                organization_id=record.organization_id,
                purchase_intent_id=record.purchase_intent_id,
                approval_request_id=record.approval_request_id,
                intent_hash=record.intent_hash,
                destination_url=record.destination_url,
                recipient=record.recipient,
                amount=Money(record.amount, record.currency),
                reference=record.reference,
                created_at=self._as_utc(record.created_at),
                expires_at=self._as_utc(record.expires_at),
                status=PaymentHandoffStatus(record.status),
                opened_at=(self._as_utc(record.opened_at) if record.opened_at else None),
                handoff_hash=record.handoff_hash,
            )
            try:
                opened = PaymentHandoffTransitionService.transition(
                    domain_handoff, PaymentHandoffStatus.OPENED, at=self._now()
                )
            except (ValueError, DomainValidationError, InvalidTransitionError) as exc:
                raise ApiProblem(
                    code="HANDOFF_NOT_OPENABLE",
                    message="This payment handoff cannot be opened.",
                    status_code=409,
                    next_action="create_payment_handoff",
                ) from exc
            record.status = opened.status.value
            record.opened_at = opened.opened_at
            await repository.add_outbox(
                aggregate_type="payment_handoff",
                aggregate_id=record.id,
                event_type="payment_handoff.opened",
                event_key=f"payment-handoff-opened:{record.id}",
                payload={
                    "payment_handoff_id": record.id,
                    "purchase_intent_id": record.purchase_intent_id,
                    "handoff_hash": record.handoff_hash,
                },
            )
            response = self._payment_handoff_view(record)
            await repository.complete_idempotency(
                claim.record,
                response_status=200,
                response_payload=response,
                response_reference=record.id,
            )
            return response

    async def purchase_status(self, organization_id: str, intent_id: str) -> dict[str, Any]:
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            intent = await self._not_found(
                repository.get_purchase_intent(intent_id), "PURCHASE_INTENT"
            )
            handoff = (
                await session.execute(
                    select(PaymentHandoff)
                    .where(
                        PaymentHandoff.organization_id == organization_id,
                        PaymentHandoff.purchase_intent_id == intent.id,
                    )
                    .order_by(PaymentHandoff.created_at.desc(), PaymentHandoff.id.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            outcome = (
                await session.execute(
                    select(OutcomeCheckpoint)
                    .where(
                        OutcomeCheckpoint.organization_id == organization_id,
                        OutcomeCheckpoint.purchase_intent_id == intent.id,
                    )
                    .order_by(OutcomeCheckpoint.observed_at.desc(), OutcomeCheckpoint.id.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            handoff_status = handoff.status if handoff is not None else None
            if intent.approval_status != "APPROVED":
                purchase_state = "AWAITING_APPROVAL"
            elif handoff_status == "OPENED":
                purchase_state = "HANDOFF_OPENED"
            elif handoff_status == "EXPIRED":
                purchase_state = "HANDOFF_EXPIRED"
            elif handoff_status == "CANCELLED":
                purchase_state = "HANDOFF_CANCELLED"
            else:
                purchase_state = "READY_FOR_HANDOFF"
            return {
                "purchase_intent_id": intent.id,
                "approval_status": intent.approval_status,
                "handoff_status": handoff_status,
                "purchase_state": purchase_state,
                "outcome_state": outcome.state if outcome is not None else "NOT_MEASURED",
            }

    async def record_outcome_checkpoint(
        self,
        *,
        organization_id: str,
        actor_id: str,
        intent_id: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        request_hash = content_hash({"intent_id": intent_id, **body})
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation="outcome_checkpoint.create",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if claim.replay:
                return int(claim.record.response_status or 201), dict(
                    claim.record.response_payload or {}
                )
            intent = await self._not_found(
                repository.get_purchase_intent(intent_id), "PURCHASE_INTENT"
            )
            handoff = (
                await session.execute(
                    select(PaymentHandoff).where(
                        PaymentHandoff.organization_id == organization_id,
                        PaymentHandoff.purchase_intent_id == intent.id,
                        PaymentHandoff.status == "OPENED",
                    )
                )
            ).scalar_one_or_none()
            if handoff is None or handoff.opened_at is None:
                raise ApiProblem(
                    code="OUTCOME_REQUIRES_OPENED_HANDOFF",
                    message="Outcome measurement starts after the approved handoff is opened.",
                    status_code=409,
                    next_action="open_payment_handoff",
                )
            decision = await self._not_found(
                repository.get_decision(intent.decision_id), "DECISION"
            )
            purchase_brief = (
                await session.execute(
                    select(PurchaseBriefVersion).where(
                        PurchaseBriefVersion.id == decision.purchase_brief_id,
                        PurchaseBriefVersion.organization_id == organization_id,
                    )
                )
            ).scalar_one_or_none()
            if purchase_brief is None:
                raise self._missing("PURCHASE_BRIEF")
            desired = purchase_brief.payload.get("desired_outcome")
            if not isinstance(desired, dict):
                raise ApiProblem(
                    code="OUTCOME_TARGET_NOT_DECLARED",
                    message="The frozen Purchase Brief has no measurable outcome target.",
                    status_code=409,
                )
            metric = desired.get("metric")
            target_raw = desired.get("target")
            target_operator = desired.get("operator", "gte")
            checkpoint_days = desired.get("checkpoint_days")
            if (
                body["metric"] != metric
                or isinstance(target_raw, bool)
                or not isinstance(target_raw, (int, float))
                or isinstance(checkpoint_days, bool)
                or not isinstance(checkpoint_days, int)
                or not 1 <= checkpoint_days <= 365
                or target_operator not in {"gte", "lte"}
            ):
                raise ApiProblem(
                    code="OUTCOME_TARGET_MISMATCH",
                    message="The checkpoint must match the frozen metric and measurement window.",
                    status_code=409,
                )
            observed_at = self._as_utc(cast(datetime, body["observed_at"]))
            now = self._now()
            if observed_at > now + timedelta(minutes=5):
                raise ApiProblem(
                    code="OUTCOME_OBSERVATION_IN_FUTURE",
                    message="Outcome observations cannot be recorded in the future.",
                    status_code=422,
                )
            measurement_started_at = self._as_utc(handoff.opened_at)
            if observed_at < measurement_started_at:
                raise ApiProblem(
                    code="OUTCOME_OBSERVATION_BEFORE_HANDOFF",
                    message="Outcome observations cannot predate the approved handoff.",
                    status_code=422,
                )
            checkpoint_due_at = measurement_started_at + timedelta(days=checkpoint_days)
            target = Decimal(str(target_raw))
            observed = Decimal(str(body["observed_value"]))
            state = (
                "MEASURING"
                if observed_at < checkpoint_due_at
                else "ACHIEVED"
                if (observed >= target if target_operator == "gte" else observed <= target)
                else "NOT_ACHIEVED"
            )
            source_reference_hash = content_hash(
                {
                    "source_class": body["source_class"],
                    "source_reference": body["source_reference"],
                }
            )
            checkpoint_payload = {
                "purchase_intent_id": intent.id,
                "decision_id": intent.decision_id,
                "decision_hash": intent.decision_hash,
                "solution_plan_id": intent.solution_plan_id,
                "metric": metric,
                "target_value": self._metric_value(target),
                "target_operator": target_operator,
                "observed_value": self._metric_value(observed),
                "checkpoint_days": checkpoint_days,
                "measurement_started_at": measurement_started_at.isoformat(),
                "checkpoint_due_at": checkpoint_due_at.isoformat(),
                "observed_at": observed_at.isoformat(),
                "state": state,
                "source_class": body["source_class"],
                "source_reference_hash": source_reference_hash,
            }
            checkpoint_hash = content_hash(checkpoint_payload)
            proposal = (
                {
                    "status": "PROPOSED",
                    "action": "REVIEW_OUTCOME_PREFERENCE",
                    "metric": metric,
                    "ranking_effect": False,
                    "silent_policy_update": False,
                }
                if state == "NOT_ACHIEVED"
                else None
            )
            checkpoint = OutcomeCheckpoint(
                id=new_id("out"),
                organization_id=organization_id,
                purchase_intent_id=intent.id,
                decision_id=intent.decision_id,
                decision_hash=intent.decision_hash,
                solution_plan_id=intent.solution_plan_id,
                metric_id=str(metric),
                target_value=target,
                target_operator=target_operator,
                observed_value=observed,
                checkpoint_days=checkpoint_days,
                measurement_started_at=measurement_started_at,
                checkpoint_due_at=checkpoint_due_at,
                observed_at=observed_at,
                state=state,
                source_class=body["source_class"],
                source_reference_hash=source_reference_hash,
                recorded_by_actor_id=actor_id,
                checkpoint_hash=checkpoint_hash,
                preference_proposal=proposal,
                created_at=now,
                updated_at=now,
            )
            session.add(checkpoint)
            await repository.add_outbox(
                aggregate_type="outcome_checkpoint",
                aggregate_id=checkpoint.id,
                event_type="outcome_checkpoint.recorded",
                event_key=f"outcome-checkpoint-recorded:{checkpoint_hash}",
                payload={
                    "outcome_checkpoint_id": checkpoint.id,
                    "purchase_intent_id": intent.id,
                    "decision_hash": intent.decision_hash,
                    "state": state,
                    "checkpoint_hash": checkpoint_hash,
                },
            )
            response = self._outcome_checkpoint_view(checkpoint)
            await repository.complete_idempotency(
                claim.record,
                response_status=201,
                response_payload=response,
                response_reference=checkpoint.id,
            )
            return 201, response

    async def stackfile(self, organization_id: str) -> dict[str, Any]:
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            snapshot = await self._not_found(repository.get_stack_snapshot(), "STACK_SNAPSHOT")
            patch = (
                await session.execute(
                    select(StackPatch)
                    .where(StackPatch.organization_id == organization_id)
                    .order_by(StackPatch.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            return {
                "organization_id": organization_id,
                "current": {"manifest": snapshot.manifest, "lock": snapshot.lock},
                "proposed_patch": deepcopy(patch.payload) if patch is not None else None,
            }

    async def workflow(self, organization_id: str, workflow_id: str) -> dict[str, Any]:
        async with self.database.transaction(organization_id) as session:
            workflow = (
                await session.execute(
                    select(WorkflowRun).where(
                        WorkflowRun.id == workflow_id,
                        WorkflowRun.organization_id == organization_id,
                    )
                )
            ).scalar_one_or_none()
            if workflow is None:
                raise self._missing("WORKFLOW")
            return {
                "workflow_id": workflow.id,
                "aggregate_id": workflow.aggregate_id,
                "operation": workflow.operation,
                "status": workflow.status,
                "result_reference": workflow.result_reference,
                "safe_error_code": workflow.safe_error_code,
            }

    async def workflow_events(self, organization_id: str, workflow_id: str) -> list[dict[str, Any]]:
        async with self.database.transaction(organization_id) as session:
            workflow = (
                await session.execute(
                    select(WorkflowRun).where(
                        WorkflowRun.id == workflow_id,
                        WorkflowRun.organization_id == organization_id,
                    )
                )
            ).scalar_one_or_none()
            if workflow is None:
                raise self._missing("WORKFLOW")
            return list(workflow.event_log)

    async def _ensure_organization(self, session: Any, organization_id: str) -> None:
        organization = await session.get(Organization, organization_id)
        if organization is None:
            if not self.allow_development_tenant_bootstrap:
                raise ApiProblem(
                    code="ORGANIZATION_NOT_PROVISIONED",
                    message="The verified organization is not provisioned in canonical state.",
                    status_code=403,
                )
            session.add(
                Organization(id=organization_id, name="Development organization", version=1)
            )
            await session.flush()

    async def _add_request_briefs(
        self, session: Any, organization_id: str, request: PurchaseRequest
    ) -> tuple[PurchaseBriefVersion, RequirementBriefVersion]:
        fixtures = self._fixture_bundle()
        brief = deepcopy(fixtures.purchase_brief)
        brief_id = f"pb_{request.id}"
        brief["purchase_brief_id"] = brief_id
        brief["request_id"] = request.id
        brief["organization_id"] = organization_id
        brief["intent"] = request.intent
        request_outcome = request.payload.get("desired_outcome")
        if isinstance(request_outcome, dict):
            if request_outcome.get("metric") != brief["desired_outcome"]["metric"]:
                raise ApiProblem(
                    code="DEMO_OUTCOME_METRIC_UNSUPPORTED",
                    message="The selected demo scenario has a fixed measurable outcome metric.",
                    status_code=422,
                    details={"supported_metric": brief["desired_outcome"]["metric"]},
                )
            brief["desired_outcome"] = {
                **brief["desired_outcome"],
                **request_outcome,
            }
            outcome = brief["desired_outcome"]
            outcome["statement"] = (
                f"{outcome['metric']} {outcome['operator']} {outcome['target']} "
                f"{outcome['unit']} at {outcome['checkpoint_days']} days after verified "
                "fulfillment"
            )
        brief["content_hash"] = content_hash(
            {key: value for key, value in brief.items() if key != "content_hash"}
        )
        requirement = deepcopy(fixtures.requirement_brief)
        requirement_id = f"rb_{request.id}"
        requirement["requirement_brief_id"] = requirement_id
        requirement["purchase_brief_id"] = brief_id
        requirement["intent"] = request.intent
        requirement["desired_outcome"] = brief["desired_outcome"]["statement"]
        requirement["content_hash"] = content_hash(
            {key: value for key, value in requirement.items() if key != "content_hash"}
        )
        brief_record = PurchaseBriefVersion(
            id=brief_id,
            organization_id=organization_id,
            purchase_request_id=request.id,
            version=1,
            status="APPROVED",
            payload=brief,
            content_hash=brief["content_hash"],
            supersedes_id=None,
        )
        requirement_record = RequirementBriefVersion(
            id=requirement_id,
            organization_id=organization_id,
            purchase_request_id=request.id,
            purchase_brief_id=brief_id,
            version=1,
            payload=requirement,
            content_hash=requirement["content_hash"],
        )
        session.add_all((brief_record, requirement_record))
        return brief_record, requirement_record

    async def _ensure_demo_stack_snapshot(
        self, session: Any, organization_id: str
    ) -> StackSnapshot:
        fixtures = self._fixture_bundle()
        snapshot = (
            await session.execute(
                select(StackSnapshot)
                .where(StackSnapshot.organization_id == organization_id)
                .order_by(StackSnapshot.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if snapshot is None:
            snapshot = StackSnapshot(
                id=f"stack_{organization_id}_v1",
                organization_id=organization_id,
                version=1,
                manifest=fixtures.stack_manifest,
                lock=fixtures.stack_lock,
                lock_hash=fixtures.stack_lock["content_hash"],
            )
            session.add(snapshot)
            await session.flush()
        return cast(StackSnapshot, snapshot)

    async def _add_demo_decision_source(
        self,
        *,
        repository: WorkflowRepository,
        organization_id: str,
        actor_id: str,
        request: PurchaseRequest,
        brief: PurchaseBriefVersion,
        requirement: RequirementBriefVersion,
        stack_snapshot: StackSnapshot,
    ) -> DecisionSourceSnapshot:
        source = load_demo_decision_source(DEMO)
        payload = source.to_payload()
        buyer_passport = payload["buyer_passport"]
        buyer_passport["organization_id"] = organization_id
        for fact in buyer_passport["facts"]:
            fact["organization_id"] = organization_id
        payload["purchase_brief"] = deepcopy(brief.payload)
        payload["requirement_brief"] = deepcopy(requirement.payload)
        payload["stack_lock"] = deepcopy(stack_snapshot.lock)
        source_hash = content_hash(payload)
        accepted_at = datetime.fromisoformat(
            str(payload["category_taxonomy"]["evaluated_at"]).replace("Z", "+00:00")
        )
        return await repository.add_decision_source_snapshot(
            DecisionSourceSnapshot(
                id=f"dss_{request.id}_v{brief.version}",
                organization_id=organization_id,
                purchase_request_id=request.id,
                purchase_brief_id=brief.id,
                stack_snapshot_id=stack_snapshot.id,
                version=brief.version,
                source_kind="DEVELOPMENT_FIXTURE",
                payload=payload,
                content_hash=source_hash,
                accepted_by_actor_id=actor_id,
                accepted_at=accepted_at,
            )
        )

    def _request_view(self, request: PurchaseRequest) -> dict[str, Any]:
        return {
            "id": request.id,
            "organization_id": request.organization_id,
            "intent": request.intent,
            "status": request.status,
            "visibility": request.visibility,
            "version": request.version,
            **self._request_evaluation_metadata(request),
            "workflow_id": None,
            "decision_id": None,
        }

    @staticmethod
    def _purchase_brief_view(payload: dict[str, Any]) -> dict[str, Any]:
        keys = {
            "schema_version",
            "purchase_brief_id",
            "request_id",
            "organization_id",
            "version",
            "supersedes_version",
            "status",
            "visibility",
            "intent",
            "category_id",
            "desired_outcome",
            "stakeholder_roles",
            "hard_gates",
            "preferences",
            "known_alternatives",
            "stackfile_impact_policy",
            "disclosure_choices",
            "approval_requirements",
            "calibration_examples",
            "created_at",
            "content_hash",
        }
        return {key: deepcopy(value) for key, value in payload.items() if key in keys}

    @staticmethod
    def _requirement_brief_view(payload: dict[str, Any]) -> dict[str, Any]:
        # Explicit allowlist: buyer identity, budget, contacts, private failures,
        # competing offers, and unrestricted Stackfile content cannot cross it.
        keys = {
            "schema_version",
            "requirement_brief_id",
            "purchase_brief_id",
            "purchase_brief_version",
            "version",
            "visibility",
            "category_id",
            "intent",
            "desired_outcome",
            "team",
            "data_profile",
            "hard_requirements",
            "preferences",
            "allowed_stack_context",
            "seller_questions",
            "expires_at",
            "content_hash",
        }
        return {key: deepcopy(value) for key, value in payload.items() if key in keys}

    @staticmethod
    def _engagement_view(engagement: Engagement) -> dict[str, Any]:
        return {
            "id": engagement.id,
            "status": engagement.status,
            "buyer_consented": engagement.buyer_consented,
            "seller_consented": engagement.seller_consented,
            "contact_details": (
                deepcopy(engagement.contact_exchange)
                if engagement.buyer_consented and engagement.seller_consented
                else None
            ),
        }

    @staticmethod
    def _purchase_intent_view(intent: PurchaseIntent) -> dict[str, Any]:
        payload = deepcopy(intent.payload)
        payload.update(
            {
                "purchase_intent_id": intent.id,
                "decision_id": intent.decision_id,
                "decision_hash": intent.decision_hash,
                "solution_plan_id": intent.solution_plan_id,
                "quote_version": intent.quote_version,
                "quote_expires_at": intent.quote_expires_at.isoformat(),
                "amount": f"{intent.amount:.2f}",
                "currency": intent.currency,
                "expected_fulfillments": intent.expected_fulfillments,
                "approval_status": intent.approval_status,
                "intent_hash": intent.intent_hash,
            }
        )
        return payload

    @staticmethod
    def _approval_view(approval: ApprovalRequest) -> dict[str, Any]:
        return {
            "id": approval.id,
            "purchase_intent_id": approval.purchase_intent_id,
            "intent_hash": approval.intent_hash,
            "status": approval.status,
            "required_roles": approval.required_roles,
            "approved_roles": approval.approved_roles,
            "expires_at": approval.expires_at.isoformat(),
        }

    @staticmethod
    def _payment_handoff_view(handoff: PaymentHandoff) -> dict[str, Any]:
        return {
            "id": handoff.id,
            "purchase_intent_id": handoff.purchase_intent_id,
            "approval_request_id": handoff.approval_request_id,
            "intent_hash": handoff.intent_hash,
            "handoff_hash": handoff.handoff_hash,
            "destination_url": handoff.destination_url,
            "recipient": handoff.recipient,
            "amount": f"{handoff.amount:.2f}",
            "currency": handoff.currency,
            "reference": handoff.reference,
            "status": handoff.status,
            "expires_at": handoff.expires_at.isoformat(),
            "opened_at": handoff.opened_at.isoformat() if handoff.opened_at else None,
        }

    @classmethod
    def _outcome_checkpoint_view(cls, checkpoint: OutcomeCheckpoint) -> dict[str, Any]:
        return {
            "id": checkpoint.id,
            "purchase_intent_id": checkpoint.purchase_intent_id,
            "decision_id": checkpoint.decision_id,
            "decision_hash": checkpoint.decision_hash,
            "solution_plan_id": checkpoint.solution_plan_id,
            "metric": checkpoint.metric_id,
            "target_value": cls._metric_value(checkpoint.target_value),
            "target_operator": checkpoint.target_operator,
            "observed_value": cls._metric_value(checkpoint.observed_value),
            "checkpoint_days": checkpoint.checkpoint_days,
            "measurement_started_at": checkpoint.measurement_started_at.isoformat(),
            "checkpoint_due_at": checkpoint.checkpoint_due_at.isoformat(),
            "observed_at": checkpoint.observed_at.isoformat(),
            "state": checkpoint.state,
            "source_class": checkpoint.source_class,
            "source_reference_hash": checkpoint.source_reference_hash,
            "checkpoint_hash": checkpoint.checkpoint_hash,
            "preference_proposal": deepcopy(checkpoint.preference_proposal),
        }

    @staticmethod
    def _metric_value(value: Decimal) -> str:
        rendered = format(value, "f")
        if "." in rendered:
            rendered = rendered.rstrip("0").rstrip(".")
        return rendered or "0"

    @staticmethod
    def _as_utc(value: datetime | str) -> datetime:
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _workflow_urls(workflow_id: str) -> dict[str, Any]:
        return {
            "workflow_id": workflow_id,
            "status_url": f"/v1/workflows/{workflow_id}",
            "events_url": f"/v1/workflows/{workflow_id}/events",
        }

    @staticmethod
    async def _require_current_decision(
        session: Any,
        organization_id: str,
        decision: DecisionRecord,
    ) -> None:
        current_id = (
            await session.execute(
                select(DecisionRecord.id)
                .where(
                    DecisionRecord.organization_id == organization_id,
                    DecisionRecord.purchase_request_id == decision.purchase_request_id,
                )
                .order_by(DecisionRecord.version.desc())
                .limit(1)
            )
        ).scalar_one()
        if current_id != decision.id:
            raise ApiProblem(
                code="DECISION_SUPERSEDED",
                message="This Decision version is historical and cannot start a new action.",
                status_code=409,
                next_action="review_current_decision",
                details={"current_decision_id": current_id},
            )

    @staticmethod
    def _missing(kind: str) -> ApiProblem:
        return ApiProblem(
            code=f"{kind}_NOT_FOUND",
            message=f"The requested {kind.lower().replace('_', ' ')} was not found.",
            status_code=404,
        )

    @classmethod
    async def _not_found(cls, awaitable: Any, kind: str) -> Any:
        try:
            return await awaitable
        except RecordNotFound as error:
            raise cls._missing(kind) from error


def translate_persistence_conflict(error: Exception) -> ApiProblem:
    if isinstance(error, IdempotencyConflict):
        return ApiProblem(
            code="IDEMPOTENCY_CONFLICT",
            message="The idempotency key was already used with a different request body.",
            status_code=409,
            retryable=False,
            next_action="use_original_request_or_new_key",
        )
    return ApiProblem(
        code="STATE_CONFLICT",
        message="The resource changed or the requested transition is not allowed.",
        status_code=409,
        retryable=False,
        next_action="refresh_resource",
    )
