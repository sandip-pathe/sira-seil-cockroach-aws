from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from sira_agents.kernel_models import Party, Principal, ToolManifest, ToolRisk
from sira_agents.runtime import AgentRunContext
from sira_api.cognitive_engine import RunEngine, TurnResult
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


def test_kernel_context_uses_durable_history_without_promoting_stale_mission_goal() -> None:
    service = WorkspaceService(
        DemoFixtureBundle.load(),
        database=cast(object, SimpleNamespace()),
    )
    body = WorkspaceChatCreate(
        message="What can you help me do?",
        history=[],
    )
    recent, summary, unresolved, private = service._kernel_context(
        body=body,
        model_context={
            "mission": {
                "id": "msn_123",
                "goal": "Hi",
                "state": "ORIENTING",
                "version": 2,
                "plan": [],
                "world_model": {"unknowns": []},
            },
            "recent_events": [
                {"type": "user.message", "payload": {"message": "Hi"}},
                {
                    "type": "assistant.message",
                    "payload": {"message": "Hello. How can I help?"},
                },
                {
                    "type": "user.message",
                    "payload": {"message": "What can you help me do?"},
                },
            ],
        },
    )

    assert recent == (
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello. How can I help?"},
    )
    assert summary == "State: ORIENTING"
    assert unresolved == ()
    assert "goal" not in private["mission"]


def test_search_observations_are_projected_into_existing_product_cards() -> None:
    result = TurnResult(
        run_id="run-1",
        status="COMPLETED",
        message="I found one published option.",
        tool_calls=("search_published_products",),
        tool_results=(
            {
                "call_id": "search-1",
                "tool_name": "search_published_products",
                "contract_version": "v1",
                "output": {
                    "results": [
                        {
                            "product_id": "product-1",
                            "name": "Product One",
                            "seller": "Seller One",
                            "summary": "Published evidence.",
                        }
                    ]
                },
            },
        ),
    )

    products = WorkspaceService._products_from_tool_results(result)

    assert products[0]["id"] == "product-1"
    assert products[0]["evidence_status"] == "PUBLISHED"
    assert products[0]["seller_attested"] is True
