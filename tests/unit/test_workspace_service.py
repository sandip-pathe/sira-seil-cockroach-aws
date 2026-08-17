from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from sira_agents.kernel_models import Party, Principal, ToolManifest, ToolRisk
from sira_agents.runtime import AgentRunContext
from sira_api.cognitive_engine import RunEngine
from sira_api.errors import ApiProblem
from sira_api.fixtures import DemoFixtureBundle
from sira_api.workspace_schemas import WorkspaceChatCreate
from sira_api.workspace_service import WorkspaceService


def _run_context(service: WorkspaceService) -> AgentRunContext:
    return AgentRunContext(
        organization_id="org_consultco",
        actor_id="actor_requester",
        permissions=frozenset({"can_view_context"}),
        services={"workspace_catalog": service},
    )


def _tool(name: str, principal: Principal) -> ToolManifest:
    return ToolManifest(
        name=name,
        contract_version="v1",
        description=name,
        allowed_principals=frozenset({principal}),
        allowed_parties=frozenset({Party.BUYER, Party.SELLER}),
        purposes=frozenset({"commerce"}),
        allowed_stages=frozenset({"evaluating"}),
        risk=ToolRisk.READ,
        input_schema={"type": "object", "additionalProperties": False},
        output_schema={"type": "object", "additionalProperties": True},
    )


def test_catalog_is_derived_from_published_product_evidence() -> None:
    service = WorkspaceService(DemoFixtureBundle.load())

    catalog = service.catalog()

    assert len(catalog) == 4
    assert {product["id"] for product in catalog} == {
        "product_fixture_a",
        "product_fixture_b",
        "product_fixture_c",
        "product_fixture_d",
    }
    assert service.product("product_fixture_d") is not None
    assert service.product("missing") is None


@pytest.mark.asyncio
async def test_chat_fails_clearly_when_cognitive_runtime_is_not_configured() -> None:
    service = WorkspaceService(DemoFixtureBundle.load())

    with pytest.raises(ApiProblem) as raised:
        await service.chat(
            WorkspaceChatCreate(message="Show me products"),
            run_context=_run_context(service),
        )

    assert raised.value.code == "AGENT_PROVIDER_NOT_CONFIGURED"
    assert raised.value.status_code == 503


@pytest.mark.parametrize(
    ("mode", "expected"),
    [("sira", ("buyer_search",)), ("seil", ("seller_search",))],
)
def test_tool_visibility_is_derived_from_typed_principal_manifests(
    mode: str, expected: tuple[str, ...]
) -> None:
    catalog = {
        "buyer_search": _tool("buyer_search", Principal.SIRA),
        "seller_search": _tool("seller_search", Principal.SEIL),
    }
    engine = cast(RunEngine, SimpleNamespace(broker=SimpleNamespace(catalog=catalog)))
    service = WorkspaceService(DemoFixtureBundle.load(), cognitive_engine=engine)

    assert service._allowed_tools(mode) == expected
