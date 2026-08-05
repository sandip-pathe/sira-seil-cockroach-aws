"""Strict SIRA and SEIL tools over existing application-service boundaries."""

from __future__ import annotations

from typing import Any, Literal, Protocol, cast

from pydantic import BaseModel

from agents import RunContextWrapper, WebSearchTool, function_tool
from domain import content_hash
from sira_agents.runtime import AgentRunContext


class WorkflowToolsService(Protocol):
    async def get_purchase_request(
        self, organization_id: str, request_id: str
    ) -> dict[str, Any]: ...

    async def get_purchase_brief(
        self, organization_id: str, request_id: str
    ) -> dict[str, Any]: ...

    async def get_requirement_brief(
        self,
        organization_id: str,
        brief_id: str,
        *,
        actor_id: str,
        actor_party: str | None,
    ) -> dict[str, Any]: ...

    async def decision_view(
        self, organization_id: str, request_id: str
    ) -> dict[str, Any]: ...

    async def get_decision(
        self, organization_id: str, decision_id: str
    ) -> dict[str, Any]: ...

    async def counterfactuals(
        self, organization_id: str, decision_id: str
    ) -> dict[str, Any]: ...

    async def purchase_status(
        self, organization_id: str, intent_id: str
    ) -> dict[str, Any]: ...

    async def stackfile(self, organization_id: str) -> dict[str, Any]: ...


class SellerToolsService(Protocol):
    async def search_products(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_role: str,
        query: str | None,
    ) -> dict[str, Any]: ...

    async def get_product_view(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_role: str,
        product_id: str,
    ) -> dict[str, Any]: ...

    async def get_draft(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_role: str,
        draft_id: str,
    ) -> dict[str, Any]: ...

    async def get_exports(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_role: str,
        version_id: str,
    ) -> dict[str, Any]: ...


class AgentProposal(BaseModel):
    proposal_type: str
    proposal_hash: str
    payload: dict[str, Any]
    advisory_only: bool = True
    ranking_effect: bool = False
    requires_human_action: bool = True


def _require_permission(context: AgentRunContext, permission: str) -> None:
    if permission not in context.permissions:
        raise PermissionError(f"agent tool requires {permission}")


def _workflow(context: AgentRunContext) -> WorkflowToolsService:
    service = context.services.get("workflow_service")
    if service is None:
        raise RuntimeError("workflow service is unavailable")
    return cast(WorkflowToolsService, service)


def _seller(context: AgentRunContext) -> SellerToolsService:
    service = context.services.get("seller_evidence_service")
    if service is None:
        raise RuntimeError("seller evidence service is unavailable")
    return cast(SellerToolsService, service)


def _seller_role(context: AgentRunContext) -> str:
    normalized_roles = {role.strip().casefold() for role in context.actor_roles}
    if "platform_operator" in normalized_roles:
        return "PLATFORM_OPERATOR"
    if context.party != "SELLER":
        raise PermissionError("SEIL tools require a seller identity")
    if "seller_reviewer" in normalized_roles:
        return "SELLER_REVIEWER"
    if "seller_editor" in normalized_roles:
        return "SELLER_EDITOR"
    if "seller_viewer" in normalized_roles:
        return "SELLER_EDITOR"
    raise PermissionError("SEIL tools require seller_editor or seller_reviewer")


def _proposal(
    context: AgentRunContext, proposal_type: str, payload: dict[str, Any]
) -> AgentProposal:
    bound_payload = {
        "organization_id": context.organization_id,
        "actor_id": context.actor_id,
        **payload,
    }
    return AgentProposal(
        proposal_type=proposal_type,
        proposal_hash=content_hash({"proposal_type": proposal_type, **bound_payload}),
        payload=bound_payload,
    )


@function_tool(strict_mode=True)
async def get_purchase_request(
    wrapper: RunContextWrapper[AgentRunContext], request_id: str
) -> dict[str, Any]:
    """Load one buyer purchase request by exact server-owned ID."""

    _require_permission(wrapper.context, "can_view_context")
    return await _workflow(wrapper.context).get_purchase_request(
        wrapper.context.organization_id, request_id
    )


@function_tool(strict_mode=True)
async def get_purchase_brief(
    wrapper: RunContextWrapper[AgentRunContext], request_id: str
) -> dict[str, Any]:
    """Load the current private Purchase Brief for one request."""

    _require_permission(wrapper.context, "can_view_context")
    return await _workflow(wrapper.context).get_purchase_brief(
        wrapper.context.organization_id, request_id
    )


@function_tool(strict_mode=True)
async def get_stack_snapshot(
    wrapper: RunContextWrapper[AgentRunContext],
) -> dict[str, Any]:
    """Load the buyer organization's current Stackfile snapshot."""

    _require_permission(wrapper.context, "can_view_context")
    return await _workflow(wrapper.context).stackfile(wrapper.context.organization_id)


