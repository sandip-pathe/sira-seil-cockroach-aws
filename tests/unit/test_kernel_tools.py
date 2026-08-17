from __future__ import annotations

from typing import Any

import pytest
from sira_agents.kernel_models import ContextManifest, Party, Principal
from sira_agents.kernel_tools import build_kernel_tool_set


class FakeWorkflow:
    async def get_purchase_request(self, organization_id: str, request_id: str) -> dict[str, Any]:
        return {"organization_id": organization_id, "request_id": request_id}

    async def get_purchase_brief(self, organization_id: str, request_id: str) -> dict[str, Any]:
        return {"organization_id": organization_id, "request_id": request_id}

    async def stackfile(self, organization_id: str) -> dict[str, Any]:
        return {"organization_id": organization_id}

    async def decision_view(self, organization_id: str, request_id: str) -> dict[str, Any]:
        return {"organization_id": organization_id, "request_id": request_id}

    async def get_decision(self, organization_id: str, decision_id: str) -> dict[str, Any]:
        return {"organization_id": organization_id, "decision_id": decision_id}

    async def counterfactuals(self, organization_id: str, decision_id: str) -> dict[str, Any]:
        return {"organization_id": organization_id, "decision_id": decision_id}

    async def purchase_status(self, organization_id: str, intent_id: str) -> dict[str, Any]:
        return {"organization_id": organization_id, "intent_id": intent_id}

    async def get_requirement_brief(
        self,
        organization_id: str,
        brief_id: str,
        *,
        actor_id: str,
        actor_party: str | None,
    ) -> dict[str, Any]:
        return {
            "organization_id": organization_id,
            "brief_id": brief_id,
            "actor_id": actor_id,
            "actor_party": actor_party,
        }


class FakeSeller:
    async def search_products(self, **kwargs: Any) -> dict[str, Any]:
        return dict(kwargs)

    async def get_product_view(self, **kwargs: Any) -> dict[str, Any]:
        return dict(kwargs)

    async def get_draft(self, **kwargs: Any) -> dict[str, Any]:
        return dict(kwargs)

    async def get_exports(self, **kwargs: Any) -> dict[str, Any]:
        return dict(kwargs)


class FakeQualification:
    async def search_marketplace(self, organization_id: str, **kwargs: Any) -> dict[str, Any]:
        return {"organization_id": organization_id, **kwargs}

    async def marketplace_product(
        self, organization_id: str, product_id: str
    ) -> dict[str, Any]:
        return {"organization_id": organization_id, "product_id": product_id}


def _manifest(principal: Principal, *, roles: tuple[str, ...] = ()) -> ContextManifest:
    return ContextManifest(
        principal=principal,
        party=Party.BUYER if principal is Principal.SIRA else Party.SELLER,
        organization_id="org-1",
        actor_id="actor-1",
        actor_roles=roles,
        purpose="software_selection" if principal is Principal.SIRA else "seller_evidence",
        conversation_id="conversation-1",
        turn_id="turn-1",
        current_message="Find the relevant record.",
    ).sealed()


async def test_kernel_tools_bind_reads_to_the_manifest_identity() -> None:
    tools = build_kernel_tool_set(
        workflow=FakeWorkflow(), seller=FakeSeller(), qualification=FakeQualification()
    )
    buyer_result = await tools.handlers["search_published_products"](
        {"query": "meeting intelligence", "limit": 3}, _manifest(Principal.SIRA)
    )
    assert buyer_result == {
        "organization_id": "org-1",
        "category": "business-software",
        "query": "meeting intelligence",
        "limit": 3,
    }
    seller_result = await tools.handlers["search_seller_products"](
        {"query": "Luma"}, _manifest(Principal.SEIL, roles=("seller_editor",))
    )
    assert seller_result["organization_id"] == "org-1"
    assert seller_result["actor_id"] == "actor-1"
    assert seller_result["actor_role"] == "SELLER_EDITOR"


async def test_kernel_tools_reject_a_seller_without_a_bound_role() -> None:
    tools = build_kernel_tool_set(
        workflow=FakeWorkflow(), seller=FakeSeller(), qualification=FakeQualification()
    )
    with pytest.raises(PermissionError, match="seller role"):
        await tools.handlers["search_seller_products"](
            {"query": "Luma"}, _manifest(Principal.SEIL)
        )
