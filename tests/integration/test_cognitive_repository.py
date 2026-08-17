from __future__ import annotations

import pytest
from sira_agents.kernel_models import ContextManifest, ToolRisk, TurnBudget, UserEvent

from persistence.cognitive_repository import CognitiveRepository
from persistence.database import Database, DatabaseSettings
from persistence.models import Base, Organization
from persistence.repositories import PersistenceConflict


async def _database() -> Database:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.transaction("org-buyer") as session:
        session.add(Organization(id="org-buyer", name="Buyer"))
    return database


async def test_cognitive_turn_is_idempotent_resumable_and_user_safe() -> None:
    database = await _database()
    try:
        async with database.transaction("org-buyer") as session:
            repository = CognitiveRepository(session, "org-buyer")
            run = await repository.capture(
                principal="SIRA",
                actor_id="buyer-1",
                conversation_id="conversation-1",
                turn_id="turn-1",
                idempotency_key="submit-1",
                purpose="software_selection",
                input_text="Help me compare meeting assistants.",
                budget=TurnBudget(),
            )
            duplicate = await repository.capture(
                principal="SIRA",
                actor_id="buyer-1",
                conversation_id="conversation-1",
                turn_id="turn-1",
                idempotency_key="submit-1",
                purpose="software_selection",
                input_text="Help me compare meeting assistants.",
                budget=TurnBudget(),
            )
            assert duplicate.id == run.id
            manifest = ContextManifest(
                principal="SIRA",
                organization_id="org-buyer",
                actor_id="buyer-1",
                purpose="software_selection",
                conversation_id="conversation-1",
                turn_id="turn-1",
                current_message=run.input_text,
                available_tools=("read_evidence",),
            ).sealed()
            await repository.bind_manifest(run, manifest)
            tool = await repository.request_tool(
                run,
                call_id="call-1",
                tool_name="read_evidence",
                contract_version="v1",
                risk=ToolRisk.READ,
                arguments={"evidence_id": "evidence-1"},
            )
            same_tool = await repository.request_tool(
                run,
                call_id="call-1",
                tool_name="read_evidence",
                contract_version="v1",
                risk=ToolRisk.READ,
                arguments={"evidence_id": "evidence-1"},
            )
            assert same_tool.id == tool.id
            await repository.checkpoint(run, projection={"next": "compose"})
            await repository.append_user_event(
                run,
                UserEvent(
                    kind="clarification_needed",
                    message="One detail could change the comparison.",
                ),
            )

        async with database.transaction("org-buyer") as session:
            repository = CognitiveRepository(session, "org-buyer")
            resumed = await repository.get(run.id)
            snapshot = await repository.snapshot(resumed)
        assert [step.kind for step in snapshot.steps] == ["INPUT"]
        assert snapshot.checkpoints[0].projection == {"next": "compose"}
        assert [event.kind for event in snapshot.user_events] == [
            "message_received",
            "clarification_needed",
        ]
        assert snapshot.run.manifest_hash == manifest.manifest_hash
    finally:
        await database.close()


async def test_cognitive_idempotency_key_rejects_changed_input() -> None:
    database = await _database()
    try:
        async with database.transaction("org-buyer") as session:
            repository = CognitiveRepository(session, "org-buyer")
            common = {
                "principal": "SIRA",
                "actor_id": "buyer-1",
                "conversation_id": "conversation-1",
                "turn_id": "turn-1",
                "idempotency_key": "submit-1",
                "purpose": "software_selection",
                "budget": TurnBudget(),
            }
            await repository.capture(input_text="first", **common)
            with pytest.raises(PersistenceConflict, match="different input"):
                await repository.capture(input_text="changed", **common)
    finally:
        await database.close()
