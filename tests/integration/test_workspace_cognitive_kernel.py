from __future__ import annotations

import pytest
from sira_agents.cognitive_runtime import DeterministicCognitiveRuntime
from sira_agents.run_engine import RunEngine
from sira_agents.runtime import AgentRunContext
from sira_agents.tool_broker import ToolBroker
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
        api_key="",
        model="test",
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
