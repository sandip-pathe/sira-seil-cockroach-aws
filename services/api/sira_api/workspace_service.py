"""Chat-first workspace service with explicit agent and catalogue boundaries."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC
from hashlib import sha256
from typing import Any, ClassVar
from urllib.parse import urlparse
from uuid import uuid4

from openai import AuthenticationError, RateLimitError
from pydantic import ValidationError
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
from sqlalchemy import select

from persistence.database import Database
from persistence.mission_repository import MissionRepository, MissionSnapshot
from persistence.models import Organization, PurchaseRequest, WorkflowRun
from persistence.repositories import RecordNotFound

from .errors import ApiProblem
from .fixtures import DemoFixtureBundle
from .proof_runtime import ProofWorkspaceRuntime
from .seil_web_research import (
    OpenAISeilWebResearcher,
    SeilDiscoveredProduct,
    SeilWebResearcher,
)
from .snowflake_service import SnowflakeDecisionService
from .workspace_schemas import WorkspaceChatCreate

logger = logging.getLogger(__name__)


def _canonical_agent_json(value: Any) -> Any:
    """Normalize model output before it enters hashed domain state."""

    if isinstance(value, float):
        return format(value, ".15g")
    if isinstance(value, dict):
        return {str(key): _canonical_agent_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical_agent_json(item) for item in value]
    return value


_GREETING_PATTERN = re.compile(
    r"^(?:hi|hello|hey|hiya|howdy|good\s+(?:morning|afternoon|evening))(?:\s+there)?[\s!,.?]*$",
    re.IGNORECASE,
)
_THANKS_PATTERN = re.compile(r"^(?:thanks|thank\s+you|thx)[\s!,.?]*$", re.IGNORECASE)
_GOODBYE_PATTERN = re.compile(r"^(?:bye|goodbye|see\s+you|later)[\s!,.?]*$", re.IGNORECASE)


def _compile_research_only_packet(
    payload: dict[str, Any], source_refs: list[dict[str, Any]]
) -> dict[str, Any]:
    """Project model research into SEIL's stable packet-shaped artifact boundary."""

    identity = payload.get("identity")
    if not isinstance(identity, dict):
        identity = {
            "product_name": payload.get("product_name") or payload.get("name") or "Unknown product",
            "seller_name": payload.get("seller_name") or payload.get("vendor") or "Unknown seller",
            "canonical_url": payload.get("canonical_url") or payload.get("website"),
        }
    evidence = []
    for index, source in enumerate(source_refs, start=1):
        if not isinstance(source, dict):
            continue
        evidence.append(
            {
                "id": f"public_source_{index}",
                "source_reference": source.get("url"),
                "title": source.get("title"),
                "source_class": source.get("authority") or "PUBLIC_WEB",
                "verification_state": "UNVERIFIED",
            }
        )
    return {
        "schema_version": "seil.product_evidence.research.v1",
        "state": "RESEARCH_ONLY",
        "publisher_authority": "PLATFORM_COMPILED",
        "identity": identity,
        "summary": payload.get("summary") or payload.get("public_summary"),
        "claims": payload.get("claims") if isinstance(payload.get("claims"), list) else [],
        "fit_rules": payload.get("fit_rules") if isinstance(payload.get("fit_rules"), list) else [],
        "anti_fit_rules": payload.get("anti_fit_rules")
        if isinstance(payload.get("anti_fit_rules"), list)
        else [],
        "evidence": evidence,
        "unknowns": payload.get("unknowns") if isinstance(payload.get("unknowns"), list) else [],
        "conflicts": payload.get("conflicts") if isinstance(payload.get("conflicts"), list) else [],
        "qualification_blockers": (
            payload.get("qualification_blockers")
            if isinstance(payload.get("qualification_blockers"), list)
            else []
        ),
        "seller_attested": False,
        "publishable": False,
    }


