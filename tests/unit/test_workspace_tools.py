from __future__ import annotations

import pytest
from sira_agents.runtime import AgentRunContext
from sira_agents.workspace_tools import get_catalog_product, search_catalog
from sira_api.fixtures import DemoFixtureBundle
from sira_api.workspace_service import WorkspaceService


def _context(*, permitted: bool = True) -> AgentRunContext:
    service = WorkspaceService(DemoFixtureBundle.load(), api_key="unused", model="test")
    return AgentRunContext(
        organization_id="org_consultco",
        actor_id="actor_requester",
        permissions=frozenset({"can_view_context"}) if permitted else frozenset(),
        services={"workspace_catalog": service},
    )


def test_catalog_search_is_bounded_and_uses_published_facts() -> None:
    results = search_catalog(_context(), query="meeting", limit=2)

    assert len(results) == 2
    assert {result.id for result in results}.issubset(
        {
            "product_fixture_a",
            "product_fixture_b",
            "product_fixture_c",
            "product_fixture_d",
        }
    )


def test_catalog_lookup_uses_exact_server_owned_id() -> None:
    result = get_catalog_product(_context(), product_id="product_fixture_d")

    assert result is not None
    assert result.id == "product_fixture_d"
    assert get_catalog_product(_context(), product_id="missing") is None


def test_catalog_tools_reauthorize_local_run_context() -> None:
    with pytest.raises(PermissionError, match="can_view_context"):
        search_catalog(_context(permitted=False))