@function_tool(strict_mode=True)
async def get_decision_view(
    wrapper: RunContextWrapper[AgentRunContext], request_id: str
) -> dict[str, Any]:
    """Load the action-neutral current decision view for one purchase request."""

    _require_permission(wrapper.context, "can_view_context")
    return await _workflow(wrapper.context).decision_view(
        wrapper.context.organization_id, request_id
    )


@function_tool(strict_mode=True)
async def get_decision_ledger(
    wrapper: RunContextWrapper[AgentRunContext], decision_id: str
) -> dict[str, Any]:
    """Load the frozen deterministic ledger for one decision."""

    _require_permission(wrapper.context, "can_view_context")
    return await _workflow(wrapper.context).get_decision(
        wrapper.context.organization_id, decision_id
    )


@function_tool(strict_mode=True)
async def get_decision_counterfactuals(
    wrapper: RunContextWrapper[AgentRunContext], decision_id: str
) -> dict[str, Any]:
    """Load deterministic company-aware counterfactuals for one decision."""

    _require_permission(wrapper.context, "can_view_context")
    return await _workflow(wrapper.context).counterfactuals(
        wrapper.context.organization_id, decision_id
    )


@function_tool(strict_mode=True)
async def get_purchase_status(
    wrapper: RunContextWrapper[AgentRunContext], purchase_intent_id: str
) -> dict[str, Any]:
    """Load canonical approval, payment and fulfillment status without acting on it."""

    _require_permission(wrapper.context, "can_view_context")
    return await _workflow(wrapper.context).purchase_status(
        wrapper.context.organization_id, purchase_intent_id
    )


@function_tool(strict_mode=True)
async def propose_purchase_request(
    wrapper: RunContextWrapper[AgentRunContext],
    intent: str,
    visibility: Literal["PRIVATE", "SELECTIVE"] = "SELECTIVE",
) -> AgentProposal:
    """Create a non-authoritative purchase-request proposal for human confirmation."""

    _require_permission(wrapper.context, "can_submit_request")
    return _proposal(
        wrapper.context,
        "PURCHASE_REQUEST",
        {"intent": intent.strip(), "visibility": visibility},
    )


@function_tool(strict_mode=True)
async def propose_plan_selection(
    wrapper: RunContextWrapper[AgentRunContext], request_id: str, plan_id: str
) -> AgentProposal:
    """Propose selecting an exact deterministic plan; this does not select it."""

    _require_permission(wrapper.context, "can_select_recommendation")
    return _proposal(
        wrapper.context,
        "PLAN_SELECTION",
        {"request_id": request_id, "plan_id": plan_id},
    )


@function_tool(strict_mode=True)
async def request_purchase_approval(
    wrapper: RunContextWrapper[AgentRunContext], purchase_intent_id: str
) -> AgentProposal:
    """Propose opening approval for an existing intent; this never approves or pays."""

    _require_permission(wrapper.context, "can_select_recommendation")
    return _proposal(
        wrapper.context,
        "APPROVAL_REQUEST",
        {"purchase_intent_id": purchase_intent_id},
    )


@function_tool(strict_mode=True)
async def search_seller_products(
    wrapper: RunContextWrapper[AgentRunContext], query: str = ""
) -> dict[str, Any]:
    """Search products visible to the authenticated seller identity."""

    return await _seller(wrapper.context).search_products(
        organization_id=wrapper.context.organization_id,
        actor_id=wrapper.context.actor_id,
        actor_role=_seller_role(wrapper.context),
        query=query.strip() or None,
    )


@function_tool(strict_mode=True)
async def get_seller_product_view(
    wrapper: RunContextWrapper[AgentRunContext], product_id: str
) -> dict[str, Any]:
    """Load seller-visible Pack health, validation, review and available actions."""

    return await _seller(wrapper.context).get_product_view(
        organization_id=wrapper.context.organization_id,
        actor_id=wrapper.context.actor_id,
        actor_role=_seller_role(wrapper.context),
        product_id=product_id,
    )


@function_tool(strict_mode=True)
async def get_seller_pack_draft(
    wrapper: RunContextWrapper[AgentRunContext], draft_id: str
) -> dict[str, Any]:
    """Load one seller-authorized Pack draft and its current revision."""

    return await _seller(wrapper.context).get_draft(
        organization_id=wrapper.context.organization_id,
        actor_id=wrapper.context.actor_id,
        actor_role=_seller_role(wrapper.context),
        draft_id=draft_id,
    )


@function_tool(strict_mode=True)
async def get_seller_pack_exports(
    wrapper: RunContextWrapper[AgentRunContext], pack_version_id: str
) -> dict[str, Any]:
    """Load safe export references for an authorized published Pack version."""

    return await _seller(wrapper.context).get_exports(
        organization_id=wrapper.context.organization_id,
        actor_id=wrapper.context.actor_id,
        actor_role=_seller_role(wrapper.context),
        version_id=pack_version_id,
    )


