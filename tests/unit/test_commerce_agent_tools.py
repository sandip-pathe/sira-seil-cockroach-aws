from __future__ import annotations

import pytest
from sira_agents.commerce_tools import (
    SEIL_TOOL_NAMES,
    SIRA_TOOL_NAMES,
    _proposal,
    _seller_role,
    commerce_tool_registry,
)
from sira_agents.runtime import AgentRunContext
from sira_agents.workspace_tools import workspace_tool_registry


def test_every_role_tool_is_registered_strict_and_bounded_by_allowlist() -> None:
    registry = {**workspace_tool_registry(), **commerce_tool_registry()}

    assert (set(SIRA_TOOL_NAMES) | set(SEIL_TOOL_NAMES)).issubset(registry)
    assert not {"pay", "charge", "approve", "publish", "sql", "http", "shell"}.intersection(
        registry
    )
    for name, tool in registry.items():
        assert tool.name == name
        if name == "web_search":
            continue
        assert tool.strict_json_schema is True
        assert tool.params_json_schema["additionalProperties"] is False


def test_proposals_bind_actor_and_tenant_without_gaining_authority() -> None:
    context = AgentRunContext(
        organization_id="org_consultco",
        actor_id="actor_requester",
        permissions=frozenset({"can_submit_request"}),
    )

    proposal = _proposal(context, "PURCHASE_REQUEST", {"intent": "Buy meeting software"})

    assert proposal.payload["organization_id"] == "org_consultco"
    assert proposal.payload["actor_id"] == "actor_requester"
    assert proposal.advisory_only is True
    assert proposal.ranking_effect is False
    assert proposal.requires_human_action is True


def test_seil_tools_require_an_exact_seller_identity_and_role() -> None:
    buyer = AgentRunContext(
        organization_id="org_consultco",
        actor_id="actor_requester",
        actor_roles=frozenset({"seller_editor"}),
        party="BUYER",
    )
    seller = AgentRunContext(
        organization_id="org_seller",
        actor_id="actor_seller",
        actor_roles=frozenset({"seller_editor"}),
        party="SELLER",
    )

    with pytest.raises(PermissionError, match="seller identity"):
        _seller_role(buyer)
    assert _seller_role(seller) == "SELLER_EDITOR"
