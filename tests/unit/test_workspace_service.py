from __future__ import annotations

import pytest
from sira_agents.commerce_tools import SEIL_TOOL_NAMES, SIRA_TOOL_NAMES
from sira_agents.runtime import AgentRunContext, AgentRunRequest, AgentRunResult
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


class _CaptureRuntime:
    def __init__(self) -> None:
        self.request: AgentRunRequest | None = None

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        self.request = request
        return AgentRunResult(
            output={
                "message": "ok",
                "mission_state": "EXPLORING",
                "plan": [],
                "claims": [],
                "events": [],
                "artifacts": [],
                "tasks": [],
                "attention": None,
                "continue_autonomously": False,
                "show_product_ids": [],
            }
        )


class _UnexpectedRuntime:
    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        raise AssertionError("a greeting must not start the commerce agent")


def test_catalog_is_derived_from_published_product_evidence() -> None:
    service = WorkspaceService(DemoFixtureBundle.load(), api_key="unused", model="test")

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
async def test_chat_fails_clearly_when_provider_is_not_configured() -> None:
    service = WorkspaceService(DemoFixtureBundle.load(), api_key="", model="test")

    with pytest.raises(ApiProblem) as raised:
        await service.chat(
            WorkspaceChatCreate(message="Show me products"),
            run_context=_run_context(service),
        )

    assert raised.value.code == "AGENT_PROVIDER_NOT_CONFIGURED"
    assert raised.value.status_code == 503


@pytest.mark.asyncio
async def test_injected_bedrock_runtime_does_not_require_an_openai_key() -> None:
    runtime = _CaptureRuntime()
    service = WorkspaceService(
        DemoFixtureBundle.load(),
        api_key="",
        model="test",
        runtime=runtime,
        runtime_provider="bedrock",
    )

    result = await service.chat(
        WorkspaceChatCreate(message="Help me understand my options"),
        run_context=_run_context(service),
    )

    assert result["message"] == "ok"
    assert runtime.request is not None


@pytest.mark.asyncio
async def test_greeting_is_short_and_does_not_start_commerce_agent() -> None:
    service = WorkspaceService(DemoFixtureBundle.load(), api_key="configured", model="test")
    service.runtime = _UnexpectedRuntime()  # type: ignore[assignment]

    result = await service.chat(
        WorkspaceChatCreate(message="hi"),
        run_context=_run_context(service),
    )

    assert result["message"] == "Hi! What would you like help buying?"
    assert result["follow_up_required"] is False
    assert result["products"] == []
    assert result["tool_calls"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "expected_tools"),
    [("sira", SIRA_TOOL_NAMES), ("seil", SEIL_TOOL_NAMES)],
)
async def test_chat_uses_the_role_specific_tool_allowlist(
    mode: str, expected_tools: tuple[str, ...]
) -> None:
    service = WorkspaceService(
        DemoFixtureBundle.load(),
        api_key="configured",  # pragma: allowlist secret - inert test value
        model="test",
        workflow_service=object(),
        seller_evidence_service=object(),
    )
    runtime = _CaptureRuntime()
    service.runtime = runtime  # type: ignore[assignment]
    context = AgentRunContext(
        organization_id="org_consultco",
        actor_id="actor",
        actor_roles=frozenset({"seller_editor"}),
        permissions=frozenset(
            {"can_view_context", "can_submit_request", "can_select_recommendation"}
        ),
        party="SELLER" if mode == "seil" else "BUYER",
        services=service.agent_services(),
    )

    await service.chat(
        WorkspaceChatCreate(message="Help", mode=mode),
        run_context=context,
    )

    assert runtime.request is not None
    assert runtime.request.allowed_tools == expected_tools
    assert runtime.request.run_context is context
    assert runtime.request.authority_mode.value == "MISSION_OPERATOR"
