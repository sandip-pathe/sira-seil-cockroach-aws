from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from sira_agents.cognitive_runtime import DeterministicCognitiveRuntime
from sira_agents.kernel_models import ContextManifest, Party, Principal, ToolManifest, ToolRisk
from sira_agents.runtime import AgentRunContext
from sira_agents.tool_broker import ToolBroker
from sira_api.cognitive_engine import RunEngine
from sira_api.fixtures import DemoFixtureBundle
from sira_api.workspace_schemas import WorkspaceChatCreate
from sira_api.workspace_service import WorkspaceService

from persistence.database import Database, DatabaseSettings
from persistence.models import Base, Organization


@pytest.mark.parametrize(
    ("mode", "organization_id", "party", "message"),
    [
        ("sira", "org-buyer", "BUYER", "What outcome are you trying to achieve?"),
        ("seil", "org-seller", "SELLER", "Which product should we prepare evidence for?"),
    ],
)
async def test_existing_workspace_routes_both_principals_through_cognitive_kernel(
    mode: str,
    organization_id: str,
    party: str,
    message: str,
) -> None:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.transaction(organization_id) as session:
        session.add(Organization(id=organization_id, name=party.title()))
    runtime = DeterministicCognitiveRuntime(
        decisions=[
            {
                "kind": "clarify",
                "question": message,
                "reason": "This answer can change the next decision.",
            }
        ]
    )
    service = WorkspaceService(
        DemoFixtureBundle.load(),
        database=database,
        cognitive_engine=RunEngine(
            database=database,
            runtime=runtime,
            broker=ToolBroker({}),
            handlers={},
        ),
    )
    context = AgentRunContext(
        organization_id=organization_id,
        actor_id=f"actor-{mode}",
        party=party,
        permissions=frozenset({"can_view_context"}),
        request_id=f"request-{mode}",
    )
    try:
        result = await service.chat(
            WorkspaceChatCreate(mode=mode, message="Help me get started."),
            run_context=context,
        )
        assert result["message"] == message
        assert result["follow_up_required"] is True
        assert result["tool_calls"] == []
        assert runtime.calls[0].principal.value == mode.upper()
        assert result["mission"]["state"] == "PAUSED"
    finally:
        await database.close()


async def test_workspace_projects_completed_kernel_tools_into_existing_run_details() -> None:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.transaction("org-seller") as session:
        session.add(Organization(id="org-seller", name="Seller"))

    runtime = DeterministicCognitiveRuntime(
        decisions=[
            {
                "kind": "propose_tools",
                "calls": [
                    {
                        "call_id": "products-1",
                        "tool_name": "search_seller_products",
                        "contract_version": "v1",
                        "arguments": {"query": ""},
                    }
                ],
            },
            {"kind": "respond", "message": "I found one product in your workspace."},
        ]
    )
    tool = ToolManifest(
        name="search_seller_products",
        contract_version="v1",
        description="Search products visible to this seller.",
        allowed_principals=frozenset({Principal.SEIL}),
        allowed_parties=frozenset({Party.SELLER}),
        purposes=frozenset({"seller_evidence"}),
        allowed_stages=frozenset({"evaluating"}),
        risk=ToolRisk.READ,
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        output_schema={"type": "object", "additionalProperties": True},
    )

    async def search_products(
        _arguments: Mapping[str, Any], _manifest: ContextManifest
    ) -> dict[str, Any]:
        return {"results": [{"id": "product-1", "name": "Luma"}]}

    service = WorkspaceService(
        DemoFixtureBundle.load(),
        database=database,
        cognitive_engine=RunEngine(
            database=database,
            runtime=runtime,
            broker=ToolBroker({tool.name: tool}),
            handlers={tool.name: search_products},
        ),
    )
    context = AgentRunContext(
        organization_id="org-seller",
        actor_id="seller-1",
        actor_roles=frozenset({"seller_editor"}),
        party="SELLER",
        permissions=frozenset({"seller_editor"}),
        request_id="request-tools",
    )
    try:
        result = await service.chat(
            WorkspaceChatCreate(mode="seil", message="Show my products."),
            run_context=context,
        )

        assert result["message"] == "I found one product in your workspace."
        assert result["tool_calls"] == ["search_seller_products"]
        tool_event = next(
            event for event in result["events"] if event["type"] == "agent.tool.completed"
        )
        assert tool_event["summary"] == "Used search seller products"
        assert tool_event["details"]["verified"] is True
    finally:
        await database.close()
