from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

import pytest
from sira_agents.experiment import ExperimentResult, ExperimentSpec
from sira_worker.experiment_coordinator import ExperimentCoordinator

from domain import content_hash
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


class TrackingDatabase:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.transaction_depth = 0

    @asynccontextmanager
    async def transaction(self, organization_id: str) -> AsyncIterator[Any]:
        self.transaction_depth += 1
        try:
            async with self.database.transaction(organization_id) as session:
                yield session
        finally:
            self.transaction_depth -= 1

    async def run_retryable(self, organization_id: str, work: Any) -> Any:
        async with self.transaction(organization_id) as session:
            return await work(session)


class ObservingRunner:
    def __init__(self, database: TrackingDatabase, *, fail: bool = False) -> None:
        self.database = database
        self.fail = fail
        self.calls = 0

    async def run(self, spec: ExperimentSpec) -> ExperimentResult:
        self.calls += 1
        assert self.database.transaction_depth == 0
        if self.fail:
            raise TimeoutError("provider timeout should not be persisted")
        observations = [
            {"signal": "grounded", "value": True, "source": f"fixture:{spec.fixture_id}"}
        ]
        return ExperimentResult(
            status="COMPLETED",
            observations=observations,
            limitations=["synthetic fixture"],
            artifact_hash=content_hash(observations),
        )


def _experiment_spec() -> ExperimentSpec:
    return ExperimentSpec(
        candidate_id="product_fixture_a",
        fixture_id="qualification_case_v1",
        procedure=["Evaluate labelled evidence"],
        environment={"locale": "en-US"},
        success_signals=[
            {"name": "grounded", "measurement": "Citations resolve", "success_threshold": "true"}
        ],
        replay_command=["evaluate", "qualification_case_v1"],
    )


async def test_experiment_is_durable_idempotent_and_runs_outside_transaction() -> None:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    tracked = TrackingDatabase(database)
    runner = ObservingRunner(tracked)
    coordinator = ExperimentCoordinator(database=cast(Database, tracked), runner=runner)

    try:
        async with database.transaction("org_agent") as session:
            session.add(Organization(id="org_agent", name="Agent Org"))
            repository = MissionRepository(session, "org_agent")
            await repository.create(
                mission_id="msn_experiment",
                actor_id="actor_1",
                mode="SIRA",
                goal="Evaluate a candidate",
                budget={"experiments_remaining": 1},
            )

        first_id = await coordinator.execute(
            organization_id="org_agent",
            mission_id="msn_experiment",
            actor_id="actor_1",
            spec=_experiment_spec(),
        )
        second_id = await coordinator.execute(
            organization_id="org_agent",
            mission_id="msn_experiment",
            actor_id="actor_1",
            spec=_experiment_spec(),
        )

        async with database.transaction("org_agent") as session:
            repository = MissionRepository(session, "org_agent")
            mission = await repository.get_for_actor("msn_experiment", "actor_1")
            snapshot = await repository.snapshot(mission)

        assert first_id == second_id
        assert runner.calls == 1
        assert snapshot.experiments[0].status == "COMPLETED"
        assert snapshot.experiments[0].result_artifact_id == snapshot.artifacts[0].id
        assert snapshot.mission.budget["experiments_remaining"] == 0
        assert [event.event_type for event in snapshot.events] == [
            "mission.created",
            "experiment.planned",
            "experiment.started",
            "experiment.finished",
        ]
    finally:
        await database.close()


async def test_experiment_records_sanitized_failure_then_reraises() -> None:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    tracked = TrackingDatabase(database)
    coordinator = ExperimentCoordinator(
        database=cast(Database, tracked), runner=ObservingRunner(tracked, fail=True)
    )

    try:
        async with database.transaction("org_agent") as session:
            session.add(Organization(id="org_agent", name="Agent Org"))
            repository = MissionRepository(session, "org_agent")
            await repository.create(
                mission_id="msn_failed_experiment",
                actor_id="actor_1",
                mode="SIRA",
                goal="Evaluate a candidate",
                budget={"experiments_remaining": 1},
            )

        with pytest.raises(TimeoutError, match="provider timeout"):
            await coordinator.execute(
                organization_id="org_agent",
                mission_id="msn_failed_experiment",
                actor_id="actor_1",
                spec=_experiment_spec(),
            )

        async with database.transaction("org_agent") as session:
            repository = MissionRepository(session, "org_agent")
            mission = await repository.get_for_actor("msn_failed_experiment", "actor_1")
            snapshot = await repository.snapshot(mission)
        assert snapshot.experiments[0].status == "FAILED"
        assert snapshot.experiments[0].limitations == ["runner_failure:TimeoutError"]
        assert "provider timeout" not in str(snapshot.model_context())
    finally:
        await database.close()
