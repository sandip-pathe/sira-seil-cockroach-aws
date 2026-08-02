"""Application service backed by PostgreSQL repositories and frozen fixtures."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import delete, func, select, text

from decision_engine import (
    DecisionGraphDecision,
    DecisionGraphInput,
    evaluate_decision_graph,
    load_demo_decision_graph_input,
)
from integrations.errors import ProviderError, ProviderErrorCode
from integrations.prava.models import (
    PravaMerchantDetails,
    PravaProductDetails,
    PravaSessionRequest,
)
from persistence.database import Database
from persistence.models import (
    ActionRun,
    ApprovalEvent,
    ApprovalRequest,
    BrowserReturnBinding,
    CalibrationRun,
    CandidateFeedback,
    CandidateSetMember,
    CounterfactualRecordModel,
    DecisionGateResult,
    DecisionRecord,
    DecisionSimulation,
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
    Organization,
    OutboxEvent,
    PaymentAttempt,
    PaymentSession,
    PurchaseBriefVersion,
    PurchaseIntent,
    PurchaseRequest,
    Receipt,
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
    TransactionTransition,
    WorkflowRun,
)
from persistence.repositories import (
    IdempotencyConflict,
    PersistenceConflict,
    RecordNotFound,
    WorkflowRepository,
    new_id,
)

from .callback_state import BrowserReturnStateSigner
from .decision_room_projection import project_decision_room
from .errors import ApiProblem, SetupBlocked
from .fixtures import DEMO, DemoFixtureBundle, content_hash
from .graph_ledger import DecisionLedgerMetadata, build_decision_ledger
from .graph_persistence import (
    EvaluationPersistenceMetadata,
    build_evaluation_graph_write,
    ensure_evaluation_pipeline_version,
)
from .providers import PravaRuntimeConfiguration

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
        browser_return_signer: BrowserReturnStateSigner | None = None,
        browser_return_ttl_seconds: int = 600,
    ) -> None:
        self.database = database
        self.fixtures = fixtures
        self.allow_development_tenant_bootstrap = allow_development_tenant_bootstrap
        self.browser_return_signer = browser_return_signer or BrowserReturnStateSigner(
            "development-only-browser-return-key"  # pragma: allowlist secret
        )
        self.browser_return_ttl_seconds = browser_return_ttl_seconds

    def _fixture_bundle(self) -> DemoFixtureBundle:
        if self.fixtures is None:
            raise SetupBlocked(
                "production_decision_pipeline",
                ["SENSO_PROVIDER_CONFIGURATION", "AGENT_RUNTIME_CONFIGURATION"],
            )
        return self.fixtures

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
    ) -> tuple[DecisionGraphInput, DecisionGraphDecision, dict[str, Any], dict[str, Any]]:
        """Run the deterministic graph and bind DB-owned artifact identifiers."""

        fixtures = self._fixture_bundle()
        graph_input = load_demo_decision_graph_input(DEMO)
        graph_input = replace(
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
        return graph_input, graph_decision, ledger, patch

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
        )
        await repository.add_evaluation_graph(graph_write)
        return graph_write.evaluation_run.id

    async def health(self) -> str:
        try:
            async with self.database.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return "configured"
        except Exception:
            return "unavailable"

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
                TransactionTransition,
                Entitlement,
                ApprovalEvent,
                PaymentAttempt,
                BrowserReturnBinding,
                PaymentSession,
                MerchantOrder,
                Receipt,
                ApprovalRequest,
                PurchaseIntent,
                CandidateFeedback,
                Engagement,
                CalibrationRun,
                DecisionSimulation,
                DecisionRecord,
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

            brief = deepcopy(fixtures.purchase_brief)
            requirement = deepcopy(fixtures.requirement_brief)
            graph_input, graph_decision, ledger, patch = self._demo_graph_artifacts(
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
                    "fixture_label": "DEVELOPMENT_FIXTURE_NON_PRODUCTION",
                },
                request_hash=content_hash({"request_id": "req_demo", "version": 1}),
                created_at=graph_input.evaluated_at,
                updated_at=graph_input.evaluated_at,
            )
            session.add(request)
            session.add(
                PurchaseBriefVersion(
                    id=brief["purchase_brief_id"],
                    organization_id=organization_id,
                    purchase_request_id=request.id,
                    version=brief["version"],
                    status=brief["status"],
                    payload=brief,
                    content_hash=brief["content_hash"],
                    supersedes_id=None,
                )
            )
            session.add(
                RequirementBriefVersion(
                    id=requirement["requirement_brief_id"],
                    organization_id=organization_id,
                    purchase_request_id=request.id,
                    purchase_brief_id=brief["purchase_brief_id"],
                    version=requirement["version"],
                    payload=requirement,
                    content_hash=requirement["content_hash"],
                )
            )
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
                    receipt=None,
                    superseded_by=None,
                ),
            }
            session.add(decision_record)
            evaluation_run_id = await self._persist_base_graph(
                repository=repository,
                organization_id=organization_id,
                request_id=request.id,
                purchase_brief_id=str(brief["purchase_brief_id"]),
                decision_id=decision_record.id,
                graph_input=graph_input,
                graph_decision=graph_decision,
                ledger=ledger,
            )
            decision_record.payload = {
                **decision_record.payload,
                "graph": {
                    **decision_record.payload["graph"],
                    "evaluation_run_id": evaluation_run_id,
                },
            }
            session.add(
                StackSnapshot(
                    id="stack_consultco_v1",
                    organization_id=organization_id,
                    version=1,
                    manifest=fixtures.stack_manifest,
                    lock=fixtures.stack_lock,
                    lock_hash=fixtures.stack_lock["content_hash"],
                )
            )
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
                payload=body,
                request_hash=request_hash,
            )
            await repository.add_purchase_request(record)
            if self.fixtures is not None:
                await self._add_request_briefs(session, organization_id, record)
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
            graph_input, graph_decision, ledger, stack_patch = self._demo_graph_artifacts(
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
                    receipt=None,
                    superseded_by=None,
                ),
            }
            session.add(decision_record)
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
                view["payment"]["status"] = intent.payment_status
                view["fulfillment"]["status"] = intent.fulfillment_status
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
                receipt = (
                    await session.execute(
                        select(Receipt).where(
                            Receipt.organization_id == organization_id,
                            Receipt.purchase_intent_id == intent.id,
                        )
                    )
                ).scalar_one_or_none()
                if receipt is not None:
                    view["receipt"] = receipt.payload
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
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            brief = await self._not_found(
                repository.get_requirement_brief(brief_id), "REQUIREMENT_BRIEF"
            )
            if actor_party == "SELLER":
                engagement = (
                    await session.execute(
                        select(Engagement).where(
                            Engagement.organization_id == organization_id,
                            Engagement.requirement_brief_id == brief.id,
                            Engagement.requirement_brief_version == brief.version,
                            Engagement.requirement_brief_hash == brief.content_hash,
                            Engagement.expected_seller_actor_id == actor_id,
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
            graph_input = load_demo_decision_graph_input(DEMO)
            graph = evaluate_decision_graph(
                graph_input,
                evaluation_id=f"calibration_{run_id}",
                generated_at=graph_input.evaluated_at,
            )
            plan_by_product = {
                plan.components[0].component_id: plan
                for plan in graph.base.plans
                if plan.components and plan.components[0].source_type == "PACK"
            }
            status_by_candidate = {
                candidate.pack_id: plan_by_product[candidate.product_id].status.value
                for candidate in graph_input.candidates
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
                engagement_id = new_id("eng")
                session.add(
                    Engagement(
                        id=engagement_id,
                        organization_id=organization_id,
                        purchase_request_id=request_id,
                        requirement_brief_id=requirement_brief.id,
                        requirement_brief_version=requirement_brief.version,
                        requirement_brief_hash=requirement_brief.content_hash,
                        candidate_id=candidate_id,
                        expected_buyer_actor_id=actor_id,
                        expected_seller_actor_id=seller_actor_id,
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
            if actor_id != expected_actor_id:
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
                    "buyer": "buyer-contact-channel-demo",
                    "seller": "seller-contact-channel-demo",
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

        graph_input = load_demo_decision_graph_input(DEMO)
        replay = evaluate_decision_graph(
            graph_input,
            evaluation_id=str(ledger["evaluation"]["evaluation_id"]),
            generated_at=graph_input.evaluated_at,
        )
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
            generic_plan.components[0].component_id,
            generic_plan.components[0].component_id,
        )
        company_candidate = pack_by_product.get(
            company_plan.components[0].component_id,
            company_plan.components[0].component_id,
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

        graph_input = load_demo_decision_graph_input(DEMO)
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
            decision = await self._not_found(
                repository.get_decision(evaluation_run_id), "EVALUATION_RUN"
            )
            ledger = deepcopy(decision.payload["ledger"])

        score_components = [
            component for plan in ledger["solution_plans"] for component in plan["score_components"]
        ]
        preference_weights = {
            str(component["criterion_id"]): int(component["weight"])
            for component in score_components
        }
        selected_plan = next(
            plan
            for plan in ledger["solution_plans"]
            if plan["solution_plan_id"] == ledger["selected_solution_plan_id"]
        )
        created_at = datetime.fromisoformat(str(ledger["created_at"]).replace("Z", "+00:00"))
        _graph_input, replay, replayed_ledger, _patch = self._demo_graph_artifacts(
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
            "evaluation_run_id": evaluation_run_id,
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
            now = datetime.now(UTC)
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
                session.add(
                    PurchaseBriefVersion(
                        id=resulting_id,
                        organization_id=organization_id,
                        purchase_request_id=base.purchase_request_id,
                        version=resulting_version,
                        status="APPROVED",
                        payload=payload,
                        content_hash=payload["content_hash"],
                        supersedes_id=base.id,
                    )
                )

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
                session.add(
                    RequirementBriefVersion(
                        id=requirement_id,
                        organization_id=organization_id,
                        purchase_request_id=base.purchase_request_id,
                        purchase_brief_id=resulting_id,
                        version=requirement_payload["version"],
                        payload=requirement_payload,
                        content_hash=requirement_payload["content_hash"],
                    )
                )

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
                graph_input, graph_decision, graph_ledger, graph_patch = self._demo_graph_artifacts(
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
                            StackSnapshot.version == graph_patch["base_snapshot"],
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
                        receipt=None,
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
        fixtures = self._fixture_bundle()
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
            if body.get("solution_plan_id") not in {None, selected_plan_id}:
                raise ApiProblem(
                    code="SOLUTION_PLAN_MISMATCH",
                    message=(
                        "The requested Solution Plan is not the selected exact decision output."
                    ),
                    status_code=409,
                    next_action="refresh_decision",
                )
            ledger = decision.payload.get("ledger")
            solution_plans = ledger.get("solution_plans", []) if isinstance(ledger, dict) else []
            selected_plan = next(
                (
                    plan
                    for plan in solution_plans
                    if isinstance(plan, dict) and plan.get("solution_plan_id") == selected_plan_id
                ),
                None,
            )
            stack_patch_id = (
                selected_plan.get("stack_patch_id") if isinstance(selected_plan, dict) else None
            )
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
            payload = fixtures.purchase_intent_payload()
            payload["decision_id"] = decision.id
            payload["decision_version"] = decision.version
            payload["decision_hash"] = decision.decision_hash
            selection = decision.payload.get("selection")
            payload["selection_id"] = (
                str(selection["selection_id"])
                if isinstance(selection, dict) and isinstance(selection.get("selection_id"), str)
                else f"selection_{decision.id}"
            )
            payload["solution_plan_id"] = selected_plan_id
            payload["stack_patch_id"] = stack_patch_id
            payload["purchase_intent_id"] = new_id("pi")
            payload["intent_hash"] = content_hash(
                {k: v for k, v in payload.items() if k != "intent_hash"}
            )
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
                payment_status="NOT_STARTED",
                fulfillment_status="NOT_STARTED",
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
            if self._as_utc(intent.quote_expires_at) <= datetime.now(UTC):
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
                expires_at=datetime.now(UTC) + timedelta(minutes=60),
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
            now = datetime.now(UTC)
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
            expiry_problem = self._approval_expiry_problem(approval, intent, datetime.now(UTC))
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

    @classmethod
    def _approval_expiry_problem(
        cls, approval: ApprovalRequest, intent: PurchaseIntent, now: datetime
    ) -> ApiProblem | None:
        if cls._as_utc(approval.expires_at) <= now:
            return ApiProblem(
                code="APPROVAL_EXPIRED",
                message="This exact-hash approval request has expired.",
                status_code=409,
                next_action="create_approval_request",
            )
        if cls._as_utc(intent.quote_expires_at) <= now:
            return ApiProblem(
                code="QUOTE_EXPIRED",
                message="The quote expired before approval completed.",
                status_code=409,
                next_action="refresh_quote",
            )
        return None

    @staticmethod
    def _require_approval_role(
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

    async def create_prava_session(
        self,
        *,
        organization_id: str,
        actor_id: str,
        intent_id: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        configuration = PravaRuntimeConfiguration.load()
        return_url = str(body["return_url"])
        configuration.validate_return_url(return_url)
        callback_state = self.browser_return_signer.issue()
        callback_state_hash = self.browser_return_signer.digest(callback_state)
        return_url_hash = self.browser_return_signer.digest(return_url)
        request_hash = content_hash({"intent_id": intent_id, "return_url": return_url})
        internal_session_id = new_id("pays")
        idempotency_record_id: str
        session_request: PravaSessionRequest

        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation="prava_sessions.create",
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
            if intent.approval_status != "APPROVED":
                raise ApiProblem(
                    code="APPROVAL_REQUIRED",
                    message="Every required role must approve the exact current intent hash first.",
                    status_code=409,
                    next_action="complete_approval",
                )
            if self._as_utc(intent.quote_expires_at) <= datetime.now(UTC):
                raise ApiProblem(
                    code="QUOTE_EXPIRED",
                    message="The approved quote expired before Prava session creation.",
                    status_code=409,
                    next_action="refresh_quote",
                )
            existing = (
                await session.execute(
                    select(PaymentSession)
                    .where(
                        PaymentSession.organization_id == organization_id,
                        PaymentSession.purchase_intent_id == intent_id,
                    )
                    .order_by(PaymentSession.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if existing is not None:
                if existing.status == "SESSION_CREATED":
                    response = self._prava_session_view(existing)
                    await repository.complete_idempotency(
                        claim.record,
                        response_status=201,
                        response_payload=response,
                        response_reference=existing.id,
                    )
                    return 201, response
                raise ApiProblem(
                    code="SESSION_CREATE_RECONCILIATION_REQUIRED",
                    message="A prior provider session create is incomplete; do not create another.",
                    status_code=409,
                    retryable=False,
                    next_action="reconcile_provider_session",
                )

            configuration.validate_merchant_url(intent.merchant_url)
            line_items = intent.payload.get("line_items")
            if not isinstance(line_items, list) or not line_items:
                raise ApiProblem(
                    code="PURCHASE_INTENT_INVALID",
                    message="The locked Purchase Intent has no line items.",
                    status_code=409,
                )
            products = tuple(
                PravaProductDetails(
                    description=str(item["description"]),
                    unit_price=str(item["unit_amount"]),
                    quantity=int(item["quantity"]),
                    product_id=str(item["line_item_id"]),
                )
                for item in line_items
                if isinstance(item, dict)
            )
            session_request = PravaSessionRequest(
                user_id=actor_id,
                user_email=configuration.user_email,
                total_amount=f"{intent.amount:.2f}",
                currency=intent.currency,
                merchant=PravaMerchantDetails(
                    name=intent.merchant_name,
                    url=intent.merchant_url,
                    country_code_iso2=configuration.merchant_country,
                ),
                products=products,
                callback_url=configuration.callback_url_with_state(callback_state),
            )
            placeholder = PaymentSession(
                id=internal_session_id,
                organization_id=organization_id,
                purchase_intent_id=intent_id,
                provider="PRAVA",
                provider_session_id=f"pending:{internal_session_id}",
                provider_order_id=f"pending:{internal_session_id}",
                hosted_url="",
                expires_at=datetime.now(UTC) + timedelta(minutes=15),
                status="CREATING",
            )
            session.add(placeholder)
            idempotency_record_id = claim.record.id

        adapter = configuration.build_adapter(canonical_merchant_url=session_request.merchant.url)
        provider_error: ProviderError | None = None
        unexpected_failure = False
        hosted_session = None
        try:
            hosted_session = await adapter.create_session(session_request)
        except ProviderError as error:
            provider_error = error
        except Exception:
            unexpected_failure = True
        finally:
            await adapter.aclose()

        if provider_error is not None or unexpected_failure:
            retryable = provider_error.retryable if provider_error is not None else True
            safe_code = (
                provider_error.code.value
                if provider_error is not None
                else ProviderErrorCode.UNAVAILABLE.value
            )
            await self._mark_session_create_failed(
                organization_id=organization_id,
                intent_id=intent_id,
                internal_session_id=internal_session_id,
                safe_code=safe_code,
                uncertain=retryable,
            )
            raise ApiProblem(
                code=safe_code,
                message="Prava session creation did not produce a safely confirmed session.",
                status_code=503 if retryable else 502,
                retryable=retryable,
                next_action=(
                    "reconcile_provider_session" if retryable else "review_provider_configuration"
                ),
            ) from None
        if hosted_session is None:
            raise RuntimeError("unreachable hosted session state")

        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            payment_session = (
                await session.execute(
                    select(PaymentSession)
                    .where(
                        PaymentSession.id == internal_session_id,
                        PaymentSession.organization_id == organization_id,
                    )
                    .with_for_update()
                )
            ).scalar_one()
            payment_session.provider_session_id = hosted_session.session_id
            payment_session.provider_order_id = hosted_session.order_id
            payment_session.hosted_url = hosted_session.hosted_url
            payment_session.expires_at = hosted_session.expires_at
            payment_session.status = "SESSION_CREATED"
            session.add(
                BrowserReturnBinding(
                    id=new_id("brb"),
                    organization_id=organization_id,
                    purchase_intent_id=intent_id,
                    payment_session_id=payment_session.id,
                    actor_id=actor_id,
                    state_hash=callback_state_hash,
                    provider_session_hash=self.browser_return_signer.digest(
                        hosted_session.session_id
                    ),
                    return_url_hash=return_url_hash,
                    expires_at=min(
                        self._as_utc(hosted_session.expires_at),
                        datetime.now(UTC) + timedelta(seconds=self.browser_return_ttl_seconds),
                    ),
                    consumed_at=None,
                )
            )
            await repository.transition_purchase_intent(
                intent_id=intent_id,
                state_field="payment_status",
                allowed_from={"NOT_STARTED"},
                to_state="SESSION_CREATED",
                event_key=f"prava-session-created:{hosted_session.session_id}",
                actor_type="provider",
                actor_id="prava",
                reason_code="HOSTED_SESSION_CREATED",
                payload_hash=content_hash(
                    {
                        "session_id": hosted_session.session_id,
                        "order_id": hosted_session.order_id,
                        "expires_at": hosted_session.expires_at.isoformat(),
                    }
                ),
                provider_event_ref=hosted_session.session_id,
            )
            idempotency_record = (
                await session.execute(
                    select(IdempotencyRecord).where(
                        IdempotencyRecord.id == idempotency_record_id,
                        IdempotencyRecord.organization_id == organization_id,
                    )
                )
            ).scalar_one()
            response = self._prava_session_view(payment_session)
            await repository.complete_idempotency(
                idempotency_record,
                response_status=201,
                response_payload=response,
                response_reference=payment_session.id,
            )
            return 201, response

    async def accept_prava_browser_return(
        self,
        *,
        organization_id: str,
        actor_id: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        state = str(body["state"])
        return_url = str(body["return_url"])
        if not self.browser_return_signer.verify(state):
            raise ApiProblem(
                code="CALLBACK_STATE_INVALID",
                message="The browser-return state could not be verified.",
                status_code=400,
                next_action="restart_hosted_checkout",
            )
        state_hash = self.browser_return_signer.digest(state)
        return_url_hash = self.browser_return_signer.digest(return_url)
        now = datetime.now(UTC)
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            binding = (
                await session.execute(
                    select(BrowserReturnBinding)
                    .where(
                        BrowserReturnBinding.organization_id == organization_id,
                        BrowserReturnBinding.state_hash == state_hash,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if binding is None or binding.actor_id != actor_id:
                raise ApiProblem(
                    code="CALLBACK_STATE_INVALID",
                    message="The browser-return state is not valid for this identity.",
                    status_code=403,
                    next_action="restart_hosted_checkout",
                )
            if binding.consumed_at is not None:
                raise ApiProblem(
                    code="CALLBACK_STATE_REPLAYED",
                    message="The browser-return state has already been consumed.",
                    status_code=409,
                    next_action="poll_purchase_status",
                )
            if binding.return_url_hash != return_url_hash:
                raise ApiProblem(
                    code="CALLBACK_BINDING_MISMATCH",
                    message="The browser return does not match the approved destination.",
                    status_code=403,
                    next_action="restart_hosted_checkout",
                )
            payment_session = (
                await session.execute(
                    select(PaymentSession)
                    .where(
                        PaymentSession.id == binding.payment_session_id,
                        PaymentSession.organization_id == organization_id,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if payment_session is None:
                raise ApiProblem(
                    code="CALLBACK_BINDING_MISMATCH",
                    message="The bound payment session is unavailable.",
                    status_code=409,
                    next_action="restart_hosted_checkout",
                )
            intent = await repository.get_purchase_intent(binding.purchase_intent_id, lock=True)
            if (
                payment_session.purchase_intent_id != intent.id
                or binding.provider_session_hash
                != self.browser_return_signer.digest(payment_session.provider_session_id)
            ):
                raise ApiProblem(
                    code="CALLBACK_BINDING_MISMATCH",
                    message="The browser return no longer matches the locked payment session.",
                    status_code=409,
                    next_action="restart_hosted_checkout",
                )
            if (
                self._as_utc(binding.expires_at) <= now
                or self._as_utc(payment_session.expires_at) <= now
                or self._as_utc(intent.quote_expires_at) <= now
            ):
                raise ApiProblem(
                    code="CALLBACK_STATE_EXPIRED",
                    message="The browser-return authority has expired.",
                    status_code=409,
                    next_action="restart_hosted_checkout",
                )
            if (
                payment_session.status != "SESSION_CREATED"
                or intent.payment_status != "SESSION_CREATED"
                or intent.approval_status != "APPROVED"
            ):
                raise ApiProblem(
                    code="CALLBACK_STATE_INVALID_STATE",
                    message="The locked purchase is not ready for browser-return continuation.",
                    status_code=409,
                    next_action="poll_purchase_status",
                )

            binding.consumed_at = now
            payment_session.status = "CARDHOLDER_PENDING"
            await repository.transition_purchase_intent(
                intent_id=intent.id,
                state_field="payment_status",
                allowed_from={"SESSION_CREATED"},
                to_state="CARDHOLDER_PENDING",
                event_key=f"prava-browser-return:{payment_session.id}",
                actor_type="user",
                actor_id=actor_id,
                reason_code="AUTHENTICATED_BROWSER_RETURN",
                payload_hash=content_hash(
                    {
                        "payment_session_id": payment_session.id,
                        "state_hash": binding.state_hash,
                    }
                ),
            )
            workflow_id = f"wf_checkout_{intent.id}"
            workflow = (
                await session.execute(
                    select(WorkflowRun)
                    .where(
                        WorkflowRun.id == workflow_id,
                        WorkflowRun.organization_id == organization_id,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if workflow is None:
                session.add(
                    WorkflowRun(
                        id=workflow_id,
                        organization_id=organization_id,
                        aggregate_type="purchase_intent",
                        aggregate_id=intent.id,
                        operation="purchase_checkout",
                        status="PENDING",
                        result_reference=f"/v1/purchase-intents/{intent.id}/status",
                        safe_error_code=None,
                        event_log=[
                            {
                                "id": "1",
                                "status": "PENDING",
                                "message": "Hosted authorization returned; checkout queued",
                            }
                        ],
                    )
                )
            await repository.add_outbox(
                aggregate_type="purchase_intent",
                aggregate_id=intent.id,
                event_type="purchase_checkout.requested",
                event_key=f"purchase-checkout-requested:{payment_session.id}",
                payload={
                    "workflow_id": workflow_id,
                    "purchase_intent_id": intent.id,
                    "intent_hash": intent.intent_hash,
                    "payment_session_id": payment_session.id,
                    "prava_session_id": payment_session.provider_session_id,
                },
            )
            return self._workflow_urls(workflow_id)

    async def _mark_session_create_failed(
        self,
        *,
        organization_id: str,
        intent_id: str,
        internal_session_id: str,
        safe_code: str,
        uncertain: bool,
    ) -> None:
        target = "UNCERTAIN" if uncertain else "FAILED"
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            payment_session = (
                await session.execute(
                    select(PaymentSession)
                    .where(
                        PaymentSession.id == internal_session_id,
                        PaymentSession.organization_id == organization_id,
                    )
                    .with_for_update()
                )
            ).scalar_one()
            payment_session.status = target
            await repository.transition_purchase_intent(
                intent_id=intent_id,
                state_field="payment_status",
                allowed_from={"NOT_STARTED"},
                to_state=target,
                event_key=f"prava-session-create-failed:{internal_session_id}",
                actor_type="provider",
                actor_id="prava",
                reason_code=safe_code,
                payload_hash=content_hash(
                    {"payment_session_id": internal_session_id, "safe_code": safe_code}
                ),
            )

    async def purchase_status(self, organization_id: str, intent_id: str) -> dict[str, Any]:
        async with self.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            intent = await self._not_found(
                repository.get_purchase_intent(intent_id), "PURCHASE_INTENT"
            )
            return {
                "purchase_intent_id": intent.id,
                "approval_status": intent.approval_status,
                "payment_status": intent.payment_status,
                "fulfillment_status": intent.fulfillment_status,
                "purchase_state": self._derive_purchase_state(intent),
                "deployment_state": "STAGED"
                if intent.fulfillment_status == "VERIFIED"
                else "NOT_STARTED",
                "outcome_state": "NOT_MEASURED",
            }

    async def get_receipt(self, organization_id: str, purchase_id: str) -> dict[str, Any]:
        async with self.database.transaction(organization_id) as session:
            receipt = (
                await session.execute(
                    select(Receipt).where(
                        Receipt.organization_id == organization_id,
                        (Receipt.id == purchase_id) | (Receipt.purchase_intent_id == purchase_id),
                    )
                )
            ).scalar_one_or_none()
            if receipt is None:
                raise ApiProblem(
                    code="RECEIPT_NOT_AVAILABLE",
                    message=(
                        "A receipt exists only after payment reconciliation and required "
                        "entitlement verification."
                    ),
                    status_code=404,
                    next_action="check_purchase_status",
                )
            return deepcopy(receipt.payload)

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
    ) -> None:
        fixtures = self._fixture_bundle()
        brief = deepcopy(fixtures.purchase_brief)
        brief_id = f"pb_{request.id}"
        brief["purchase_brief_id"] = brief_id
        brief["request_id"] = request.id
        brief["organization_id"] = organization_id
        brief["intent"] = request.intent
        brief["content_hash"] = content_hash(
            {key: value for key, value in brief.items() if key != "content_hash"}
        )
        requirement = deepcopy(fixtures.requirement_brief)
        requirement_id = f"rb_{request.id}"
        requirement["requirement_brief_id"] = requirement_id
        requirement["purchase_brief_id"] = brief_id
        requirement["intent"] = request.intent
        requirement["content_hash"] = content_hash(
            {key: value for key, value in requirement.items() if key != "content_hash"}
        )
        session.add(
            PurchaseBriefVersion(
                id=brief_id,
                organization_id=organization_id,
                purchase_request_id=request.id,
                version=1,
                status="APPROVED",
                payload=brief,
                content_hash=brief["content_hash"],
                supersedes_id=None,
            )
        )
        session.add(
            RequirementBriefVersion(
                id=requirement_id,
                organization_id=organization_id,
                purchase_request_id=request.id,
                purchase_brief_id=brief_id,
                version=1,
                payload=requirement,
                content_hash=requirement["content_hash"],
            )
        )

    @staticmethod
    def _request_view(request: PurchaseRequest) -> dict[str, Any]:
        return {
            "id": request.id,
            "organization_id": request.organization_id,
            "intent": request.intent,
            "status": request.status,
            "visibility": request.visibility,
            "version": request.version,
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
                "payment_status": intent.payment_status,
                "fulfillment_status": intent.fulfillment_status,
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
    def _prava_session_view(payment_session: PaymentSession) -> dict[str, Any]:
        return {
            "id": payment_session.id,
            "purchase_intent_id": payment_session.purchase_intent_id,
            "status": payment_session.status,
            "hosted_url": payment_session.hosted_url,
            "expires_at": payment_session.expires_at.isoformat(),
            "production_provider": "PRAVA",
            "production_verified": False,
            "setup_blocked": False,
            "missing_configuration": [],
        }

    @staticmethod
    def _derive_purchase_state(intent: PurchaseIntent) -> str:
        if intent.approval_status != "APPROVED":
            return "AWAITING_APPROVAL"
        if intent.payment_status == "NOT_STARTED":
            return "APPROVED_NOT_STARTED"
        if intent.payment_status in {
            "SESSION_CREATED",
            "CARDHOLDER_PENDING",
            "CHECKOUT_PENDING",
            "MERCHANT_APPROVED",
            "REPORTING",
        }:
            return "PAYMENT_IN_PROGRESS"
        if intent.payment_status in {"DECLINED", "EXPIRED", "FAILED"}:
            return "PAYMENT_NOT_COMPLETED"
        if intent.payment_status == "UNCERTAIN":
            return "PAYMENT_UNCERTAIN"
        if intent.payment_status == "PRAVA_COMPLETED":
            if intent.fulfillment_status == "VERIFIED":
                return "PURCHASE_FULFILLED"
            return "PAID_UNFULFILLED"
        return "PAYMENT_UNCERTAIN"

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
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
