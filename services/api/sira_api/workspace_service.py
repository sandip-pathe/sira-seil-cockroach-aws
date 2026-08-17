"""Chat-first workspace service with explicit agent and catalogue boundaries."""

from __future__ import annotations

from datetime import UTC
from typing import Any, ClassVar
from uuid import uuid4

from sira_agents.kernel_models import Party, Principal
from sira_agents.runtime import AgentRunContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.database import Database
from persistence.mission_repository import MissionRepository, MissionSnapshot
from persistence.models import Organization, PurchaseRequest, WorkflowRun
from persistence.repositories import RecordNotFound
from sira_api.cognitive_engine import RunEngine, TurnCommand, TurnResult

from .errors import ApiProblem
from .fixtures import DemoFixtureBundle
from .workspace_schemas import WorkspaceChatCreate


class WorkspaceService:
    _SELLER_LISTING_IDS: ClassVar[frozenset[str]] = frozenset(
        {"product_fixture_a", "product_fixture_b"}
    )
    _REAL_PRODUCT_EVIDENCE: ClassVar[dict[str, dict[str, Any]]] = {
        "product_fixture_d": {
            "name": "Fathom",
            "seller": "Fathom",
            "edition": "Team",
            "price": "USD 19",
            "billing_unit": "seat_month",
            "summary": (
                "Meeting recording, transcription, summaries, action items, and team CRM sync."
            ),
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
                {
                    "title": "Fathom pricing",
                    "url": "https://fathom.video/pricing",
                    "authority": "PUBLIC_WEB",
                },
                {
                    "title": "Fathom for teams",
                    "url": "https://fathom.video/for/teams",
                    "authority": "PUBLIC_WEB",
                },
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
                {
                    "title": "Fireflies meeting transcription guide",
                    "url": "https://fireflies.ai/blog/meeting-transcription-software/",
                    "authority": "PUBLIC_WEB",
                }
            ],
        },
        "product_fixture_b": {
            "name": "Otter.ai",
            "seller": "Otter.ai",
            "edition": "Enterprise",
            "price": "Quote required",
            "billing_unit": "workspace",
            "summary": (
                "Live transcription, meeting summaries, action items, and enterprise CRM autofill."
            ),
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
                {
                    "title": "Otter HubSpot for Enterprise",
                    "url": "https://help.otter.ai/hc/en-us/articles/40426498007959-Otter-HubSpot-for-Enterprise",
                    "authority": "VENDOR",
                }
            ],
        },
        "product_fixture_a": {
            "name": "tl;dv",
            "seller": "tl;dv",
            "edition": "Business",
            "price": "Verify current price",
            "billing_unit": "seat_month",
            "summary": (
                "Meeting recording, multilingual transcription, AI notes, and sales "
                "workflow integrations."
            ),
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
        workflow_service: object | None = None,
        seller_evidence_service: object | None = None,
        database: Database | None = None,
        cognitive_engine: RunEngine | None = None,
    ) -> None:
        self.fixtures = fixtures
        self.workflow_service = workflow_service
        self.seller_evidence_service = seller_evidence_service
        self.database = database
        self.cognitive_engine = cognitive_engine
        self.runtime_ready = cognitive_engine is not None

    def agent_services(self) -> dict[str, object]:
        services: dict[str, object] = {"workspace_catalog": self}
        if self.workflow_service is not None:
            services["workflow_service"] = self.workflow_service
        if self.seller_evidence_service is not None:
            services["seller_evidence_service"] = self.seller_evidence_service
        return services

    def capabilities(self) -> list[dict[str, str | None]]:
        return [
            {
                "id": "sira-agent",
                "label": "SIRA reasoning and tools",
                "status": "ready" if self.runtime_ready else "misconfigured",
                "reason_code": "READY" if self.runtime_ready else "AGENT_RUNTIME_MISSING",
                "remediation": None if self.runtime_ready else "Configure the agent runtime",
            },
            {
                "id": "seil-agent",
                "label": "SEIL reasoning and seller evidence",
                "status": "ready" if self.runtime_ready else "misconfigured",
                "reason_code": "READY" if self.runtime_ready else "AGENT_RUNTIME_MISSING",
                "remediation": None if self.runtime_ready else "Configure the agent runtime",
            },
            {
                "id": "product-evidence",
                "label": "Product Evidence lifecycle",
                "status": "ready" if self.seller_evidence_service and self.database else "offline",
                "reason_code": "READY"
                if self.seller_evidence_service and self.database
                else "PRODUCT_EVIDENCE_OFFLINE",
                "remediation": None
                if self.seller_evidence_service and self.database
                else "Start the database and API",
            },
        ]

    def catalog(self) -> list[dict[str, Any]]:
        if self.fixtures is None:
            return []
        products: list[dict[str, Any]] = []
        for candidate_id, pack in self.fixtures.packs.items():
            product_id = str(pack["product_id"])
            seller_published = product_id in self._SELLER_LISTING_IDS
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
            product: dict[str, Any] = {
                "id": product_id,
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
            if not seller_published:
                product.update(self._REAL_PRODUCT_EVIDENCE.get(product_id, {}))
            product.update(
                {
                    "listing_origin": (
                        "SELLER_PUBLISHED" if seller_published else "SEIL_RESEARCHED"
                    ),
                    "evidence_status": "PUBLISHED" if seller_published else "RESEARCH_ONLY",
                    "seller_attested": seller_published,
                    "status": "published" if seller_published else "research_only",
                }
            )
            products.append(product)
        return products

    def product(self, product_id: str) -> dict[str, Any] | None:
        return next((item for item in self.catalog() if item["id"] == product_id), None)

    async def chat(
        self, body: WorkspaceChatCreate, *, run_context: AgentRunContext
    ) -> dict[str, Any]:
        if not self.runtime_ready:
            raise ApiProblem(
                code="AGENT_PROVIDER_NOT_CONFIGURED",
                message="The workspace agent is not configured on the server.",
                status_code=503,
                retryable=False,
                next_action="configure_agent_runtime",
            )
        mission_id, _model_context = await self._prepare_mission(
            body=body,
            run_context=run_context,
        )
        return await self._chat_with_cognitive_kernel(
            body=body,
            mission_id=mission_id,
            run_context=run_context,
        )

    async def _chat_with_cognitive_kernel(
        self,
        *,
        body: WorkspaceChatCreate,
        mission_id: str,
        run_context: AgentRunContext,
    ) -> dict[str, Any]:
        if self.cognitive_engine is None:
            raise RuntimeError("cognitive engine is not configured")
        request_key = run_context.request_id or uuid4().hex
        result = await self.cognitive_engine.process(
            TurnCommand(
                organization_id=run_context.organization_id,
                actor_id=run_context.actor_id,
                actor_roles=tuple(sorted(run_context.actor_roles)),
                permissions=tuple(sorted(run_context.permissions)),
                principal=Principal.SIRA if body.mode == "sira" else Principal.SEIL,
                party=Party.BUYER if body.mode == "sira" else Party.SELLER,
                purpose="software_selection" if body.mode == "sira" else "seller_evidence",
                conversation_id=mission_id,
                turn_id=request_key,
                idempotency_key=request_key,
                message=body.message,
                available_tools=self._allowed_tools(body.mode),
                recent_messages=tuple(
                    {"role": item.role, "content": item.content} for item in body.history[-20:]
                ),
            )
        )
        snapshot = await self._persist_kernel_projection(
            mission_id=mission_id,
            result=result,
            run_context=run_context,
            turn_key=request_key,
        )
        return {
            "conversation_id": mission_id,
            "mission_id": mission_id,
            "message": result.message,
            "follow_up_required": result.status == "WAITING",
            "panel": None,
            "products": [],
            "tool_calls": list(result.tool_calls),
            "proposals": [],
            "mission": snapshot["mission"],
            "events": snapshot["events"],
            "artifacts": snapshot["artifacts"],
            "attention": None,
            "advisory_only": False,
        }

    async def _persist_kernel_projection(
        self,
        *,
        mission_id: str,
        result: TurnResult,
        run_context: AgentRunContext,
        turn_key: str,
    ) -> dict[str, Any]:
        if self.database is None:
            return {
                "mission": {
                    "id": mission_id,
                    "mode": "sira",
                    "goal": result.message,
                    "state": "PAUSED" if result.status == "WAITING" else result.status,
                    "version": 1,
                    "plan": [],
                    "stop_reason": None,
                },
                "events": [],
                "artifacts": [],
            }

        async def work(session: AsyncSession) -> dict[str, Any]:
            repository = MissionRepository(session, run_context.organization_id)
            mission = await repository.get_for_actor(mission_id, run_context.actor_id, lock=True)
            mission.state = "PAUSED" if result.status == "WAITING" else result.status
            mission.version += 1
            await repository.append_event(
                mission,
                event_type="assistant.message",
                event_key=f"assistant-message:{mission.id}:{turn_key}",
                actor_type="ROOT_AGENT",
                actor_id=f"{mission.mode.lower()}-agent",
                payload={"message": result.message, "cognitive_run_id": result.run_id},
            )
            for index, tool_name in enumerate(result.tool_calls):
                await repository.append_event(
                    mission,
                    event_type="agent.tool.completed",
                    event_key=f"kernel-tool-completed:{mission.id}:{turn_key}:{index}:{tool_name}",
                    actor_type="SYSTEM",
                    actor_id="mission-runtime",
                    payload={
                        "summary": f"Used {tool_name.replace('_', ' ')}",
                        "details": {
                            "tool": tool_name,
                            "cognitive_run_id": result.run_id,
                            "verified": True,
                        },
                    },
                )
            await repository.checkpoint(mission)
            return self._snapshot_view(await repository.snapshot(mission))

        return await self.database.run_retryable(run_context.organization_id, work)

    def _allowed_tools(self, mode: str) -> tuple[str, ...]:
        if self.cognitive_engine is None:
            return ()
        principal = Principal.SIRA if mode == "sira" else Principal.SEIL
        return tuple(
            name
            for name, tool in sorted(self.cognitive_engine.broker.catalog.items())
            if principal in tool.allowed_principals
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
                    for item in body.history[-20:]
                ],
            }
        requested_mission_id = mission_id
        turn_key = run_context.request_id or uuid4().hex

        async def work(session: AsyncSession) -> tuple[str, dict[str, Any]]:
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
            resolved_mission_id = requested_mission_id
            if resolved_mission_id is None:
                resolved_mission_id = f"msn_{uuid4().hex}"
                mission = await repository.create(
                    mission_id=resolved_mission_id,
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
                        resolved_mission_id, run_context.actor_id, lock=True
                    )
                except RecordNotFound:
                    mission = await repository.create(
                        mission_id=resolved_mission_id,
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
            mission.state = "ORIENTING"
            await repository.append_event(
                mission,
                event_type="user.message",
                event_key=f"user-message:{mission.id}:{turn_key}",
                actor_type="USER",
                actor_id=run_context.actor_id,
                payload={"message": body.message},
            )
            await repository.append_event(
                mission,
                event_type="agent.accepted",
                event_key=(f"agent-accepted:{mission.id}:{turn_key}"),
                actor_type="SYSTEM",
                actor_id="mission-runtime",
                payload={
                    "summary": "Request received; choosing the next evidence-backed action",
                    "details": {"safe_to_leave": True, "checkpoint": "request_received"},
                },
            )
            snapshot = await repository.snapshot(mission)
            return mission.id, snapshot.model_context()

        return await self.database.run_retryable(run_context.organization_id, work)

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
        response["handoffs"] = await self._mission_handoffs(run_context.organization_id, mission_id)
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
                    "verified": bool(
                        event.payload.get("details", {}).get(
                            "verified", event.actor_type == "SYSTEM"
                        )
                    ),
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
