"""Chat-first workspace service with explicit agent and catalogue boundaries."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from openai import AuthenticationError, RateLimitError
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from persistence.database import Database
from persistence.models import WorkflowRun
from sira_agents.commerce_tools import SEIL_TOOL_NAMES, SIRA_TOOL_NAMES, commerce_tool_registry
from sira_agents.runtime import AgentRole, AgentRunContext, AgentRunRequest, OpenAIAgentsRuntime
from sira_agents.workspace_tools import workspace_tool_registry

from .errors import ApiProblem
from .fixtures import DemoFixtureBundle
from .workspace_schemas import WorkspaceChatCreate


class _AgentAnswer(BaseModel):
    message: str
    follow_up_required: bool = False
    panel: str = "run"
    show_catalog: bool = False


_CATALOG_PRESENTATION: dict[str, dict[str, str]] = {
    "product_fixture_d": {
        "category": "Meeting intelligence",
        "deployment": "1 business day",
        "fit": "Best company fit",
        "why_company": "Fits a ten-consultant team, keeps client conversations private, and works with the tools already in use.",
        "admin_effort": "Low",
        "evidence_freshness": "Reviewed 2 days ago",
        "requirement_coverage": "4 of 4 key needs",
        "limitation": "Advanced retention policies and SCIM require the Enterprise edition.",
        "logo_url": "/product-logos/northstar.svg",
        "logo_tone": "teal",
        "seats": "10–50 seats",
    },
    "product_fixture_c": {
        "category": "Conversation intelligence",
        "deployment": "3–5 business days",
        "fit": "Supported alternative",
        "why_company": "Covers the current stack and privacy needs, but needs a named workspace administrator for rollout and policy changes.",
        "admin_effort": "Medium",
        "evidence_freshness": "Reviewed 6 days ago",
        "requirement_coverage": "4 of 4 key needs",
        "limitation": "Implementation includes a two-hour admin setup session and ongoing workspace ownership.",
        "logo_url": "/product-logos/relayiq.svg",
        "logo_tone": "blue",
        "seats": "10–100 seats",
    },
    "product_fixture_b": {
        "category": "AI meeting assistant",
        "deployment": "1 business day",
        "fit": "Internal teams only",
        "why_company": "The lowest-friction option for internal meetings, but it cannot isolate access for shared client workspaces.",
        "admin_effort": "Low",
        "evidence_freshness": "Reviewed 12 days ago",
        "requirement_coverage": "3 of 4 key needs",
        "limitation": "Restricted external-client workspaces are not available on the Team plan.",
        "logo_url": "/product-logos/briefly.svg",
        "logo_tone": "plum",
        "seats": "5–50 seats",
    },
    "product_fixture_a": {
        "category": "AI meeting notes",
        "deployment": "Same day",
        "fit": "Policy mismatch",
        "why_company": "Affordable and quick to roll out, but its model-improvement terms conflict with the client-data requirement.",
        "admin_effort": "Low",
        "evidence_freshness": "Reviewed 8 days ago",
        "requirement_coverage": "2 of 4 key needs",
        "limitation": "The Starter terms allow customer content to be used for general model improvement.",
        "logo_url": "/product-logos/memoflow.svg",
        "logo_tone": "gold",
        "seats": "Up to 25 seats",
    },
}


class WorkspaceService:
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
            product.update(_CATALOG_PRESENTATION.get(str(pack["product_id"]), {}))
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
        instructions = (
            "You are SIRA, a B2B buying assistant. Collect purchasing context conversationally. "
            "Ask one material question at a time until outcome, users, deadline, constraints, "
            "budget, "
            "and approval path are sufficiently clear. Never claim to rank, approve, buy, pay, or "
            "activate anything. Use catalogue tools for product facts and never invent products. "
            "Use search_senso_evidence for company documents and preserve source citations. "
            "When the context is sufficient and the user explicitly asks to create or start the "
            "buying work, call propose_purchase_request. Tell the user that nothing is created "
            "until they confirm the returned proposal. "
            "When the user asks to browse, compare, buy, find, or see products, set "
            "show_catalog true. "
            "Return only JSON with message, follow_up_required, panel, and show_catalog."
            if body.mode == "sira"
            else "You are SEIL, a B2B selling assistant. Collect product and evidence "
            "context one question "
            "at a time. Use seller tools for product, evidence, Pack, and sanitized buyer facts. "
            "Use search_senso_evidence for seller-private sources and preserve citations. "
            "Tool proposals are advisory drafts requiring human review. Never publish, approve, "
            "or invent claims. When the user asks to change claims, fit rules, anti-fit rules, or "
            "request review, use the matching proposal tool. Return only JSON with message, "
            "follow_up_required, panel, and show_catalog=false."
        )
        try:
            result = await self.runtime.run(
                AgentRunRequest(
                    role=AgentRole.SIRA if body.mode == "sira" else AgentRole.SEIL,
                    instructions=instructions,
                    prompt=body.message,
                    model_context={
                        "recent_history": [
                            {"role": item.role, "content": item.content}
                            for item in body.history[-12:]
                        ],
                    },
                    run_context=run_context,
                    allowed_tools=SIRA_TOOL_NAMES if body.mode == "sira" else SEIL_TOOL_NAMES,
                    output_type=_AgentAnswer,
                )
            )
            raw = result.output
            if isinstance(raw, str):
                cleaned = raw.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.removeprefix("```json").removeprefix("```")
                    cleaned = cleaned.removesuffix("```").strip()
                parsed = json.loads(cleaned)
            else:
                parsed = raw
            answer = _AgentAnswer.model_validate(parsed)
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
        panel = "catalog" if answer.show_catalog else answer.panel
        if panel not in {"run", "catalog", "connectors", "decisions", "inbox"}:
            panel = "run"
        conversation_id = body.conversation_id or f"wc_{uuid4().hex}"
        messages = [item.model_dump(mode="json") for item in body.history]
        messages.extend(
            [
                {"role": "user", "content": body.message},
                {
                    "role": "assistant",
                    "content": answer.message,
                    "tool_calls": list(dict.fromkeys(result.tool_calls)),
                    "proposals": list(result.proposals),
                },
            ]
        )
        await self._save_conversation(
            run_context=run_context,
            conversation_id=conversation_id,
            mode=body.mode,
            messages=messages[-40:],
        )
        return {
            "conversation_id": conversation_id,
            "message": answer.message,
            "follow_up_required": answer.follow_up_required,
            "panel": panel,
            "products": self.catalog() if answer.show_catalog else [],
            "tool_calls": list(dict.fromkeys(result.tool_calls)),
            "proposals": list(result.proposals),
            "advisory_only": True,
        }

    async def conversations(
        self, *, run_context: AgentRunContext, mode: str
    ) -> list[dict[str, Any]]:
        if self.database is None:
            return []
        async with self.database.transaction(run_context.organization_id) as session:
            records = list(
                (
                    await session.execute(
                        select(WorkflowRun)
                        .where(
                            WorkflowRun.organization_id == run_context.organization_id,
                            WorkflowRun.aggregate_type == "WORKSPACE_CONVERSATION",
                            WorkflowRun.operation == f"workspace.chat.{mode}",
                        )
                        .order_by(WorkflowRun.updated_at.desc())
                    )
                ).scalars()
            )
        results: list[dict[str, Any]] = []
        for record in records:
            metadata = record.event_log[0] if record.event_log else {}
            if metadata.get("actor_id") != run_context.actor_id:
                continue
            messages = [item for item in record.event_log[1:] if item.get("role")]
            first_user = next(
                (str(item.get("content", "")) for item in messages if item.get("role") == "user"),
                "New chat",
            )
            results.append(
                {
                    "id": record.aggregate_id,
                    "mode": mode,
                    "title": first_user[:46] or "New chat",
                    "messages": messages,
                    "updated_at": record.updated_at.astimezone(UTC).isoformat(),
                }
            )
        return results

    async def _save_conversation(
        self,
        *,
        run_context: AgentRunContext,
        conversation_id: str,
        mode: str,
        messages: list[dict[str, Any]],
    ) -> None:
        if self.database is None:
            return
        async with self.database.transaction(run_context.organization_id) as session:
            record = (
                await session.execute(
                    select(WorkflowRun).where(
                        WorkflowRun.organization_id == run_context.organization_id,
                        WorkflowRun.aggregate_type == "WORKSPACE_CONVERSATION",
                        WorkflowRun.aggregate_id == conversation_id,
                        WorkflowRun.operation == f"workspace.chat.{mode}",
                    )
                )
            ).scalar_one_or_none()
            event_log = [{"actor_id": run_context.actor_id}, *messages]
            if record is None:
                session.add(
                    WorkflowRun(
                        id=f"wrun_{uuid4().hex}",
                        organization_id=run_context.organization_id,
                        aggregate_type="WORKSPACE_CONVERSATION",
                        aggregate_id=conversation_id,
                        operation=f"workspace.chat.{mode}",
                        status="COMPLETED",
                        result_reference=None,
                        safe_error_code=None,
                        event_log=event_log,
                    )
                )
            else:
                metadata = record.event_log[0] if record.event_log else {}
                if metadata.get("actor_id") != run_context.actor_id:
                    raise PermissionError("conversation belongs to another actor")
                record.event_log = event_log
                record.updated_at = datetime.now(UTC)