@function_tool(strict_mode=True)
async def get_engagement_requirement_brief(
    wrapper: RunContextWrapper[AgentRunContext], requirement_brief_id: str
) -> dict[str, Any]:
    """Load only an engagement-granted sanitized Requirement Brief for this seller."""

    _seller_role(wrapper.context)
    return await _workflow(wrapper.context).get_requirement_brief(
        wrapper.context.organization_id,
        requirement_brief_id,
        actor_id=wrapper.context.actor_id,
        actor_party=wrapper.context.party,
    )


@function_tool(strict_mode=True)
async def propose_pack_claim(
    wrapper: RunContextWrapper[AgentRunContext],
    draft_id: str,
    field: str,
    value: str,
    evidence_ids: list[str],
) -> AgentProposal:
    """Propose one evidence-linked Pack claim; this never edits or publishes the Pack."""

    role = _seller_role(wrapper.context)
    if role not in {"SELLER_EDITOR", "PLATFORM_OPERATOR"}:
        raise PermissionError("Pack claim proposals require seller_editor")
    return _proposal(
        wrapper.context,
        "PACK_CLAIM",
        {
            "draft_id": draft_id,
            "field": field,
            "value": value,
            "evidence_ids": evidence_ids,
        },
    )


@function_tool(strict_mode=True)
async def propose_fit_rule(
    wrapper: RunContextWrapper[AgentRunContext],
    draft_id: str,
    field: str,
    operator: str,
    value: str,
) -> AgentProposal:
    """Propose a best-fit rule; it has no buyer ranking authority."""

    role = _seller_role(wrapper.context)
    if role not in {"SELLER_EDITOR", "PLATFORM_OPERATOR"}:
        raise PermissionError("fit-rule proposals require seller_editor")
    return _proposal(
        wrapper.context,
        "FIT_RULE",
        {"draft_id": draft_id, "field": field, "operator": operator, "value": value},
    )


@function_tool(strict_mode=True)
async def propose_anti_fit_rule(
    wrapper: RunContextWrapper[AgentRunContext],
    draft_id: str,
    field: str,
    operator: str,
    value: str,
) -> AgentProposal:
    """Propose a seller anti-fit rule for independent review before publication."""

    role = _seller_role(wrapper.context)
    if role not in {"SELLER_EDITOR", "PLATFORM_OPERATOR"}:
        raise PermissionError("anti-fit proposals require seller_editor")
    return _proposal(
        wrapper.context,
        "ANTI_FIT_RULE",
        {"draft_id": draft_id, "field": field, "operator": operator, "value": value},
    )


@function_tool(strict_mode=True)
async def request_pack_review(
    wrapper: RunContextWrapper[AgentRunContext], draft_id: str
) -> AgentProposal:
    """Propose submitting a Pack draft for human review; this never submits or publishes."""

    role = _seller_role(wrapper.context)
    if role not in {"SELLER_EDITOR", "PLATFORM_OPERATOR"}:
        raise PermissionError("Pack review proposals require seller_editor")
    return _proposal(wrapper.context, "PACK_REVIEW_REQUEST", {"draft_id": draft_id})


SIRA_TOOL_NAMES = (
    "search_published_products",
    "get_published_product",
    "search_senso_evidence",
    "get_purchase_request",
    "get_purchase_brief",
    "get_stack_snapshot",
    "get_decision_view",
    "get_decision_ledger",
    "get_decision_counterfactuals",
    "get_purchase_status",
    "propose_purchase_request",
    "propose_plan_selection",
    "request_purchase_approval",
)

SEIL_TOOL_NAMES = (
    "web_search",
    "search_senso_evidence",
    "search_seller_products",
    "get_seller_product_view",
    "get_seller_pack_draft",
    "get_seller_pack_exports",
    "get_engagement_requirement_brief",
    "propose_pack_claim",
    "propose_fit_rule",
    "propose_anti_fit_rule",
    "request_pack_review",
)


def commerce_tool_registry() -> dict[str, object]:
    return {
        "web_search": WebSearchTool(search_context_size="medium", external_web_access=True),
        "get_purchase_request": get_purchase_request,
        "get_purchase_brief": get_purchase_brief,
        "get_stack_snapshot": get_stack_snapshot,
        "get_decision_view": get_decision_view,
        "get_decision_ledger": get_decision_ledger,
        "get_decision_counterfactuals": get_decision_counterfactuals,
        "get_purchase_status": get_purchase_status,
        "propose_purchase_request": propose_purchase_request,
        "propose_plan_selection": propose_plan_selection,
        "request_purchase_approval": request_purchase_approval,
        "search_seller_products": search_seller_products,
        "get_seller_product_view": get_seller_product_view,
        "get_seller_pack_draft": get_seller_pack_draft,
        "get_seller_pack_exports": get_seller_pack_exports,
        "get_engagement_requirement_brief": get_engagement_requirement_brief,
        "propose_pack_claim": propose_pack_claim,
        "propose_fit_rule": propose_fit_rule,
        "propose_anti_fit_rule": propose_anti_fit_rule,
        "request_pack_review": request_pack_review,
    }
