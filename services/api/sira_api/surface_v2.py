"""Application service for the current action-neutral API surface."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select

from persistence.models import (
    ActionRun,
    ApprovalRequest,
    CandidateFeedback,
    DecisionRecord,
    EvaluationRun,
    EvaluationSolutionPlan,
    PaymentHandoff,
    PurchaseBriefVersion,
    PurchaseIntent,
    PurchaseRequest,
)
from persistence.repositories import WorkflowRepository, new_id

from .decision_room_projection import actor_role, project_decision_room, selection_payload
from .errors import ApiProblem
from .fixtures import content_hash
from .service import WorkflowService

_FEEDBACK_TO_LEGACY = {
    "KEEP_FOR_COMPARISON": "SHORTLIST",
    "ELIMINATE": "PASS",
    "ASK_VENDOR": "REQUEST_OFFER",
    "SAVE": "SAVE_FOR_LATER",
    "NEED_EVIDENCE": "NOT_ENOUGH_EVIDENCE",
}

_PACK_BY_OPTION = {
    "sol_replace_low_price_policy_fail": "fixture_low_price_policy_fail",
    "sol_replace_honest_anti_fit": "fixture_honest_anti_fit",
    "sol_replace_eligible_runner_up": "fixture_eligible_runner_up",
    "sol_replace_selected_fit": "fixture_selected_fit",
}


class DecisionRoomSurface:
    def __init__(self, service: WorkflowService) -> None:
        self.service = service

    async def list_requests(
        self, *, organization_id: str, roles: frozenset[str], party: str | None
    ) -> dict[str, Any]:
        async with self.service.database.transaction(organization_id) as session:
            requests = (
                await session.execute(
                    select(PurchaseRequest)
                    .where(PurchaseRequest.organization_id == organization_id)
                    .order_by(PurchaseRequest.created_at.desc(), PurchaseRequest.id)
                )
            ).scalars()
            rows = [
                await self._request_projection(session, organization_id, item, roles, party)
                for item in requests
            ]
        return {
            "active": [item for item in rows if item["status"] not in {"COMPLETED", "CLOSED"}],
            "history": [item for item in rows if item["status"] in {"COMPLETED", "CLOSED"}],
            "available_actions": (
                [
                    {
                        "id": "NEW_DECISION",
                        "label": "New decision",
                        "method": "POST",
                        "href": "/v1/decision-requests",
                        "requires_confirmation": False,
                        "expires_at": None,
                    }
                ]
                if "can_submit_request" in roles
                else []
            ),
        }

    async def create_request(
        self,
        *,
        organization_id: str,
        actor_id: str,
        roles: frozenset[str],
        party: str | None,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        legacy_body = {
            "intent": body["intent"],
            "scenario_id": body.get("scenario_id"),
            "desired_outcome": (
                {
                    "metric": body["desired_outcome"],
                    "target": 1,
                    "checkpoint_days": 30,
                }
                if body.get("desired_outcome")
                else None
            ),
            "deadline": body.get("deadline"),
            "visibility": body["visibility"],
            "mission_id": body.get("mission_id"),
        }
        status_code, created = await self.service.create_purchase_request(
            organization_id=organization_id,
            actor_id=actor_id,
            idempotency_key=idempotency_key,
            body=legacy_body,
        )
        request_id = str(created["id"])
        projected = await self.get_request(
            organization_id=organization_id,
            request_id=request_id,
            roles=roles,
            party=party,
        )
        return status_code, projected

    async def get_request(
        self,
        *,
        organization_id: str,
        request_id: str,
        roles: frozenset[str],
        party: str | None,
    ) -> dict[str, Any]:
        async with self.service.database.transaction(organization_id) as session:
            record = (
                await session.execute(
                    select(PurchaseRequest).where(
                        PurchaseRequest.organization_id == organization_id,
                        PurchaseRequest.id == request_id,
                    )
                )
            ).scalar_one_or_none()
            if record is None:
                raise self.service._missing("DECISION_REQUEST")
            return await self._request_projection(session, organization_id, record, roles, party)

    async def decision_view(
        self,
        *,
        organization_id: str,
        request_id: str,
        roles: frozenset[str],
        party: str | None,
        decision_version: int | None = None,
    ) -> dict[str, Any]:
        fixtures = self.service._fixture_bundle()
        async with self.service.database.transaction(organization_id) as session:
            request = (
                await session.execute(
                    select(PurchaseRequest).where(
                        PurchaseRequest.organization_id == organization_id,
                        PurchaseRequest.id == request_id,
                    )
                )
            ).scalar_one_or_none()
            if request is None:
                raise self.service._missing("DECISION_REQUEST")
            statement = select(DecisionRecord).where(
                DecisionRecord.organization_id == organization_id,
                DecisionRecord.purchase_request_id == request_id,
            )
            if decision_version is None:
                statement = statement.order_by(DecisionRecord.version.desc()).limit(1)
            else:
                statement = statement.where(DecisionRecord.version == decision_version)
            decision = (await session.execute(statement)).scalar_one_or_none()
            if decision is None:
                raise self.service._missing("DECISION")
            superseded_by = (
                await session.execute(
                    select(DecisionRecord)
                    .where(
                        DecisionRecord.organization_id == organization_id,
                        DecisionRecord.supersedes_id == decision.id,
                    )
                    .order_by(DecisionRecord.version.asc())
                    .limit(1)
                )
            ).scalar_one_or_none()
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
            approval = None
            handoff = None
            if intent is not None:
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
            return project_decision_room(
                request=request,
                decision=decision,
                fixtures=fixtures,
                roles=roles,
                party=party,
                intent=intent,
                approval=approval,
                handoff=handoff,
                superseded_by=superseded_by,
            )

    async def decision_rules(self, *, organization_id: str, request_id: str) -> dict[str, Any]:
        async with self.service.database.transaction(organization_id) as session:
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
                raise self.service._missing("DECISION_RULES")
            payload = brief.payload
            rules: list[dict[str, Any]] = []
            for gate in payload.get("hard_gates", []):
                rules.append(
                    {
                        "id": gate["gate_id"],
                        "kind": "HARD_GATE",
                        "label": gate.get("label") or gate.get("reason") or gate["gate_id"],
                        "weight": None,
                        "required": True,
                        "version": brief.version,
                    }
                )
            for preference in payload.get("preferences", []):
                rules.append(
                    {
                        "id": preference["criterion_id"],
                        "kind": "PREFERENCE",
                        "label": preference.get("label") or preference["criterion_id"],
                        "weight": int(preference["weight"]),
                        "required": False,
                        "version": brief.version,
                    }
                )
            for index, requirement in enumerate(payload.get("approval_requirements", []), 1):
                rules.append(
                    {
                        "id": f"approval_{index}_{requirement['role']}",
                        "kind": "APPROVAL",
                        "label": f"Stage {requirement['stage']}: {requirement['role']}",
                        "weight": None,
                        "required": bool(requirement["required"]),
                        "version": brief.version,
                    }
                )
            return {
                "id": brief.id,
                "request_id": request_id,
                "version": brief.version,
                "content_hash": brief.content_hash,
                "rules": rules,
            }

    async def feedback(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_party: str | None,
        request_id: str,
        solution_plan_id: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        legacy_action = _FEEDBACK_TO_LEGACY[body["action"]]
        candidate_id = _PACK_BY_OPTION.get(solution_plan_id)
        if body["action"] == "ASK_VENDOR":
            if candidate_id is None:
                raise ApiProblem(
                    code="SELLER_ENGAGEMENT_NOT_APPLICABLE",
                    message="This current-stack action has no seller engagement target.",
                    status_code=409,
                )
            status_code, result = await self.service.candidate_action(
                organization_id=organization_id,
                actor_id=actor_id,
                actor_party=actor_party,
                request_id=request_id,
                candidate_id=candidate_id,
                idempotency_key=idempotency_key,
                body={
                    "action": legacy_action,
                    "reason": body["reason"],
                    "proposed_criterion_change": body.get("proposed_criterion_change"),
                },
            )
            return status_code, self._feedback_response(result, solution_plan_id, body)

        request_hash = content_hash(
            {"request_id": request_id, "solution_plan_id": solution_plan_id, **body}
        )
        async with self.service.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation="solution_option_feedback.create",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if claim.replay:
                return int(claim.record.response_status or 201), dict(
                    claim.record.response_payload or {}
                )
            request = await self.service._not_found(
                repository.get_purchase_request(request_id), "DECISION_REQUEST"
            )
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
                raise self.service._missing("DECISION")
            view = project_decision_room(
                request=request,
                decision=decision,
                fixtures=self.service._fixture_bundle(),
                roles=frozenset({"can_view_context", "can_select_recommendation"}),
                party="BUYER",
                intent=None,
                approval=None,
                handoff=None,
                superseded_by=None,
            )
            if not any(item["id"] == solution_plan_id for item in view["solution_options"]):
                raise self.service._missing("SOLUTION_OPTION")
            feedback_id = new_id("fb")
            proposal_id = new_id("proposal") if body.get("proposed_criterion_change") else None
            session.add(
                CandidateFeedback(
                    id=feedback_id,
                    organization_id=organization_id,
                    purchase_request_id=request.id,
                    candidate_id=solution_plan_id,
                    action=legacy_action,
                    reason=body["reason"],
                    actor_id=actor_id,
                    proposed_change=(
                        {
                            "proposal_id": proposal_id,
                            "base_purchase_brief_id": None,
                            "status": "PROPOSED",
                            "changes": [deepcopy(body["proposed_criterion_change"])],
                            "ranking_effect": False,
                        }
                        if proposal_id is not None
                        else None
                    ),
                )
            )
            response = {
                "id": feedback_id,
                "request_id": request_id,
                "solution_plan_id": solution_plan_id,
                "action": body["action"],
                "reason": body["reason"],
                "engagement_id": None,
                "proposal_id": proposal_id,
                "contact_details_revealed": False,
                "ranking_effect": False,
            }
            await repository.complete_idempotency(
                claim.record,
                response_status=201,
                response_payload=response,
                response_reference=feedback_id,
            )
            return 201, response

    async def select_plan(
        self,
        *,
        organization_id: str,
        actor_id: str,
        roles: frozenset[str],
        party: str | None,
        decision_id: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        request_hash = content_hash({"decision_id": decision_id, **body})
        async with self.service.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation="plan_selections.create",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if claim.replay:
                return int(claim.record.response_status or 201), dict(
                    claim.record.response_payload or {}
                )
            source = await self.service._not_found(repository.get_decision(decision_id), "DECISION")
            await self.service._require_current_decision(session, organization_id, source)
            if (
                source.version != body["decision_version"]
                or source.decision_hash != body["decision_hash"]
            ):
                raise ApiProblem(
                    code="DECISION_VERSION_HASH_MISMATCH",
                    message="Plan selection must bind the exact current Decision version and hash.",
                    status_code=409,
                    next_action="refresh_decision",
                )
            request = await self.service._not_found(
                repository.get_purchase_request(source.purchase_request_id), "DECISION_REQUEST"
            )
            projected = project_decision_room(
                request=request,
                decision=source,
                fixtures=self.service._fixture_bundle(),
                roles=roles,
                party=party,
                intent=None,
                approval=None,
                handoff=None,
                superseded_by=None,
            )
            option = next(
                (
                    item
                    for item in projected["solution_options"]
                    if item["id"] == body["solution_plan_id"]
                ),
                None,
            )
            if option is None:
                raise self.service._missing("SOLUTION_OPTION")
            if option["status"] not in {"SUPPORTED", "SUPPORTED_WITH_EXCEPTION"}:
                raise ApiProblem(
                    code="SOLUTION_OPTION_NOT_SELECTABLE",
                    message=(
                        "The selected action plan is not executable under the current Decision."
                    ),
                    status_code=409,
                    next_action="resolve_option_blocker",
                )
            # This mutation is the buyer's explicit, confirmed choice, not an
            # autonomous agent selection. Keep uncertainty visible in the ledger,
            # but do not prevent an authorized human from choosing a supported plan.
            if projected["rank_stability"]["status"] != "STABLE" and party != "BUYER":
                raise ApiProblem(
                    code="RANK_NOT_STABLE",
                    message="An unstable or undetermined Decision cannot be selected autonomously.",
                    status_code=409,
                    next_action="resolve_evidence_frontier",
                )
            selection_id = new_id("selection")
            now = datetime.now(UTC)
            selected_version = source.version + 1
            selected_id = new_id("dec")
            selection = selection_payload(
                source=source,
                solution_plan_id=body["solution_plan_id"],
                selected_by_role=actor_role(roles, party),
                selection_id=selection_id,
                selected_at=now,
            )
            payload = deepcopy(source.payload)
            payload["selection"] = selection
            ledger = cast(dict[str, Any], payload["ledger"])
            evaluation_hash = str(ledger["evaluation"]["evaluation_payload_hash"])
            payload["evaluation_payload_hash"] = evaluation_hash
            ledger.update(
                {
                    "decision_id": selected_id,
                    "decision_version": selected_version,
                    "decision_state": "CURRENT",
                    "supersedes_decision_id": source.id,
                    "decision_outcome": "SELECTED_SOLUTION_PLAN",
                    "selected_solution_plan_id": body["solution_plan_id"],
                    "created_at": now.isoformat().replace("+00:00", "Z"),
                }
            )
            ledger["decision_hash"] = content_hash(
                {key: value for key, value in ledger.items() if key != "decision_hash"}
            )
            selected_hash = str(ledger["decision_hash"])
            selected_record = DecisionRecord(
                id=selected_id,
                organization_id=organization_id,
                purchase_request_id=source.purchase_request_id,
                purchase_brief_id=source.purchase_brief_id,
                version=selected_version,
                supersedes_id=source.id,
                decision_hash=selected_hash,
                selected_solution_plan_id=body["solution_plan_id"],
                payload=payload,
            )
            session.add(selected_record)
            await repository.supersede_intents_for_decision_change(
                purchase_request_id=source.purchase_request_id,
                current_decision_id=selected_id,
                proposal_id=selection_id,
            )
            response = {
                "selection_id": selection_id,
                "source_decision_id": source.id,
                "selected_decision_id": selected_id,
                "solution_plan_id": body["solution_plan_id"],
                "decision_version": selected_version,
                "decision_hash": selected_hash,
                "state": "SELECTED",
                "action_run_href": f"/v1/decisions/{selected_id}/action-runs",
            }
            await repository.complete_idempotency(
                claim.record,
                response_status=201,
                response_payload=response,
                response_reference=selected_id,
            )
            return 201, response

    async def start_action_run(
        self,
        *,
        organization_id: str,
        actor_id: str,
        roles: frozenset[str],
        party: str | None,
        decision_id: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        request_hash = content_hash({"decision_id": decision_id, **body})
        async with self.service.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation="action_runs.create",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if claim.replay:
                return int(claim.record.response_status or 202), dict(
                    claim.record.response_payload or {}
                )
            decision = await self.service._not_found(
                repository.get_decision(decision_id), "DECISION"
            )
            await self.service._require_current_decision(session, organization_id, decision)
            if (
                decision.version != body["decision_version"]
                or decision.decision_hash != body["decision_hash"]
            ):
                raise ApiProblem(
                    code="DECISION_VERSION_HASH_MISMATCH",
                    message=(
                        "Action execution must bind the exact selected Decision version and hash."
                    ),
                    status_code=409,
                    next_action="refresh_decision",
                )
            selection = decision.payload.get("selection")
            if (
                not isinstance(selection, dict)
                or selection.get("solution_plan_id") != body["solution_plan_id"]
            ):
                raise ApiProblem(
                    code="PLAN_SELECTION_REQUIRED",
                    message="Select this exact action plan before starting execution.",
                    status_code=409,
                    next_action="select_plan",
                )
            request = await self.service._not_found(
                repository.get_purchase_request(decision.purchase_request_id),
                "DECISION_REQUEST",
            )
            view = project_decision_room(
                request=request,
                decision=decision,
                fixtures=self.service._fixture_bundle(),
                roles=roles,
                party=party,
                intent=None,
                approval=None,
                handoff=None,
                superseded_by=None,
            )
            selected = view["selected_action_plan"]
            if not isinstance(selected, dict):
                raise ApiProblem(
                    code="PLAN_SELECTION_REQUIRED",
                    message="The selected action plan is unavailable.",
                    status_code=409,
                )
            decision_scope = [decision.id]
            if decision.supersedes_id is not None:
                decision_scope.append(decision.supersedes_id)
            evaluation_payload_hash = decision.payload.get("evaluation_payload_hash")
            if not isinstance(evaluation_payload_hash, str):
                raise ApiProblem(
                    code="EVALUATION_BINDING_UNAVAILABLE",
                    message="The selected Decision has no frozen evaluation binding.",
                    status_code=409,
                    next_action="refresh_decision",
                )
            solution_plan_record = (
                await session.execute(
                    select(EvaluationSolutionPlan)
                    .join(
                        EvaluationRun,
                        EvaluationRun.id == EvaluationSolutionPlan.evaluation_run_id,
                    )
                    .where(
                        EvaluationSolutionPlan.organization_id == organization_id,
                        EvaluationSolutionPlan.solution_plan_id == body["solution_plan_id"],
                        EvaluationRun.organization_id == organization_id,
                        EvaluationRun.decision_id.in_(decision_scope),
                        EvaluationRun.evaluation_payload_hash == evaluation_payload_hash,
                    )
                    .order_by(
                        (EvaluationRun.decision_id == decision.id).desc(),
                        EvaluationRun.evaluated_at.desc(),
                        EvaluationSolutionPlan.id,
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if solution_plan_record is None:
                raise ApiProblem(
                    code="SOLUTION_PLAN_RECORD_UNAVAILABLE",
                    message="The frozen Solution Plan cannot be loaded for execution.",
                    status_code=409,
                    next_action="refresh_decision",
                )
            action_run_id = new_id("ar")
            now = datetime.now(UTC)
            response = {
                "schema_version": "1.0.0",
                "action_run_id": action_run_id,
                "workflow_id": action_run_id,
                "decision_id": decision.id,
                "decision_version": decision.version,
                "decision_hash": decision.decision_hash,
                "selection_id": selection["selection_id"],
                "solution_plan_id": solution_plan_record.solution_plan_id,
                "action_type": solution_plan_record.action,
                "status": "WAITING_FOR_HUMAN",
                "owner_role": "DECISION_MAKER",
                "current_step_id": "step_review",
                "last_successful_checkpoint_id": None,
                "blocking_task": None,
                "recovery_action": None,
                "execution_steps": selected["execution_steps"],
                "result_artifacts": [],
                "payment_handoff": view["payment_handoff"],
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "completed_at": None,
            }
            await repository.add_action_run(
                ActionRun(
                    id=action_run_id,
                    organization_id=organization_id,
                    decision_id=decision.id,
                    solution_plan_record_id=solution_plan_record.id,
                    solution_plan_id=solution_plan_record.solution_plan_id,
                    purchase_intent_id=None,
                    action=solution_plan_record.action,
                    status="WAITING_FOR_HUMAN",
                    current_checkpoint="step_review",
                    last_successful_checkpoint=None,
                    owner_role="DECISION_MAKER",
                    blocking_task=None,
                    recovery_action=None,
                    retryable=False,
                    safe_to_leave=True,
                    started_at=now,
                    completed_at=None,
                    run_hash=content_hash(response),
                    supersedes_id=None,
                    payload=response,
                )
            )
            await repository.complete_idempotency(
                claim.record,
                response_status=202,
                response_payload=response,
                response_reference=action_run_id,
            )
            return 202, response

    async def get_action_run(self, *, organization_id: str, action_run_id: str) -> dict[str, Any]:
        async with self.service.database.transaction(organization_id) as session:
            repository = WorkflowRepository(session, organization_id)
            snapshot = await self.service._not_found(
                repository.get_action_run_snapshot(action_run_id), "ACTION_RUN"
            )
            projection = snapshot.action_run.payload
            if not isinstance(projection, dict):
                raise ApiProblem(
                    code="ACTION_RUN_PROJECTION_UNAVAILABLE",
                    message="The durable action checkpoint cannot be projected.",
                    status_code=409,
                )
            return deepcopy(projection)

    async def _request_projection(
        self,
        session: Any,
        organization_id: str,
        request: PurchaseRequest,
        roles: frozenset[str],
        party: str | None,
    ) -> dict[str, Any]:
        decision = (
            await session.execute(
                select(DecisionRecord)
                .where(
                    DecisionRecord.organization_id == organization_id,
                    DecisionRecord.purchase_request_id == request.id,
                )
                .order_by(DecisionRecord.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        resolved_role = actor_role(roles, party)
        stage = (
            "ACTION"
            if decision and isinstance(decision.payload.get("selection"), dict)
            else ("OPTIONS" if decision is not None else "NEED")
        )
        deadline_value = request.payload.get("deadline")
        evaluation = self.service._request_evaluation_metadata(request)
        return {
            "id": request.id,
            "intent": request.intent,
            "status": request.status,
            "visibility": request.visibility,
            "owner_role": resolved_role.value,
            "deadline": deadline_value,
            "current_stage": stage,
            "blocker": (
                "Choose the supported demo scenario before running evaluation."
                if evaluation["evaluation_mode"] == "SCENARIO_SELECTION_REQUIRED"
                else None
            ),
            "last_checkpoint": "Decision ready" if decision is not None else "Request saved",
            "current_decision_version": decision.version if decision is not None else None,
            **evaluation,
            "href": (
                f"/decisions/{request.id}/versions/{decision.version}/{stage.lower()}"
                if decision is not None
                else f"/decisions/{request.id}/versions/1/need"
            ),
        }

    @staticmethod
    def _feedback_response(
        legacy: dict[str, Any], solution_plan_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "id": legacy["id"],
            "request_id": legacy["request_id"],
            "solution_plan_id": solution_plan_id,
            "action": body["action"],
            "reason": legacy["reason"],
            "engagement_id": legacy.get("engagement_id"),
            "proposal_id": legacy.get("proposal_id"),
            "contact_details_revealed": False,
            "ranking_effect": False,
        }