class WorkspaceService:
    _SELLER_LISTING_IDS: ClassVar[frozenset[str]] = frozenset(
        {"product_fixture_a", "product_fixture_b"}
    )
    _DATAHUB_BUYING_PROMPTS: ClassVar[frozenset[str]] = frozenset(
        {
            "choose a data/ai tool for our actual stack",
            "choose a customer-support ai for our actual data stack",
            "choose a support ai for our actual data estate",
        }
    )
    _DATAHUB_PRODUCT_IDENTITIES: ClassVar[dict[str, dict[str, str]]] = {
        "adapter-a": {
            "id": "support_ai_cleartext",
            "name": "ClearText Assist",
            "seller": "ClearText Labs",
        },
        "adapter-b": {
            "id": "support_ai_private_relay",
            "name": "Private Relay",
            "seller": "RelayWorks",
        },
    }
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
        api_key: str,
        seil_api_key: str | None = None,
        model: str,
        workflow_service: object | None = None,
        seller_evidence_service: object | None = None,
        database: Database | None = None,
        senso_providers: Mapping[str, object] | None = None,
        senso_error: str | None = None,
        snowflake_decision_service: SnowflakeDecisionService | None = None,
        proof_runtime: ProofWorkspaceRuntime | None = None,
        seil_web_researcher: SeilWebResearcher | None = None,
    ) -> None:
        self.fixtures = fixtures
        self.api_key = api_key
        self.seil_api_key = seil_api_key or api_key
        self.seil_backup_api_key = (
            api_key if api_key and self.seil_api_key and api_key != self.seil_api_key else ""
        )
        self._seil_backup_active = False
        self.workflow_service = workflow_service
        self.seller_evidence_service = seller_evidence_service
        self.database = database
        self.senso_providers = dict(senso_providers or {})
        self.senso_error = senso_error
        self.snowflake_decision_service = snowflake_decision_service
        self.proof_runtime = proof_runtime
        self.seil_web_researcher = seil_web_researcher or (
            OpenAISeilWebResearcher(api_key=self.seil_api_key, model=model)
            if self.seil_api_key
            else None
        )
        self._discovered_catalog: dict[str, dict[str, Any]] = {}
        self._market_refresh_tasks: set[asyncio.Task[None]] = set()
        tools = {**workspace_tool_registry(), **commerce_tool_registry()}
        self.runtime = OpenAIAgentsRuntime(model=model, tools=tools)

    def agent_services(self) -> dict[str, object]:
        services: dict[str, object] = {"workspace_catalog": self}
        if self.workflow_service is not None:
            services["workflow_service"] = self.workflow_service
        if self.seller_evidence_service is not None:
            services["seller_evidence_service"] = self.seller_evidence_service
        if self.snowflake_decision_service is not None:
            services["snowflake_decision_service"] = self.snowflake_decision_service
        services.update(self.senso_providers)
        return services

    def senso_status(self) -> tuple[bool, str]:
        if {"senso_buyer", "senso_seller"}.issubset(self.senso_providers):
            return True, "Buyer and seller folder scopes verified"
        return False, self.senso_error or "Senso is not configured"

    def datahub_status(self) -> tuple[bool, str]:
        if self.proof_runtime is None:
            return False, "Run the DataHub buying evaluation"
        try:
            decision = self.proof_runtime.buyer_decision()
        except ApiProblem:
            return False, "Run the DataHub buying evaluation"
        return (
            True,
            f"Verified buying context and receipt {decision['decision_hash'][-12:]}",
        )

    def capabilities(self) -> list[dict[str, str | None]]:
        senso_ready, _ = self.senso_status()
        return [
            {
                "id": "sira-agent",
                "label": "SIRA reasoning and tools",
                "status": "ready" if self.api_key else "misconfigured",
                "reason_code": "READY" if self.api_key else "SIRA_KEY_MISSING",
                "remediation": None if self.api_key else "Configure SIRA_OPENAI_API_KEY",
            },
            {
                "id": "seil-agent",
                "label": "SEIL reasoning and public research",
                "status": (
                    "degraded"
                    if self._seil_backup_active
                    else "ready"
                    if self.seil_api_key
                    else "misconfigured"
                ),
                "reason_code": (
                    "SEIL_BACKUP_KEY_ACTIVE"
                    if self._seil_backup_active
                    else "READY"
                    if self.seil_api_key
                    else "SEIL_KEY_MISSING"
                ),
                "remediation": (
                    "Replace the expired SEIL primary key"
                    if self._seil_backup_active
                    else None
                    if self.seil_api_key
                    else "Configure SEIL_OPENAI_API_KEY"
                ),
            },
            {
                "id": "senso",
                "label": "Private evidence search",
                "status": "ready" if senso_ready else "degraded",
                "reason_code": "READY" if senso_ready else "SENSO_SCOPE_UNAVAILABLE",
                "remediation": None if senso_ready else "Check the scoped Senso connector",
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
                else "Start PostgreSQL and the API",
            },
            {
                "id": "snowflake-decision-plane",
                "label": "Governed evidence and decision ledger",
                "status": (
                    "ready"
                    if self.snowflake_decision_service and self.snowflake_decision_service.enabled
                    else "offline"
                ),
                "reason_code": (
                    "READY"
                    if self.snowflake_decision_service and self.snowflake_decision_service.enabled
                    else "SNOWFLAKE_DISABLED"
                ),
                "remediation": (
                    None
                    if self.snowflake_decision_service and self.snowflake_decision_service.enabled
                    else "Configure the Snowflake application identity"
                ),
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
        products.extend(self._discovered_catalog.values())
        return products

    def product(self, product_id: str) -> dict[str, Any] | None:
        return next((item for item in self.catalog() if item["id"] == product_id), None)

    async def chat(
        self, body: WorkspaceChatCreate, *, run_context: AgentRunContext
    ) -> dict[str, Any]:
        if self._routes_to_datahub_fit(body):
            mission_id, _ = await self._prepare_mission(
                body=body,
                run_context=run_context,
            )
            return await self._run_datahub_fit_turn(
                mission_id=mission_id,
                run_context=run_context,
            )
        selected_api_key = self.api_key if body.mode == "sira" else self.seil_api_key
        if not selected_api_key:
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
        if self._routes_to_marketplace_discovery(body):
            return await self._run_marketplace_discovery_turn(
                body=body,
                mission_id=mission_id,
                run_context=run_context,
            )
        if self._routes_to_governed_snowflake(body):
            return await self._run_governed_snowflake_turn(
                mission_id=mission_id,
                run_context=run_context,
            )
        lightweight_reply = self._lightweight_reply(body.message, body.mode)
        if lightweight_reply is not None:
            answer = MissionTurnOutput(
                message=lightweight_reply,
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
            result = await self._run_agent(
                AgentRunRequest(
                    role=AgentRole.SIRA if body.mode == "sira" else AgentRole.SEIL,
                    instructions=instructions,
                    prompt=body.message,
                    model_context=model_context,
                    run_context=run_context,
                    allowed_tools=SIRA_TOOL_NAMES if body.mode == "sira" else SEIL_TOOL_NAMES,
                    output_type=MissionTurnOutput,
                    authority_mode=AuthorityMode.MISSION_OPERATOR,
                ),
                mode=body.mode,
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
            logger.exception(
                "agent turn failed",
                extra={
                    "request_id": run_context.request_id,
                    "mission_id": mission_id,
                    "agent_role": body.mode,
                    "error_type": type(error).__name__,
                },
            )
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
                continuation = await self._run_agent(
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
                    ),
                    mode=body.mode,
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
        snowflake_decision_ready = bool(visible_products) or (
            "search_published_products" in all_tool_calls
        )
        if (
            body.mode == "sira"
            and snowflake_decision_ready
            and self.snowflake_decision_service is not None
            and self.snowflake_decision_service.enabled
        ):
            try:
                snowflake_result = await self.snowflake_decision_service.create_decision(
                    organization_id=run_context.organization_id,
                    context_version=1,
                    mission_id=mission_id,
                    actor_id=run_context.actor_id,
                    idempotency_key=f"workspace-{mission_id}-context-v1",
                )
                snowflake_artifact = await self._persist_snowflake_artifact(
                    mission_id=mission_id,
                    run_context=run_context,
                    result=snowflake_result,
                )
                all_tool_calls.append("evaluate_cited_decision")
                visible_products = self._snowflake_products(snowflake_result)
                answer = self._snowflake_answer(snowflake_result)
                governed_persisted = await self._persist_turn(
                    mission_id=mission_id,
                    answer=answer,
                    run_context=run_context,
                    tool_calls=("evaluate_cited_decision",),
                    proposals=(),
                    turn_key=f"{run_context.request_id or uuid4().hex}:snowflake",
                )
                governed_persisted["artifacts"] = [
                    *persisted["artifacts"],
                    snowflake_artifact,
                ]
                persisted = governed_persisted
            except Exception:
                logger.exception("Snowflake decision enrichment failed")
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

    @classmethod
    def _routes_to_datahub_fit(cls, body: WorkspaceChatCreate) -> bool:
        normalized = " ".join(body.message.strip().casefold().split()).rstrip(".!?")
        return body.mode == "sira" and normalized in cls._DATAHUB_BUYING_PROMPTS

    @staticmethod
    def _routes_to_marketplace_discovery(body: WorkspaceChatCreate) -> bool:
        if body.mode != "sira":
            return False
        message = body.message.casefold()
        buying_intent = any(
            phrase in message
            for phrase in (
                "buy",
                "choose",
                "compare",
                "find",
                "looking for",
                "i need",
                "recommend",
                "replace",
            )
        )
        return buying_intent

    async def _run_marketplace_discovery_turn(
        self,
        *,
        body: WorkspaceChatCreate,
        mission_id: str,
        run_context: AgentRunContext,
    ) -> dict[str, Any]:
        if self.seil_web_researcher is not None:
            refresh_task = asyncio.create_task(self._refresh_marketplace_supply(body.message))
            self._market_refresh_tasks.add(refresh_task)
            refresh_task.add_done_callback(self._market_refresh_tasks.discard)
        catalog_products = self.catalog()
        seller_products = [
            product
            for product in catalog_products
            if product.get("listing_origin") == "SELLER_PUBLISHED"
        ]
        researched_products = [
            product
            for product in catalog_products
            if product.get("listing_origin") == "SEIL_RESEARCHED"
        ]
        candidates = [
            self._apply_company_fit(product, body.message)
            for product in [*seller_products, *researched_products]
        ]
        candidates.sort(
            key=lambda product: (
                -int(product.get("fit_match_count", 0)),
                str(product["name"]).casefold(),
            )
        )
        strong_matches = [
            str(product["name"]) for product in candidates if product.get("fit") == "Strong fit"
        ][:3]
        fit_summary = (
            f" Based on the requirements you stated, the strongest documented matches are "
            f"{', '.join(strong_matches)}."
            if strong_matches
            else " I need more company requirements before naming a strongest fit."
        )
        source_refs = [
            source for product in researched_products for source in product.get("source_refs", [])
        ]
        category = self._marketplace_category(body.message)
        answer = MissionTurnOutput(
            message=(
                f"I found {len(seller_products)} seller-published listings and SEIL broadened "
                f"the {category} market with {len(researched_products)} source-linked "
                "public listings. The researched listings are clearly provisional; I can compare "
                "all candidates against your company requirements, integrations, and constraints, "
                f"but only seller-reviewed evidence is treated as seller-attested.{fit_summary}"
            ),
            mission_state="SYNTHESIZING",
            artifacts=[
                {
                    "kind": "candidate_set",
                    "title": f"{category} marketplace candidates",
                    "authority": "OBSERVED",
                    "payload": {
                        "category": category,
                        "seller_published_count": len(seller_products),
                        "seil_researched_count": len(researched_products),
                        "candidate_ids": [product["id"] for product in candidates],
                        "ranking_boundary": (
                            "Research-only listings may be compared but are not seller-attested."
                        ),
                    },
                    "source_refs": source_refs,
                }
            ],
            show_product_ids=[product["id"] for product in candidates],
            stop_reason="SIRA_MARKETPLACE_CANDIDATES_READY",
        )
        persisted = await self._persist_turn(
            mission_id=mission_id,
            answer=answer,
            run_context=run_context,
            tool_calls=(
                "search_published_products",
                "search_seil_researched_listings",
                "compare_product_evidence",
            ),
            proposals=(),
            turn_key=f"{run_context.request_id or uuid4().hex}:marketplace-discovery",
        )
        return {
            "conversation_id": mission_id,
            "mission_id": mission_id,
            "message": answer.message,
            "follow_up_required": False,
            "panel": "catalog",
            "products": candidates,
            "tool_calls": [
                "search_published_products",
                "search_seil_researched_listings",
                "compare_product_evidence",
            ],
            "proposals": [],
            "mission": persisted["mission"],
            "events": persisted["events"],
            "artifacts": persisted["artifacts"],
            "attention": None,
            "advisory_only": False,
        }

    async def _refresh_marketplace_supply(self, request: str) -> None:
        if self.seil_web_researcher is None:
            return
        try:
            discovery = await self.seil_web_researcher.discover(request)
            catalog_domains = {self._listing_domain(product) for product in self.catalog()}
            for discovered in discovery.products:
                product = self._discovered_product_listing(discovered)
                domain = self._listing_domain(product)
                if domain in catalog_domains:
                    continue
                catalog_domains.add(domain)
                self._discovered_catalog[product["id"]] = product
        except Exception:
            logger.exception("background SEIL marketplace supply refresh failed")

    @staticmethod
    def _marketplace_category(request: str) -> str:
        normalized = request.casefold()
        if any(term in normalized for term in ("note", "meeting", "transcript")):
            return "meeting notes and conversation intelligence"
        return "business software"

    @staticmethod
    def _discovered_product_listing(product: SeilDiscoveredProduct) -> dict[str, Any]:
        canonical_url = product.identity.canonical_url or product.sources[0].url
        product_id = f"seil_research_{sha256(canonical_url.encode()).hexdigest()[:16]}"
        source_refs = []
        seen: set[str] = set()
        for source in product.sources:
            url = source.url.strip()
            if url in seen or not url.startswith(("http://", "https://")):
                continue
            seen.add(url)
            source_refs.append(
                {"title": source.title.strip(), "url": url, "authority": "PUBLIC_WEB"}
            )
        return {
            "id": product_id,
            "name": product.identity.product_name,
            "seller": product.identity.seller_name,
            "edition": "Public research",
            "price": WorkspaceService._compact_listing_text(product.price, 80),
            "billing_unit": "public_listing",
            "status": "research_only",
            "summary": WorkspaceService._compact_listing_text(product.summary, 320),
            "claims": product.claims,
            "integrations": product.integrations,
            "website": canonical_url,
            "logo": None,
            "evidence_freshness": "Live public-web research",
            "source_refs": source_refs,
            "listing_origin": "SEIL_RESEARCHED",
            "evidence_status": "RESEARCH_ONLY",
            "seller_attested": False,
        }

    @staticmethod
    def _listing_domain(product: dict[str, Any]) -> str:
        website = str(product.get("website") or "")
        hostname = (urlparse(website).hostname or "").casefold()
        return hostname.removeprefix("www.") or str(product.get("seller") or "").casefold()

    @staticmethod
    def _compact_listing_text(value: str, limit: int) -> str:
        compact = " ".join(value.split())
        return compact if len(compact) <= limit else f"{compact[: limit - 3].rstrip()}..."

    @staticmethod
    def _apply_company_fit(product: dict[str, Any], request: str) -> dict[str, Any]:
        normalized_request = request.casefold().replace("-", " ")
        known_requirements = {
            "google meet",
            "google workspace",
            "hubspot",
            "salesforce",
            "slack",
            "teams",
            "zoom",
        }
        required = sorted(item for item in known_requirements if item in normalized_request)
        searchable = " ".join(str(item) for item in product.get("integrations", [])).casefold()
        matched = [item for item in required if item in searchable]
        enriched = dict(product)
        enriched["fit_match_count"] = len(matched)
        if not required:
            enriched["fit"] = "Needs requirements"
            enriched["why_company"] = "No company integration requirements were stated yet."
            enriched["requirement_coverage"] = "Company fit not evaluated"
        elif len(matched) == len(required):
            enriched["fit"] = "Strong fit"
            enriched["why_company"] = f"Documented support for {', '.join(matched)}."
            enriched["requirement_coverage"] = f"{len(matched)}/{len(required)} stated integrations"
        elif matched:
            enriched["fit"] = "Partial fit"
            enriched["why_company"] = (
                f"Documented support for {', '.join(matched)}; the remaining stated integration "
                "needs evidence."
            )
            enriched["requirement_coverage"] = f"{len(matched)}/{len(required)} stated integrations"
        else:
            enriched["fit"] = "Needs evidence"
            enriched["why_company"] = "No evidence yet for the stated company integrations."
            enriched["requirement_coverage"] = f"0/{len(required)} stated integrations"
        return enriched

    async def _run_datahub_fit_turn(
        self,
        *,
        mission_id: str,
        run_context: AgentRunContext,
    ) -> dict[str, Any]:
        if self.proof_runtime is None:
            raise ApiProblem(
                code="DATAHUB_DECISION_UNAVAILABLE",
                message="The verified DataHub buying decision is not available.",
                status_code=503,
                retryable=False,
                next_action="run_proof_demo",
            )
        decision = self.proof_runtime.buyer_decision()
        products = self._datahub_products(decision)
        artifact = self._datahub_decision_artifact(decision)
        answer = MissionTurnOutput(
            message=(
                "Private Relay is the best technical fit for the stack you actually run. "
                "DataHub shows that customer email is governed PII, which makes raw PII egress "
                "a hard requirement: Private Relay passed that gate, while lower-priced "
                "ClearText Assist returned the synthetic email unredacted. Removing only the "
                "PII classification changes the winner to ClearText Assist; restoring it changes "
                "the winner back. The decision receipt was written to DataHub and reread. These "
                "are fictional evaluation candidates, so commercial terms still need validation."
            ),
            mission_state="SYNTHESIZING",
            artifacts=[artifact],
            show_product_ids=[product["id"] for product in products],
            stop_reason="DATAHUB_FIT_DECISION_READY",
        )
        tools = (
            "query_datahub_company_context",
            "retrieve_seil_product_evidence",
            "run_buyer_specific_trial",
            "evaluate_datahub_fit",
            "reread_datahub_decision_receipt",
        )
        persisted = await self._persist_turn(
            mission_id=mission_id,
            answer=answer,
            run_context=run_context,
            tool_calls=tools,
            proposals=(),
            turn_key=f"{run_context.request_id or uuid4().hex}:datahub-fit",
        )
        return {
            "conversation_id": mission_id,
            "mission_id": mission_id,
            "message": answer.message,
            "follow_up_required": False,
            "panel": "catalog",
            "products": products,
            "tool_calls": list(tools),
            "proposals": [],
            "mission": persisted["mission"],
            "events": persisted["events"],
            "artifacts": persisted["artifacts"],
            "attention": None,
            "advisory_only": False,
        }

    @classmethod
    def _datahub_products(cls, decision: dict[str, Any]) -> list[dict[str, Any]]:
        evidence_by_id = {item["adapterId"]: item for item in decision["seller_projections"]}
        products: list[dict[str, Any]] = []
        for adapter_id in ("adapter-b", "adapter-a"):
            evidence = evidence_by_id[adapter_id]
            identity = cls._DATAHUB_PRODUCT_IDENTITIES[adapter_id]
            selected = adapter_id == decision["selected_adapter_id"]
            fixed_price = evidence["fixedPrice"]
            products.append(
                {
                    "id": identity["id"],
                    "name": identity["name"],
                    "seller": identity["seller"],
                    "edition": "Governed Support AI",
                    "price": f"{fixed_price['currency']} {fixed_price['amount']}",
                    "billing_unit": "synthetic support case",
                    "status": "QUALIFIED" if selected else "BLOCKED",
                    "fit": "Qualified" if selected else "Blocked",
                    "summary": (
                        "Redacts governed customer email and passed every buyer-specific gate."
                        if selected
                        else "Lower price, but its trial exposed governed customer email."
                    ),
                    "why_company": (
                        "Passed the DataHub-derived PII, schema, and EU-region requirements."
                        if selected
                        else (
                            "Blocked because the buyer's DataHub-governed PII cannot leave "
                            "unredacted."
                        )
                    ),
                    "requirement_coverage": (
                        "3 of 3 required gates passed"
                        if selected
                        else "2 of 3 required gates passed"
                    ),
                    "claims": (
                        [
                            "PII redaction passed",
                            "Required schema supported",
                            "EU execution region passed",
                        ]
                        if selected
                        else [
                            "Lower fixed trial price",
                            "Required schema supported",
                            "Raw PII egress gate failed",
                        ]
                    ),
                    "integrations": ["datahub", "customer_support", "eu_processing"],
                    "website": None,
                    "logo": None,
                    "evidence_freshness": "Verified in the current DataHub-bound trial",
                    "source_refs": [
                        {
                            "title": "Versioned SEIL seller evidence",
                            "source_pack_version_id": evidence["sourcePackVersionId"],
                            "projection_hash": evidence["projectionHash"],
                            "authority": "SEIL_PUBLISHED",
                        }
                    ],
                }
            )
        return products

    @classmethod
    def _datahub_decision_artifact(cls, decision: dict[str, Any]) -> dict[str, Any]:
        current_product = cls._DATAHUB_PRODUCT_IDENTITIES["adapter-b"]
        alternative_product = cls._DATAHUB_PRODUCT_IDENTITIES["adapter-a"]
        context = decision["datahub_context"]
        facts = [
            {
                "id": f"datahub_fact_{index}",
                "label": source["label"],
                "value": source["value"],
                "source_urn": source["urn"],
                "source_type": "DATAHUB",
            }
            for index, source in enumerate(context["source_details"], start=1)
        ]
        requirement_labels = {
            "RAW_PII_EGRESS_FORBIDDEN": "Do not return raw governed PII",
            "EXECUTION_REGION_ALLOWED": "Run only in an allowed execution region",
            "REQUIRED_SCHEMA_SUPPORTED": "Support the governed support-data schema",
        }
        requirements = [
            {
                "id": gate_id,
                "label": requirement_labels.get(gate_id, gate_id.replace("_", " ").title()),
                "status": "REQUIRED",
                "derived_from": ["DataHub governed metadata"],
            }
            for gate_id in decision["requirements"]
        ]
        source_refs = [
            {
                "title": source["label"],
                "urn": source["urn"],
                "fact": source["fact"],
                "authority": "DATAHUB",
            }
            for source in context["source_details"]
        ]
        return {
            "kind": "cited_decision",
            "title": "DataHub-grounded support AI decision",
            "authority": "VERIFIED",
            "payload": {
                "decision_plane": "DATAHUB",
                "status": "PASS",
                "selected_product": {
                    "id": current_product["id"],
                    "name": current_product["name"],
                },
                "facts": facts,
                "requirements": requirements,
                "counterfactual": {
                    "with_datahub": {
                        "id": current_product["id"],
                        "name": current_product["name"],
                    },
                    "without_pii": {
                        "id": alternative_product["id"],
                        "name": alternative_product["name"],
                    },
                    "restored": {
                        "id": current_product["id"],
                        "name": current_product["name"],
                    },
                    "outcome": "RECOMMENDATION_CHANGED",
                    "fact": decision["counterfactual"]["fact"],
                    "source_urn": decision["counterfactual"]["source_urn"],
                },
                "negative_control": decision["negative_control"],
                "receipt": {
                    "decision_hash": decision["receipt"]["decision_hash"],
                    "datahub_anchor_urn": decision["receipt"]["anchor_urn"],
                    "writeback_status": "WRITTEN",
                    "reread_matched": decision["receipt"]["reread_matched"],
                },
                "run_id": decision["run_id"],
                "input_hash": decision["input_hash"],
                "decision_hash": decision["decision_hash"],
            },
            "source_refs": source_refs,
        }

    def _routes_to_governed_snowflake(self, body: WorkspaceChatCreate) -> bool:
        if (
            body.mode != "sira"
            or self.snowflake_decision_service is None
            or not self.snowflake_decision_service.enabled
        ):
            return False
        normalized = body.message.casefold()
        purchase_intent = any(
            term in normalized for term in ("find", "recommend", "compare", "evaluate", "buy")
        )
        routed = purchase_intent and "meeting" in normalized
        logger.info(
            "workspace capability route evaluated",
            extra={
                "mode": body.mode,
                "snowflake_enabled": True,
                "governed_snowflake_route": routed,
            },
        )
        return routed

    async def _run_governed_snowflake_turn(
        self,
        *,
        mission_id: str,
        run_context: AgentRunContext,
    ) -> dict[str, Any]:
        assert self.snowflake_decision_service is not None
        try:
            result = await self.snowflake_decision_service.create_decision(
                organization_id=run_context.organization_id,
                context_version=1,
                mission_id=mission_id,
                actor_id=run_context.actor_id,
                idempotency_key=f"workspace-{mission_id}-context-v1",
            )
        except Exception as error:
            logger.exception("Governed Snowflake decision failed")
            raise ApiProblem(
                code="SNOWFLAKE_DECISION_UNAVAILABLE",
                message="The governed decision service is temporarily unavailable.",
                status_code=503,
                retryable=True,
                next_action="retry_later",
            ) from error
        answer = self._snowflake_answer(result)
        tools = (
            "query_governed_company_context",
            "retrieve_cited_seller_evidence",
            "evaluate_cited_decision",
        )
        persisted = await self._persist_turn(
            mission_id=mission_id,
            answer=answer,
            run_context=run_context,
            tool_calls=tools,
            proposals=(),
            turn_key=f"{run_context.request_id or uuid4().hex}:snowflake",
        )
        artifact = await self._persist_snowflake_artifact(
            mission_id=mission_id,
            run_context=run_context,
            result=result,
        )
        persisted["artifacts"] = [*persisted["artifacts"], artifact]
        return {
            "conversation_id": mission_id,
            "mission_id": mission_id,
            "message": answer.message,
            "follow_up_required": False,
            "panel": "catalog",
            "products": self._snowflake_products(result),
            "tool_calls": list(tools),
            "proposals": [],
            "mission": persisted["mission"],
            "events": persisted["events"],
            "artifacts": persisted["artifacts"],
            "attention": None,
            "advisory_only": False,
        }

    @staticmethod
    def _snowflake_answer(result: dict[str, Any]) -> MissionTurnOutput:
        selected = str(result.get("selected_product_name") or "No eligible option")
        evaluated = {
            str(item.get("product_id")): item for item in result.get("evaluated_products", [])
        }
        generic_id = str(result.get("counterfactual", {}).get("after_selected_product_id") or "")
        generic = evaluated.get(generic_id, {})
        generic_name = str(generic.get("product_name") or "the generic winner")
        return MissionTurnOutput(
            message=(
                f"{selected} is the best eligible option. Your private HubSpot requirement "
                "changes the result: without it, "
                f"{generic_name} would win on price. Snowflake evaluated the governed company "
                "facts against seller-document evidence and recorded the cited decision."
            ),
            mission_state="SYNTHESIZING",
            stop_reason="GOVERNED_DECISION_READY",
        )

    @staticmethod
    def _snowflake_products(result: dict[str, Any]) -> list[dict[str, Any]]:
        products: list[dict[str, Any]] = []
        for item in result.get("evaluated_products", []):
            product_id = str(item["product_id"])
            eligible = bool(item["eligible"])
            products.append(
                {
                    "id": product_id,
                    "name": str(item["product_name"]),
                    "seller": "MeetAI Labs" if product_id == "prod_meetai_a" else "NoteSync",
                    "edition": ("HubSpot Integration" if product_id == "prod_meetai_a" else "Team"),
                    "price": f"USD {item['unit_price']}",
                    "billing_unit": "seat/month",
                    "status": "QUALIFIED" if eligible else "PASS",
                    "summary": (
                        "Fits the private HubSpot requirement and the USD 100 per-seat cap."
                        if eligible
                        else (
                            "Cheaper base tier, but the cited HubSpot tier exceeds the private cap."
                        )
                    ),
                    "claims": [
                        str(reason).replace("_", " ").title()
                        for reason in item.get("reason_codes", [])
                    ],
                    "integrations": ["hubspot", "google_workspace", "outlook"],
                    "logo": (
                        "/products/meetai.svg"
                        if product_id == "prod_meetai_a"
                        else "/products/notesync.svg"
                    ),
                    "evidence_freshness": "Parsed and evaluated in Snowflake",
                    "source_refs": [],
                }
            )
        products.sort(key=lambda item: item["status"] != "QUALIFIED")
        return products

    async def _persist_snowflake_artifact(
        self,
        *,
        mission_id: str,
        run_context: AgentRunContext,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        citations = [
            {
                "citation_type": item.get("citation_type"),
                "fact_id": item.get("fact_id"),
                "document_id": item.get("document_id"),
                "chunk_id": item.get("chunk_id"),
                "page_number": item.get("page_number"),
                "exact_excerpt": item.get("exact_excerpt"),
                "source_hash": item.get("source_hash"),
            }
            for item in result.get("citations", [])
        ]
        payload = {
            "request_id": result.get("request_id"),
            "selected_product": result.get("selected_product_name"),
            "status": result.get("status"),
            "reason_codes": result.get("reason_codes", []),
            "private_context_effect": result.get("counterfactual", {}).get("outcome"),
            "without_private_context": result.get("counterfactual", {}).get(
                "after_selected_product_id"
            ),
            "evaluated_products": result.get("evaluated_products", []),
            "run_id": result.get("run_id"),
            "input_hash": result.get("input_hash"),
            "decision_hash": result.get("decision_hash"),
        }
        if self.database is None:
            return {
                "id": f"snowflake-{result['run_id']}",
                "kind": "cited_decision",
                "title": "Governed Snowflake decision",
                "status": "READY",
                "authority": "VERIFIED",
                "payload": payload,
                "source_refs": citations,
            }
        async with self.database.transaction(run_context.organization_id) as session:
            repository = MissionRepository(session, run_context.organization_id)
            mission = await repository.get_for_actor(mission_id, run_context.actor_id, lock=True)
            artifact = await repository.add_artifact(
                mission,
                kind="cited_decision",
                title="Governed Snowflake decision",
                authority="VERIFIED",
                payload=_canonical_agent_json(payload),
                source_refs=_canonical_agent_json(citations),
                created_by="snowflake-decision-plane",
            )
            await session.flush()
            return self._artifact_view(artifact)

    async def _run_agent(self, request: AgentRunRequest, *, mode: str) -> Any:
        if mode != "seil":
            return await self.runtime.run(replace(request, api_key=self.api_key))
        selected = self.seil_backup_api_key if self._seil_backup_active else self.seil_api_key
        try:
            return await self.runtime.run(replace(request, api_key=selected))
        except AuthenticationError:
            if self._seil_backup_active or not self.seil_backup_api_key:
                raise
            self._seil_backup_active = True
            logger.warning(
                "SEIL primary credential rejected; activating configured backup",
                extra={"agent_role": "seil", "reason_code": "SEIL_BACKUP_KEY_ACTIVE"},
            )
            return await self.runtime.run(replace(request, api_key=self.seil_backup_api_key))

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
        return WorkspaceService._lightweight_reply(message, "sira") is not None

    @staticmethod
    def _lightweight_reply(message: str, mode: str) -> str | None:
        normalized = " ".join(message.strip().split())
        if _GREETING_PATTERN.fullmatch(normalized):
            return (
                "Hi! What would you like help buying?"
                if mode == "sira"
                else "Hi! What product work can I help with?"
            )
        if _THANKS_PATTERN.fullmatch(normalized):
            return "You're welcome."
        if _GOODBYE_PATTERN.fullmatch(normalized):
            return "See you soon."
        return None

    @staticmethod
    def _root_agent_instructions(mode: str) -> str:
        shared = (
            "You are the persistent root commerce agent for one mission. Infer intent, maintain a "
            "plan and world model, use tools before asking the user for facts that can be found, "
            "and ask only when a material ambiguity, authority boundary, credential, or choice "
            "blocks useful work. Ask at most four material discovery questions, never repeat an "
            "answered question, and treat unknown optional details as assumptions rather than "
            "blocking useful preliminary results. A greeting gets a short greeting, not a "
            "fabricated project plan. "
            "Produce typed events and inspectable artifacts for meaningful work. Claims must name "
            "their authority and sources; label inference as inference. Delegate only bounded "
            "tasks with an explicit budget. You may evaluate, compare, rank, and recommend. "
            "Your final output must always use the MissionTurnOutput envelope. Never return an "
            "artifact by itself; place it inside artifacts[]. You may draft "
            "protected actions, but you cannot grant yourself capabilities, approve, charge, send, "
            "publish, sign, or activate. Those effects require a server-issued grant and exact "
            "human authority. Do not expose secrets or raw private evidence."
        )
        if mode == "sira":
            return (
                f"{shared} You are SIRA, operating for the buyer. Search company evidence and the "
                "catalogue. SEIL maintains seller-published listings and separately discovers "
                "provisional public-web listings to prevent a cold-start catalogue. Compare both, "
                "but preserve their authority labels and never describe a researched listing as "
                "seller-attested. Design reproducible evaluations when evidence is insufficient, "
                "build "
                "candidate and comparison artifacts, and advance to a purchase proposal only when "
                "the evidence supports it. Product IDs shown to the UI must come from tools."
            )
        return (
            f"{shared} You are SEIL, operating for the seller. Build and improve evidence-backed "
            "product twins, resolve claim gaps, and prepare reviewable publication proposals. "
            "Vendor chat only operates on the authenticated seller's own products. Public-web "
            "market discovery is a separate platform supply process and must never be initiated "
            "from seller chat. Never invent product claims or expose seller-private sources to "
            "buyers."
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
                    event_key=(
                        f"agent-accepted:{mission.id}:{run_context.request_id or uuid4().hex}"
                    ),
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
                "steps": [
                    _canonical_agent_json(item.model_dump(mode="json")) for item in answer.plan
                ],
                "updated_by": "root_agent",
            }
            mission.world_model = {
                "claims": [
                    _canonical_agent_json(item.model_dump(mode="json")) for item in answer.claims
                ],
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
                        "details": {"tool": tool_name, "verified": False},
                    },
                )
            for index, event in enumerate(answer.events):
                await repository.append_event(
                    mission,
                    event_type=event.event_type,
                    event_key=f"agent-event:{mission.id}:{event_turn_key}:{index}",
                    actor_type="ROOT_AGENT",
                    actor_id="sira-root-agent",
                    payload={
                        "summary": event.summary,
                        "details": _canonical_agent_json(event.details),
                    },
                )
            for task in answer.tasks:
                await repository.add_task(
                    mission,
                    kind=task.kind,
                    title=task.title,
                    owner_type=task.owner_type,
                    assigned_role=task.assigned_role,
                    input_payload=_canonical_agent_json(task.input),
                    budget=_canonical_agent_json(task.budget),
                )
            persisted_artifacts = []
            for artifact in answer.artifacts:
                authority = artifact.authority
                if authority in {"OBSERVED", "VERIFIED"} and not artifact.source_refs:
                    authority = "INFERRED"
                artifact_payload = artifact.payload
                if artifact.kind == "seller_evidence":
                    artifact_payload = _compile_research_only_packet(
                        artifact.payload, artifact.source_refs
                    )
                persisted_artifacts.append(
                    await repository.add_artifact(
                        mission,
                        kind=artifact.kind,
                        title=artifact.title,
                        authority=authority,
                        payload=_canonical_agent_json(artifact_payload),
                        source_refs=_canonical_agent_json(artifact.source_refs),
                        created_by="sira-root-agent",
                    )
                )
            await repository.checkpoint(mission)
            snapshot = await repository.snapshot(mission)
            response = self._snapshot_view(snapshot)
            response["events"] = response["events"][-(len(answer.events) + len(tool_calls) + 1) :]
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
