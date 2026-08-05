from __future__ import annotations

from persistence.database import Database, DatabaseSettings
from persistence.mission_repository import MissionRepository
from persistence.models import Base, Organization


async def test_mission_event_artifact_and_checkpoint_are_resumable() -> None:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    try:
        async with database.transaction("org_agent") as session:
            session.add(Organization(id="org_agent", name="Agent Org"))

        async with database.transaction("org_agent") as session:
            repository = MissionRepository(session, "org_agent")
            mission = await repository.create(
                mission_id="msn_00000000000000000000000000000001",
                actor_id="actor_1",
                mode="SIRA",
                goal="Choose meeting intelligence for ten people",
                budget={"model_turns": 16},
            )
            await repository.append_event(
                mission,
                event_type="agent.researched",
                event_key="research:1",
                actor_type="ROOT_AGENT",
                actor_id="sira-root-agent",
                payload={"summary": "Compared published evidence"},
            )
            await repository.add_artifact(
                mission,
                kind="comparison",
                title="Candidate comparison",
                authority="VERIFIED",
                payload={"candidate_ids": ["product_fixture_a"]},
                source_refs=[{"type": "product", "id": "product_fixture_a"}],
                created_by="sira-root-agent",
            )
            await repository.checkpoint(mission)

        async with database.transaction("org_agent") as session:
            repository = MissionRepository(session, "org_agent")
            mission = await repository.get_for_actor(
                "msn_00000000000000000000000000000001", "actor_1"
            )
            snapshot = await repository.snapshot(mission)

        assert [event.sequence for event in snapshot.events] == [1, 2]
        assert snapshot.artifacts[0].kind == "comparison"
        assert snapshot.checkpoint is not None
        assert snapshot.model_context()["checkpoint"]["mission_version"] == 1
    finally:
        await database.close()
