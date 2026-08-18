"""Authenticated read tools for the typed cognitive kernel."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from sira_agents.kernel_models import ContextManifest, Party, Principal, ToolManifest, ToolRisk

KernelHandler = Callable[[Mapping[str, Any], ContextManifest], Awaitable[dict[str, Any]]]
SellerRole = Literal["SELLER_EDITOR", "SELLER_REVIEWER", "PLATFORM_OPERATOR"]


class WorkflowReads(Protocol):
    async def get_purchase_request(
        self, organization_id: str, request_id: str
    ) -> dict[str, Any]: ...
    async def get_purchase_brief(self, organization_id: str, request_id: str) -> dict[str, Any]: ...
    async def stackfile(self, organization_id: str) -> dict[str, Any]: ...
    async def decision_view(self, organization_id: str, request_id: str) -> dict[str, Any]: ...
    async def get_decision(self, organization_id: str, decision_id: str) -> dict[str, Any]: ...
    async def counterfactuals(self, organization_id: str, decision_id: str) -> dict[str, Any]: ...
    async def purchase_status(self, organization_id: str, intent_id: str) -> dict[str, Any]: ...
    async def get_requirement_brief(
        self,
        organization_id: str,
        brief_id: str,
        *,
        actor_id: str,
        actor_party: str | None,
    ) -> dict[str, Any]: ...


class SellerReads(Protocol):
    async def search_products(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_role: SellerRole,
        query: str | None,
    ) -> dict[str, Any]: ...
    async def get_product_view(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_role: SellerRole,
        product_id: str,
    ) -> dict[str, Any]: ...
    async def get_draft(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_role: SellerRole,
        draft_id: str,
    ) -> dict[str, Any]: ...
    async def get_exports(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_role: SellerRole,
        version_id: str,
    ) -> dict[str, Any]: ...


class QualificationReads(Protocol):
    async def search_marketplace(
        self,
        organization_id: str,
        *,
        category: str,
        query: str,
        limit: int,
    ) -> dict[str, Any]: ...

    async def marketplace_product(
        self, organization_id: str, product_id: str
    ) -> dict[str, Any]: ...


def _object_schema(properties: dict[str, Any], *, required: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


_OUTPUT = {"type": "object", "additionalProperties": True}


@dataclass(frozen=True, slots=True)
class KernelToolSet:
    catalog: dict[str, ToolManifest]
    handlers: dict[str, KernelHandler]

    def names(self, principal: Principal) -> frozenset[str]:
        return frozenset(
            name for name, tool in self.catalog.items() if principal in tool.allowed_principals
        )


@dataclass(frozen=True, slots=True)
class KernelToolDispatcher:
    workflow: WorkflowReads
    seller: SellerReads
    qualification: QualificationReads

    @staticmethod
    def _seller_role(manifest: ContextManifest) -> SellerRole:
        roles = {role.casefold() for role in manifest.actor_roles}
        if "platform_operator" in roles:
            return "PLATFORM_OPERATOR"
        if "seller_reviewer" in roles:
            return "SELLER_REVIEWER"
        if "seller_editor" in roles or "seller_viewer" in roles:
            return "SELLER_EDITOR"
        raise PermissionError("SEIL read tools require a seller role")

    async def execute(
        self, name: str, arguments: Mapping[str, Any], manifest: ContextManifest
    ) -> dict[str, Any]:
        organization_id = manifest.organization_id
        if name == "search_published_products":
            return await self.qualification.search_marketplace(
                organization_id,
                category="business-software",
                query=str(arguments.get("query") or ""),
                limit=int(arguments.get("limit") or 8),
            )
        if name == "get_published_product":
            return await self.qualification.marketplace_product(
                organization_id, str(arguments["product_id"])
            )
        if name == "get_purchase_request":
            return await self.workflow.get_purchase_request(
                organization_id, str(arguments["request_id"])
            )
        if name == "get_purchase_brief":
            return await self.workflow.get_purchase_brief(
                organization_id, str(arguments["request_id"])
            )
        if name == "get_stack_snapshot":
            return await self.workflow.stackfile(organization_id)
        if name == "get_decision_view":
            return await self.workflow.decision_view(organization_id, str(arguments["request_id"]))
        if name == "get_decision_ledger":
            return await self.workflow.get_decision(organization_id, str(arguments["decision_id"]))
        if name == "get_decision_counterfactuals":
            return await self.workflow.counterfactuals(
                organization_id, str(arguments["decision_id"])
            )
        if name == "get_purchase_status":
            return await self.workflow.purchase_status(
                organization_id, str(arguments["purchase_intent_id"])
            )
        role = self._seller_role(manifest)
        if name == "search_seller_products":
            return await self.seller.search_products(
                organization_id=organization_id,
                actor_id=manifest.actor_id,
                actor_role=role,
                query=str(arguments.get("query") or "").strip() or None,
            )
        if name == "get_seller_product_view":
            return await self.seller.get_product_view(
                organization_id=organization_id,
                actor_id=manifest.actor_id,
                actor_role=role,
                product_id=str(arguments["product_id"]),
            )
        if name == "get_seller_pack_draft":
            return await self.seller.get_draft(
                organization_id=organization_id,
                actor_id=manifest.actor_id,
                actor_role=role,
                draft_id=str(arguments["draft_id"]),
            )
        if name == "get_seller_pack_exports":
            return await self.seller.get_exports(
                organization_id=organization_id,
                actor_id=manifest.actor_id,
                actor_role=role,
                version_id=str(arguments["version_id"]),
            )
        if name == "get_engagement_requirement_brief":
            return await self.workflow.get_requirement_brief(
                organization_id,
                str(arguments["brief_id"]),
                actor_id=manifest.actor_id,
                actor_party=manifest.party.value,
            )
        raise PermissionError("kernel tool is not implemented")


def build_kernel_tool_set(
    *, workflow: WorkflowReads, seller: SellerReads, qualification: QualificationReads
) -> KernelToolSet:
    dispatcher = KernelToolDispatcher(workflow, seller, qualification)
    string_id = {"type": "string", "minLength": 1, "maxLength": 128}
    definitions: tuple[tuple[str, str, Principal, Party, str, dict[str, Any]], ...] = (
        (
            "search_published_products",
            "Search current buyer-visible published products using bounded semantic retrieval.",
            Principal.SIRA,
            Party.BUYER,
            "software_selection",
            _object_schema(
                {
                    "query": {"type": "string", "maxLength": 1000},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                required=("query",),
            ),
        ),
        (
            "get_published_product",
            "Read one published product projection.",
            Principal.SIRA,
            Party.BUYER,
            "software_selection",
            _object_schema({"product_id": string_id}, required=("product_id",)),
        ),
        (
            "get_purchase_request",
            "Read one buyer purchase request.",
            Principal.SIRA,
            Party.BUYER,
            "software_selection",
            _object_schema({"request_id": string_id}, required=("request_id",)),
        ),
        (
            "get_purchase_brief",
            "Read one private buyer purchase brief.",
            Principal.SIRA,
            Party.BUYER,
            "software_selection",
            _object_schema({"request_id": string_id}, required=("request_id",)),
        ),
        (
            "get_stack_snapshot",
            "Read the buyer organization's current stack.",
            Principal.SIRA,
            Party.BUYER,
            "software_selection",
            _object_schema({}),
        ),
        (
            "get_decision_view",
            "Read one current action-neutral decision view.",
            Principal.SIRA,
            Party.BUYER,
            "software_selection",
            _object_schema({"request_id": string_id}, required=("request_id",)),
        ),
        (
            "get_decision_ledger",
            "Read one immutable decision ledger.",
            Principal.SIRA,
            Party.BUYER,
            "software_selection",
            _object_schema({"decision_id": string_id}, required=("decision_id",)),
        ),
        (
            "get_decision_counterfactuals",
            "Read deterministic counterfactuals for one decision.",
            Principal.SIRA,
            Party.BUYER,
            "software_selection",
            _object_schema({"decision_id": string_id}, required=("decision_id",)),
        ),
        (
            "get_purchase_status",
            "Read approval and external handoff status without acting.",
            Principal.SIRA,
            Party.BUYER,
            "software_selection",
            _object_schema({"purchase_intent_id": string_id}, required=("purchase_intent_id",)),
        ),
        (
            "search_seller_products",
            "Search products visible to the authenticated seller.",
            Principal.SEIL,
            Party.SELLER,
            "seller_evidence",
            _object_schema({"query": {"type": "string", "maxLength": 1000}}),
        ),
        (
            "get_seller_product_view",
            "Read one seller-owned product view.",
            Principal.SEIL,
            Party.SELLER,
            "seller_evidence",
            _object_schema({"product_id": string_id}, required=("product_id",)),
        ),
        (
            "get_seller_pack_draft",
            "Read one seller-owned evidence pack draft.",
            Principal.SEIL,
            Party.SELLER,
            "seller_evidence",
            _object_schema({"draft_id": string_id}, required=("draft_id",)),
        ),
        (
            "get_seller_pack_exports",
            "Read exports for one published seller pack.",
            Principal.SEIL,
            Party.SELLER,
            "seller_evidence",
            _object_schema({"version_id": string_id}, required=("version_id",)),
        ),
        (
            "get_engagement_requirement_brief",
            "Read the released requirement brief for one seller engagement.",
            Principal.SEIL,
            Party.SELLER,
            "seller_evidence",
            _object_schema({"brief_id": string_id}, required=("brief_id",)),
        ),
    )
    catalog: dict[str, ToolManifest] = {}
    handlers: dict[str, KernelHandler] = {}
    for name, description, principal, party, purpose, input_schema in definitions:
        catalog[name] = ToolManifest(
            name=name,
            contract_version="v1",
            description=description,
            allowed_principals=frozenset({principal}),
            allowed_parties=frozenset({party}),
            purposes=frozenset({purpose}),
            allowed_stages=frozenset({"evaluating"}),
            risk=ToolRisk.READ,
            input_schema=input_schema,
            output_schema=_OUTPUT,
        )

        async def handler(
            arguments: Mapping[str, Any],
            manifest: ContextManifest,
            *,
            _name: str = name,
        ) -> dict[str, Any]:
            return await dispatcher.execute(_name, arguments, manifest)

        handlers[name] = handler
    return KernelToolSet(catalog=catalog, handlers=handlers)
