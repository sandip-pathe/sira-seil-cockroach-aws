"""Durable experiment orchestration with network work outside SQL transactions."""

from __future__ import annotations

from dataclasses import dataclass

from sira_agents.experiment import ExperimentResult, ExperimentRunner, ExperimentSpec
from sqlalchemy.ext.asyncio import AsyncSession

from domain import content_hash
from persistence import Database
from persistence.mission_repository import MissionRepository


@dataclass(slots=True)
class ExperimentCoordinator:
    database: Database
    runner: ExperimentRunner

    async def execute(
        self,
        *,
        organization_id: str,
        mission_id: str,
        actor_id: str,
        spec: ExperimentSpec,
    ) -> str:
        """Plan/start, invoke remotely, then atomically persist a terminal result."""

        async def claim(session: AsyncSession) -> tuple[str, bool]:
            repository = MissionRepository(session, organization_id)
            mission = await repository.get_for_actor(mission_id, actor_id, lock=True)
            experiment = await repository.plan_experiment(mission, spec=spec)
            experiment = await repository.get_experiment(mission, experiment.id, lock=True)
            if experiment.status in {"COMPLETED", "FAILED", "CANCELLED"}:
                return experiment.id, False
            if experiment.status == "RUNNING":
                return experiment.id, False
            await repository.start_experiment(mission, experiment)
            return experiment.id, True

        experiment_id, should_run = await self.database.run_retryable(organization_id, claim)
        if not should_run:
            return experiment_id

        try:
            result = await self.runner.run(spec)
        except Exception as error:
            safe_result = ExperimentResult(
                status="FAILED",
                limitations=[f"runner_failure:{type(error).__name__}"],
                artifact_hash=content_hash(
                    {"experiment_id": experiment_id, "failure_type": type(error).__name__}
                ),
            )
            await self._finish(
                organization_id=organization_id,
                mission_id=mission_id,
                actor_id=actor_id,
                experiment_id=experiment_id,
                result=safe_result,
            )
            raise

        await self._finish(
            organization_id=organization_id,
            mission_id=mission_id,
            actor_id=actor_id,
            experiment_id=experiment_id,
            result=result,
        )
        return experiment_id

    async def _finish(
        self,
        *,
        organization_id: str,
        mission_id: str,
        actor_id: str,
        experiment_id: str,
        result: ExperimentResult,
    ) -> None:
        async def finish(session: AsyncSession) -> None:
            repository = MissionRepository(session, organization_id)
            mission = await repository.get_for_actor(mission_id, actor_id, lock=True)
            experiment = await repository.get_experiment(mission, experiment_id, lock=True)
            await repository.finish_experiment(mission, experiment, result=result)

        await self.database.run_retryable(organization_id, finish)
