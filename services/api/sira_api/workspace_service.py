"""Chat-first workspace service with explicit agent and catalogue boundaries."""

from __future__ import annotations

import json
from datetime import UTC
from typing import Any
from uuid import uuid4

from openai import AuthenticationError, RateLimitError
from pydantic import ValidationError
from sqlalchemy import select
from sira_agents.commerce_tools import SEIL_TOOL_NAMES, SIRA_TOOL_NAMES, commerce_tool_registry
from sira_agents.mission_models import MissionTurnOutput
from sira_agents.runtime import (
    AgentRole,
    AgentRunContext,
    AgentRunRequest,
    AuthorityMode,
    OpenAIAgentsRuntime,
)
from sira_agents.workspace_tools import workspace_tool_registry

from persistence.database import Database
from persistence.mission_repository import MissionRepository, MissionSnapshot
from persistence.models import Organization, PurchaseRequest, WorkflowRun
from persistence.repositories import RecordNotFound

from .errors import ApiProblem
from .fixtures import DemoFixtureBundle
from .workspace_schemas import WorkspaceChatCreate


class WorkspaceService:
    _REAL_PRODUCT_EVIDENCE: dict[str, dict[str, Any]] = {
        "product_fixture_d": {
            "name": "Fathom",
            "seller": "Fathom",
            "edition": "Team",
            "price": "USD 19",
            "billing_unit": "seat_month",
            "summary": "Meeting recording, transcription, summaries, action items, and team CRM sync.",
            "claims": [
                "Team plans include shared recordings and AI summaries.",
                "CRM sync supports HubSpot, Salesforce, and Close.",
                "A 14-day Team trial is publicly offered.",
            ],
            "integrations": ["hubspot", "salesforce", "close", "zoom", "google_meet", "teams"],
            "website": "https://fathom.video/pricing",
            "logo": "/products/fathom.svg",
            "evidence_freshness": "Official pricing checked 5 Aug 2026",
            "source_refs": [
                {"title": "Fathom pricing", "url": "https://fathom.video/pricing", "authority": "VENDOR"},
                {"title": "Fathom for teams", "url": "https://fathom.video/for/teams", "authority": "VENDOR"},
            ],
        },
        "product_fixture_c": {
            "name": "Fireflies.ai",
            "seller": "Fireflies.ai",
            "edition": "Business",
            "price": "USD 29",
            "billing_unit": "seat_month_annual",
            "summary": "AI meeting notes, action items, search, coaching, and CRM synchronization.",
            "claims": [
                "Business includes HubSpot and Salesforce CRM sync.",
                "Business includes AI coaching and team interaction metrics.",
                "Meeting notes and action items are available across paid plans.",
            ],
            "integrations": ["hubspot", "salesforce", "slack", "zapier"],
            "website": "https://fireflies.ai/pricing",
            "logo": "/products/fireflies.svg",
            "evidence_freshness": "Official product material checked 5 Aug 2026",
            "source_refs": [
                {"title": "Fireflies meeting transcription guide", "url": "https://fireflies.ai/blog/meeting-transcription-software/", "authority": "VENDOR"}
            ],
        },
        "product_fixture_b": {
            "name": "Otter.ai",
            "seller": "Otter.ai",
            "edition": "Enterprise",
            "price": "Quote required",
            "billing_unit": "workspace",
            "summary": "Live transcription, meeting summaries, action items, and enterprise CRM autofill.",
            "claims": [
                "HubSpot can be installed for an entire Enterprise workspace.",
                "Admins can map meeting insights to HubSpot custom fields.",
                "CRM Autofill can sync meeting conversations into HubSpot.",
            ],
            "integrations": ["hubspot", "zoom", "google_meet", "teams"],
            "website": "https://otter.ai/pricing",
            "logo": "/products/otter.svg",
            "evidence_freshness": "Official help center checked 5 Aug 2026",
            "source_refs": [
                {"title": "Otter HubSpot for Enterprise", "url": "https://help.otter.ai/hc/en-us/articles/40426498007959-Otter-HubSpot-for-Enterprise", "authority": "VENDOR"}
            ],
        },
        "product_fixture_a": {
            "name": "tl;dv",
            "seller": "tl;dv",
            "edition": "Business",
            "price": "Verify current price",
            "billing_unit": "seat_month",
            "summary": "Meeting recording, multilingual transcription, AI notes, and sales workflow integrations.",
            "claims": [
                "Supports Zoom, Google Meet, and Microsoft Teams.",
                "Offers CRM-oriented workflows and HubSpot integration.",
                "Pricing and plan eligibility must be revalidated before purchase.",
            ],
            "integrations": ["hubspot", "zoom", "google_meet", "teams"],
            "website": "https://tldv.io/pricing/",
            "logo": "/products/tldv.svg",
            "evidence_freshness": "Requires live price revalidation",
            "source_refs": [
                {"title": "tl;dv pricing", "url": "https://tldv.io/pricing/", "authority": "VENDOR"}
            ],
        },
    }
    def __init__(
        self,
        fixtures: DemoFixtureBundle | None,
        *,
        api_key: str,
        model: str,
        workflow_service: object | None = None,
        seller_evidence_service: object | None = None,
        database: Database | None = None,
        senso_providers: dict[str, object] | None = None,
        senso_error: str | None = None,
    ) -> None:
        self.fixtures = fixtures
        self.api_key = api_key
        self.workflow_service = workflow_service
        self.seller_evidence_service = seller_evidence_service
        self.database = database
        self.senso_providers = senso_providers or {}
        self.senso_error = senso_error
        tools = {**workspace_tool_registry(), **commerce_tool_registry()}
        self.runtime = OpenAIAgentsRuntime(model=model, tools=tools)

    def agent_services(self) -> dict[str, object]:
        services: dict[str, object] = {"workspace_catalog": self}
        if self.workflow_service is not None:
            services["workflow_service"] = self.workflow_service
        if self.seller_evidence_service is not None:
            services["seller_evidence_service"] = self.seller_evidence_service
        services.update(self.senso_providers)
        return services

    def senso_status(self) -> tuple[bool, str]:
        if {"senso_buyer", "senso_seller"}.issubset(self.senso_providers):
            return True, "Buyer and seller folder scopes verified"
        return False, self.senso_error or "Senso is not configured"

    def catalog(self) -> list[dict[str, Any]]:
        if self.fixtures is None:
            return []
        products: list[dict[str, Any]] = []
        for candidate_id, pack in self.fixtures.packs.items():
            identity = pack["identity"]
            offer = self.fixtures.offers[candidate_id]
            integrations: list[str] = []
            for fact in pack.get("facts", []):
                if fact.get("field") == "product.native_integrations":
                    integrations = [str(item) for item in fact.get("value", [])]
            claims = [
                str(claim["display_text"])
                for claim in pack.get("claims", [])
                if claim.get("evidence_visibility") == "public"
            ][:4]
            angles = pack.get("positioning_angles", [])
            summary = str(angles[0]["text"]) if angles else "Published seller Product Evidence."
            product = {
                    "id": str(pack["product_id"]),
                    "name": str(identity["product_name"]),
                    "seller": str(identity["seller_name"]),
                    "edition": str(identity.get("edition", "")),
                    "price": f"{offer['currency']} {offer['amount']}",
                    "billing_unit": str(offer["billing_unit"]),
                    "status": str(pack["status"]),
                    "summary": summary,
                    "claims": claims,
                    "integrations": integrations,
                }
            product.update(self._REAL_PRODUCT_EVIDENCE.get(candidate_id, {}))
            products.append(product)
        return products

    def product(self, product_id: str) -> dict[str, Any] | None:
        return next((item for item in self.catalog() if item["id"] == product_id), None)

    async def chat(
        self, body: WorkspaceChatCreate, *, run_context: AgentRunContext
    ) -> dict[str, Any]:
        if not self.api_key:
            raise ApiProblem(
                code="AGENT_PROVIDER_NOT_CONFIGURED",
                message="The workspace agent is not configured on the server.",
                status_code=503,
                retryable=False,
                next_action="configure_openai_api_key",
            )
        mission_id, model_context = await self._prepare_mission(
            body=body,
            run_context=run_context,
        )
        if self._is_lightweight_message(body.message):
            answer = MissionTurnOutput(
                message=(
                    "Hey. Tell me what you want to buy, compare, renew, or evaluate, and I’ll take it from there."
                    if body.mode == "sira"
                    else "Hey. Tell me which product, buyer question, or evidence gap you want to work on."
                ),
                mission_state="ORIENTING",
                stop_reason="LIGHTWEIGHT_REPLY",
            )
            persisted = await self._persist_turn(
                mission_id=mission_id,
                answer=answer,
                run_context=run_context,
                tool_calls=(),
                proposals=(),
                turn_key=run_context.request_id,
            )
            return {
                "conversation_id": mission_id,
                "mission_id": mission_id,
                "message": answer.message,
                "follow_up_required": False,
                "panel": None,
                "products": [],
                "tool_calls": [],
                "proposals": [],
                "mission": persisted["mission"],
                "events": persisted["events"],
                "artifacts": persisted["artifacts"],
                "attention": None,
                "advisory_only": False,
            }
        instructions = self._root_agent_instructions(body.mode)
        try:
            result = await self.runtime.run(
                AgentRunRequest(
                    role=AgentRole.SIRA if body.mode == "sira" else AgentRole.SEIL,
                    instructions=instructions,
                    prompt=body.message,
                    model_context=model_context,
                    run_context=run_context,
                    allowed_tools=SIRA_TOOL_NAMES if body.mode == "sira" else SEIL_TOOL_NAMES,
                    output_type=MissionTurnOutput,
                    authority_mode=AuthorityMode.MISSION_OPERATOR,
                )
            )
            answer = self._coerce_answer(result.output)
        except AuthenticationError as error:
            raise ApiProblem(
                code="AGENT_PROVIDER_AUTHENTICATION_FAILED",
                message=(
                    "The server's OpenAI API key is invalid. Replace "
                    "SIRA_OPENAI_API_KEY and restart the API."
                ),
                status_code=503,
                retryable=False,
                next_action="replace_openai_api_key",
            ) from error
        except RateLimitError as error:
            raise ApiProblem(
                code="AGENT_PROVIDER_RATE_LIMITED",
                message="The workspace agent is rate limited. Try again shortly.",
                status_code=503,
                retryable=True,
                next_action="retry_later",
            ) from error
        except (ValidationError, ValueError, TypeError, json.JSONDecodeError) as error:
            raise ApiProblem(
                code="AGENT_RESPONSE_INVALID",
                message="The agent returned an invalid workspace response.",
                status_code=502,
                retryable=True,
                next_action="retry_message",
            ) from error
        except Exception as error:
            raise ApiProblem(
                code="AGENT_PROVIDER_UNAVAILABLE",
                message="The workspace agent is temporarily unavailable.",
                status_code=503,
                retryable=True,
                next_action="retry_later",
            ) from error
        persisted = await self._persist_turn(
            mission_id=mission_id,
            answer=answer,
            run_context=run_context,
            tool_calls=tuple(dict.fromkeys(result.tool_calls)),
            proposals=result.proposals,
            turn_key=run_context.request_id,
        )
        all_tool_calls = list(result.tool_calls)
        all_proposals = list(result.proposals)
        product_ids = set(answer.show_product_ids)
        for continuation_index in range(2):
            if not answer.continue_autonomously or answer.attention is not None:
                break
            try:
                continuation = await self.runtime.run(
                    AgentRunRequest(
                        role=AgentRole.SIRA if body.mode == "sira" else AgentRole.SEIL,
                        instructions=instructions,
                        prompt=(
                            "Continue the mission with its next useful reversible step. Stop when "
                            "human attention or protected authority is required."
                        ),
                        model_context=await self._mission_context(
                            mission_id=mission_id, run_context=run_context
                        ),
                        run_context=run_context,
                        allowed_tools=(SIRA_TOOL_NAMES if body.mode == "sira" else SEIL_TOOL_NAMES),
                        output_type=MissionTurnOutput,
                        authority_mode=AuthorityMode.MISSION_OPERATOR,
                    )
                )
                answer = self._coerce_answer(continuation.output)
                persisted = await self._persist_turn(
                    mission_id=mission_id,
                    answer=answer,
                    run_context=run_context,
                    tool_calls=tuple(dict.fromkeys(continuation.tool_calls)),
                    proposals=continuation.proposals,
                    turn_key=(
                        f"{run_context.request_id or uuid4().hex}:continuation:{continuation_index}"
                    ),
                )
                all_tool_calls.extend(continuation.tool_calls)
                all_proposals.extend(continuation.proposals)
                product_ids.update(answer.show_product_ids)
            except Exception:
                break
        visible_products = [product for product in self.catalog() if product["id"] in product_ids]
        panel = "catalog" if visible_products else None
        return {
            "conversation_id": mission_id,
            "mission_id": mission_id,
            "message": answer.message,
            "follow_up_required": answer.attention is not None,
            "panel": panel,
            "products": visible_products,
            "tool_calls": list(dict.fromkeys(all_tool_calls)),
            "proposals": all_proposals,
            "mission": persisted["mission"],
            "events": persisted["events"],
            "artifacts": persisted["artifacts"],
            "attention": answer.attention.model_dump(mode="json") if answer.attention else None,
            "advisory_only": False,
        }

    @staticmethod
    def _coerce_answer(raw: object) -> MissionTurnOutput:
        if isinstance(raw, str):
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.removeprefix("```json").removeprefix("```")
                cleaned = cleaned.removesuffix("```").strip()
            raw = json.loads(cleaned)
        return MissionTurnOutput.model_validate(raw)

    @staticmethod
    def _is_lightweight_message(message: str) -> bool:
        normalized = " ".join(message.casefold().strip().split()).rstrip("!?.")
        return normalized in {"hi", "hey", "hello", "yo", "good morning", "good evening"}

    @staticmethod
    def _root_agent_instructions(mode: str) -> str:
        shared = (
            "You are the persistent root commerce agent for one mission. Infer intent, maintain a "
            "plan and world model, use tools before asking the user for facts that can be found, "
            "and ask only when a material ambiguity, authority boundary, credential, or choice "
            "blocks useful work. A greeting gets a short greeting, not a fabricated project plan. "
            "Produce typed events and inspectable artifacts for meaningful work. Claims must name "
            "their authority and sources; label inference as inference. Delegate only bounded "
            "tasks with an explicit budget. You may evaluate, compare, rank, and recommend. "
            "You may draft "
            "protected actions, but you cannot grant yourself capabilities, approve, charge, send, "
            "publish, sign, or activate. Those effects require a server-issued grant and exact "
            "human authority. Do not expose secrets or raw private evidence."
        )
        if mode == "sira":
            return (
                f"{shared} You are SIRA, operating for the buyer. Search company evidence and the "
                "catalogue, design reproducible evaluations when evidence is insufficient, build "
                "candidate and comparison artifacts, and advance to a purchase proposal only when "
                "the evidence supports it. Product IDs shown to the UI must come from tools."
            )
        return (
            f"{shared} You are SEIL, operating for the seller. Build and improve evidence-backed "
            "product twins, resolve claim gaps, and prepare reviewable publication proposals. "
            "Never invent product claims or expose seller-private sources to buyers."
        )

    async def _prepare_mission(
        self,
        *,
        body: WorkspaceChatCreate,
        run_context: AgentRunContext,
    ) -> tuple[str, dict[str, Any]]:
        requested_id = body.mission_id or body.conversation_id
        mission_id = requested_id if requested_id and requested_id.startswith("msn_") else None
        if self.database is None:
            mission_id = mission_id or f"msn_{uuid4().hex}"
            return mission_id, {
                "mission": {
                    "id": mission_id,
                    "goal": body.message,
                    "state": "ORIENTING",
                    "version": 1,
                    "plan": {"steps": []},
                    "world_model": {"claims": [], "unknowns": [], "contradictions": []},
                },
                "recent_events": [
                    {"type": f"{item.role}.message", "payload": {"message": item.content}}
                    for item in body.history[-12:]
                ],
            }
        async with self.database.transaction(run_context.organization_id) as session:
            organization = await session.get(Organization, run_context.organization_id)
            if organization is None and run_context.organization_id.startswith(
                ("org_guest_", "org_user_")
            ):
                session.add(
                    Organization(
                        id=run_context.organization_id,
                        name=(
                            "Private guest workspace"
                            if run_context.organization_id.startswith("org_guest_")
                            else "Private Firebase workspace"
                        ),
                        version=1,
                    )
                )
                await session.flush()
            repository = MissionRepository(session, run_context.organization_id)
            if mission_id is None:
                mission_id = f"msn_{uuid4().hex}"
                mission = await repository.create(
                    mission_id=mission_id,
                    actor_id=run_context.actor_id,
                    mode=body.mode.upper(),
                    goal=body.message,
                    budget={
                        "model_turns_remaining": 16,
                        "worker_tasks_remaining": 8,
                        "experiments_remaining": 4,
                    },
                )
            else:
                try:
                    mission = await repository.get_for_actor(
                        mission_id, run_context.actor_id, lock=True
                    )
                except RecordNotFound:
                    mission = await repository.create(
                        mission_id=mission_id,
                        actor_id=run_context.actor_id,
                        mode=body.mode.upper(),
                        goal=body.message,
                        budget={
                            "model_turns_remaining": 16,
                            "worker_tasks_remaining": 8,
                            "experiments_remaining": 4,
                        },
                    )
                if mission.mode != body.mode.upper():
                    raise PermissionError("mission mode does not match this workspace")
            mission.state = (
                "ORIENTING" if self._is_lightweight_message(body.message) else "PLANNING"
            )
            await repository.append_event(
                mission,
                event_type="user.message",
                event_key=f"user-message:{mission.id}:{run_context.request_id or uuid4().hex}",
                actor_type="USER",
                actor_id=run_context.actor_id,
                payload={"message": body.message},
            )
            if not self._is_lightweight_message(body.message):
                await repository.append_event(
                    mission,
                    event_type="agent.accepted",
                    event_key=f"agent-accepted:{mission.id}:{run_context.request_id or uuid4().hex}",
                    actor_type="SYSTEM",
                    actor_id="mission-runtime",
                    payload={
                        "summary": "Mission accepted; choosing the next evidence-backed action",
                        "details": {"safe_to_leave": True, "checkpoint": "request_received"},
                    },
                )
            snapshot = await repository.snapshot(mission)
            return mission.id, snapshot.model_context()

    async def _mission_context(
        self, *, mission_id: str, run_context: AgentRunContext
    ) -> dict[str, Any]:
        if self.database is None:
            return {"mission": {"id": mission_id}}
        async with self.database.transaction(run_context.organization_id) as session:
            repository = MissionRepository(session, run_context.organization_id)
            mission = await repository.get_for_actor(mission_id, run_context.actor_id)
            return (await repository.snapshot(mission)).model_context()

    async def conversations(
        self, *, run_context: AgentRunContext, mode: str
    ) -> list[dict[str, Any]]:
        if self.database is None:
            return []
        async with self.database.transaction(run_context.organization_id) as session:
            repository = MissionRepository(session, run_context.organization_id)
            records = await repository.list_for_actor(run_context.actor_id, mode=mode.upper())
            snapshots = [await repository.snapshot(record) for record in records]
        results: list[dict[str, Any]] = []
        for snapshot in snapshots:
            record = snapshot.mission
            messages = self._messages_from_snapshot(snapshot)
            results.append(
                {
                    "id": record.id,
                    "mode": mode,
                    "title": record.goal[:46] or "New mission",
                    "messages": messages,
                    "updated_at": record.updated_at.astimezone(UTC).isoformat(),
                    **self._snapshot_view(snapshot),
                }
            )
        return results

    async def mission(
        self,
        *,
        run_context: AgentRunContext,
        mission_id: str,
    ) -> dict[str, Any]:
        if self.database is None:
            raise ApiProblem(
                code="MISSION_STORE_UNAVAILABLE",
                message="Mission persistence is unavailable.",
                status_code=503,
            )
        async with self.database.transaction(run_context.organization_id) as session:
            repository = MissionRepository(session, run_context.organization_id)
            try:
                mission = await repository.get_for_actor(mission_id, run_context.actor_id)
            except RecordNotFound:
                raise ApiProblem(
                    code="MISSION_NOT_FOUND",
                    message="That mission is unavailable in this workspace.",
                    status_code=404,
                ) from None
            snapshot = await repository.snapshot(mission)
        response = self._snapshot_view(snapshot)
        response["handoffs"] = await self._mission_handoffs(
            run_context.organization_id, mission_id
        )
        return response

    async def _mission_handoffs(
        self, organization_id: str, mission_id: str
    ) -> list[dict[str, Any]]:
        if self.database is None:
            return []
        async with self.database.transaction(organization_id) as session:
            requests = tuple(
                (
                    await session.execute(
                        select(PurchaseRequest).where(
                            PurchaseRequest.organization_id == organization_id,
                            PurchaseRequest.payload["mission_id"].as_string() == mission_id,
                        )
                    )
                )
                .scalars()
                .all()
            )
            if not requests:
                return []
            request_ids = [item.id for item in requests]
            workflows = tuple(
                (
                    await session.execute(
                        select(WorkflowRun).where(
                            WorkflowRun.organization_id == organization_id,
                            WorkflowRun.aggregate_id.in_(request_ids),
                        )
                    )
                )
                .scalars()
                .all()
            )
        workflow_by_request = {item.aggregate_id: item for item in workflows}
        return [
            {
                "kind": "decision",
                "request_id": item.id,
                "status": item.status,
                "workflow": (
                    {
                        "id": workflow_by_request[item.id].id,
                        "operation": workflow_by_request[item.id].operation,
                        "status": workflow_by_request[item.id].status,
                        "safe_error_code": workflow_by_request[item.id].safe_error_code,
                    }
                    if item.id in workflow_by_request
                    else None
                ),
            }
            for item in requests
        ]

    async def _persist_turn(
        self,
        *,
        mission_id: str,
        answer: MissionTurnOutput,
        run_context: AgentRunContext,
        tool_calls: tuple[str, ...],
        proposals: tuple[Any, ...],
        turn_key: str | None = None,
    ) -> dict[str, Any]:
        if self.database is None:
            return {
                "mission": {
                    "id": mission_id,
                    "mode": "sira",
                    "goal": answer.message,
                    "state": answer.mission_state,
                    "version": 1,
                    "plan": [item.model_dump(mode="json") for item in answer.plan],
                    "stop_reason": answer.stop_reason,
                },
                "events": [
                    {
                        "id": f"ephemeral-event-{index}",
                        "sequence": index,
                        "type": item.event_type,
                        "summary": item.summary,
                        "details": item.details,
                        "occurred_at": None,
                    }
                    for index, item in enumerate(answer.events, start=1)
                ],
                "artifacts": [
                    {
                        "id": f"ephemeral-artifact-{index}",
                        **item.model_dump(mode="json"),
                        "status": "READY",
                    }
                    for index, item in enumerate(answer.artifacts, start=1)
                ],
            }
        async with self.database.transaction(run_context.organization_id) as session:
            repository = MissionRepository(session, run_context.organization_id)
            mission = await repository.get_for_actor(mission_id, run_context.actor_id, lock=True)
            mission.state = answer.mission_state
            mission.version += 1
            mission.plan = {
                "steps": [item.model_dump(mode="json") for item in answer.plan],
                "updated_by": "root_agent",
            }
            mission.world_model = {
                "claims": [item.model_dump(mode="json") for item in answer.claims],
                "unknowns": [],
                "contradictions": [],
            }
            mission.stop_reason = answer.stop_reason
            remaining_turns = int(mission.budget.get("model_turns_remaining", 1))
            mission.budget = {
                **mission.budget,
                "model_turns_remaining": max(0, remaining_turns - 1),
            }
            event_turn_key = turn_key or uuid4().hex
            await repository.append_event(
                mission,
                event_type="assistant.message",
                event_key=f"assistant-message:{mission.id}:{event_turn_key}",
                actor_type="ROOT_AGENT",
                actor_id="sira-root-agent",
                payload={
                    "message": answer.message,
                    "tool_calls": list(tool_calls),
                    "proposals": list(proposals),
                },
            )
            for index, tool_name in enumerate(tool_calls):
                await repository.append_event(
                    mission,
                    event_type="agent.tool.completed",
                    event_key=f"tool-completed:{mission.id}:{event_turn_key}:{index}:{tool_name}",
                    actor_type="SYSTEM",
                    actor_id="mission-runtime",
                    payload={
                        "summary": f"Used {tool_name.replace('_', ' ')}",
                        "details": {"tool": tool_name, "verified": True},
                    },
                )
            for index, event in enumerate(answer.events):
                await repository.append_event(
                    mission,
                    event_type=event.event_type,
                    event_key=f"agent-event:{mission.id}:{event_turn_key}:{index}",
                    actor_type="ROOT_AGENT",
                    actor_id="sira-root-agent",
                    payload={"summary": event.summary, "details": event.details},
                )
            for task in answer.tasks:
                await repository.add_task(
                    mission,
                    kind=task.kind,
                    title=task.title,
                    owner_type=task.owner_type,
                    assigned_role=task.assigned_role,
                    input_payload=task.input,
                    budget=task.budget,
                )
            persisted_artifacts = []
            for artifact in answer.artifacts:
                authority = artifact.authority
                if authority in {"OBSERVED", "VERIFIED"} and not artifact.source_refs:
                    authority = "INFERRED"
                persisted_artifacts.append(
                    await repository.add_artifact(
                        mission,
                        kind=artifact.kind,
                        title=artifact.title,
                        authority=authority,
                        payload=artifact.payload,
                        source_refs=artifact.source_refs,
                        created_by="sira-root-agent",
                    )
                )
            await repository.checkpoint(mission)
            snapshot = await repository.snapshot(mission)
            response = self._snapshot_view(snapshot)
            response["events"] = response["events"][
                -(len(answer.events) + len(tool_calls) + 1) :
            ]
            response["artifacts"] = [self._artifact_view(item) for item in persisted_artifacts]
            return response

    @staticmethod
    def _messages_from_snapshot(snapshot: MissionSnapshot) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for event in snapshot.events:
            if event.event_type not in {"user.message", "assistant.message"}:
                continue
            role = "user" if event.event_type == "user.message" else "assistant"
            messages.append(
                {
                    "role": role,
                    "content": str(event.payload.get("message", "")),
                    "tool_calls": event.payload.get("tool_calls", []),
                    "proposals": event.payload.get("proposals", []),
                }
            )
        return messages

    @staticmethod
    def _artifact_view(artifact: Any) -> dict[str, Any]:
        return {
            "id": artifact.id,
            "kind": artifact.kind,
            "title": artifact.title,
            "status": artifact.status,
            "authority": artifact.authority,
            "payload": artifact.payload,
            "source_refs": artifact.source_refs,
        }

    def _snapshot_view(self, snapshot: MissionSnapshot) -> dict[str, Any]:
        mission = snapshot.mission
        return {
            "mission": {
                "id": mission.id,
                "mode": mission.mode.lower(),
                "goal": mission.goal,
                "state": mission.state,
                "version": mission.version,
                "plan": mission.plan.get("steps", []),
                "stop_reason": mission.stop_reason,
            },
            "events": [
                {
                    "id": event.id,
                    "sequence": event.sequence,
                    "type": event.event_type,
                    "summary": str(
                        event.payload.get("summary")
                        or event.payload.get("message")
                        or event.event_type
                    ),
                    "details": event.payload.get("details", {}),
                    "occurred_at": event.occurred_at.astimezone(UTC).isoformat(),
                    "verified": event.actor_type == "SYSTEM",
                }
                for event in snapshot.events
            ],
            "artifacts": [self._artifact_view(item) for item in snapshot.artifacts],
            "open_tasks": [
                {
                    "id": task.id,
                    "kind": task.kind,
                    "title": task.title,
                    "status": task.status,
                    "owner_type": task.owner_type,
                    "assigned_role": task.assigned_role,
                    "budget": task.budget,
                }
                for task in snapshot.tasks
                if task.status not in {"COMPLETED", "CANCELLED"}
            ],
        }
