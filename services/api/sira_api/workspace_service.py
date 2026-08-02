"""Chat-first workspace service with explicit agent and catalogue boundaries."""

from __future__ import annotations

import json
from typing import Any

from openai import AuthenticationError, RateLimitError
from pydantic import BaseModel, ValidationError
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


class WorkspaceService:
    def __init__(
        self,
        fixtures: DemoFixtureBundle | None,
        *,
        api_key: str,
        model: str,
        workflow_service: object | None = None,
        seller_evidence_service: object | None = None,
    ) -> None:
        self.fixtures = fixtures
        self.api_key = api_key
        self.workflow_service = workflow_service
        self.seller_evidence_service = seller_evidence_service
        tools = {**workspace_tool_registry(), **commerce_tool_registry()}
        self.runtime = OpenAIAgentsRuntime(model=model, tools=tools)

    def agent_services(self) -> dict[str, object]:
        services: dict[str, object] = {"workspace_catalog": self}
        if self.workflow_service is not None:
            services["workflow_service"] = self.workflow_service
        if self.seller_evidence_service is not None:
            services["seller_evidence_service"] = self.seller_evidence_service
        return services

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
            products.append(
                {
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
            )
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
            "When the user asks to browse, compare, buy, find, or see products, set "
            "show_catalog true. "
            "Return only JSON with message, follow_up_required, panel, and show_catalog."
            if body.mode == "sira"
            else "You are SEIL, a B2B selling assistant. Collect product and evidence "
            "context one question "
            "at a time. Use seller tools for product, evidence, Pack, and sanitized buyer facts. "
            "Tool proposals are advisory drafts requiring human review. Never publish, approve, "
            "or invent claims. Return only JSON with message, "
            "follow_up_required, panel, and show_catalog=false."
        )
        try:
            result = await self.runtime.run(
                AgentRunRequest(
                    role=AgentRole.SIRA if body.mode == "sira" else AgentRole.SEIL,
                    instructions=instructions,
                    prompt=body.message,
                    model_context={
                        "recent_history": [item.model_dump() for item in body.history[-12:]],
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
        return {
            "message": answer.message,
            "follow_up_required": answer.follow_up_required,
            "panel": panel,
            "products": self.catalog() if answer.show_catalog else [],
            "tool_calls": list(dict.fromkeys(result.tool_calls)),
            "advisory_only": True,
        }
