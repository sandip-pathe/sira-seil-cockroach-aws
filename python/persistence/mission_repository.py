"""Canonical persistence boundary for resumable agent missions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sira_agents.experiment import ExperimentResult, ExperimentSpec
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domain import content_hash

from .models import (
    AgentCapabilityGrant,
    AgentEffect,
    AgentExperiment,
    AgentMission,
    AgentMissionArtifact,
    AgentMissionCheckpoint,
    AgentMissionEvent,
    AgentMissionTask,
)
from .repositories import PersistenceConflict, RecordNotFound, new_id


@dataclass(frozen=True, slots=True)
class MissionSnapshot:
    mission: AgentMission
    events: tuple[AgentMissionEvent, ...]
    tasks: tuple[AgentMissionTask, ...]
    artifacts: tuple[AgentMissionArtifact, ...]
    experiments: tuple[AgentExperiment, ...]
    grants: tuple[AgentCapabilityGrant, ...]
    effects: tuple[AgentEffect, ...]
    checkpoint: AgentMissionCheckpoint | None

    def model_context(self) -> dict[str, Any]:
        """Return a bounded, credential-free projection suitable for a model."""

        return {
            "mission": {
                "id": self.mission.id,
                "goal": self.mission.goal,
                "state": self.mission.state,
                "version": self.mission.version,
                "budget": self.mission.budget,
                "plan": self.mission.plan,
                "world_model": self.mission.world_model,
                "stop_reason": self.mission.stop_reason,
            },
            "recent_events": [
                {
                    "sequence": item.sequence,
                    "type": item.event_type,
                    "actor_type": item.actor_type,
                    "payload": item.payload,
                    "occurred_at": item.occurred_at.astimezone(UTC).isoformat(),
                }
                for item in self.events[-24:]
            ],
            "open_tasks": [
                {
                    "id": item.id,
                    "kind": item.kind,
                    "title": item.title,
                    "status": item.status,
                    "owner_type": item.owner_type,
                    "assigned_role": item.assigned_role,
                    "budget": item.budget,
                    "safe_error_code": item.safe_error_code,
                }
                for item in self.tasks
                if item.status not in {"COMPLETED", "CANCELLED"}
            ],
            "artifacts": [
                {
                    "id": item.id,
                    "kind": item.kind,
                    "title": item.title,
                    "status": item.status,
                    "authority": item.authority,
                    "payload": item.payload,
                    "source_refs": item.source_refs,
                    "content_hash": item.content_hash,
                }
                for item in self.artifacts[-20:]
            ],
            "experiments": [
                {
                    "id": item.id,
                    "candidate_id": item.candidate_id,
                    "status": item.status,
                    "procedure": item.procedure,
                    "success_signals": item.success_signals,
                    "observations": item.observations,
                    "limitations": item.limitations,
                    "replay_spec": item.replay_spec,
                }
                for item in self.experiments[-10:]
            ],
            "active_capabilities": [
                {
                    "id": item.id,
                    "capability": item.capability,
                    "scope": item.scope,
                    "expires_at": item.expires_at.astimezone(UTC).isoformat(),
                    "remaining_uses": item.max_uses - item.uses,
                }
                for item in self.grants
                if item.status == "ACTIVE"
            ],
            "protected_effects": [
                {
                    "id": item.id,
                    "effect_type": item.effect_type,
                    "status": item.status,
                    "approval_reference": item.approval_reference,
                    "provider_reference": item.provider_reference,
                    "safe_error_code": item.safe_error_code,
                }
                for item in self.effects[-10:]
            ],
            "checkpoint": (
                {
                    "id": self.checkpoint.id,
                    "sequence": self.checkpoint.sequence,
                    "mission_version": self.checkpoint.mission_version,
                    "state": self.checkpoint.state,
                    "projection": self.checkpoint.projection,
                    "unresolved_task_ids": self.checkpoint.unresolved_task_ids,
                }
                if self.checkpoint is not None
                else None
            ),
        }


class MissionRepository:
    """Transaction-scoped repository with append-only mission history."""

    def __init__(self, session: AsyncSession, organization_id: str) -> None:
        self.session = session
        self.organization_id = organization_id

    async def create(
        self,
        *,
        mission_id: str,
        actor_id: str,
        mode: str,
        goal: str,
        budget: dict[str, Any],
    ) -> AgentMission:
        mission = AgentMission(
            id=mission_id,
            organization_id=self.organization_id,
            actor_id=actor_id,
            mode=mode,
            goal=goal,
            state="ORIENTING",
            version=1,
            budget=budget,
            plan={"steps": [], "updated_by": "root_agent"},
            world_model={"claims": [], "unknowns": [], "contradictions": []},
            current_checkpoint_id=None,
            stop_reason=None,
            last_error_code=None,
        )
        self.session.add(mission)
        await self.session.flush()
        await self.append_event(
            mission,
            event_type="mission.created",
            event_key=f"mission-created:{mission.id}",
            actor_type="USER",
            actor_id=actor_id,
            payload={"goal": goal, "mode": mode, "budget": budget},
        )
        return mission

    async def get(self, mission_id: str, *, lock: bool = False) -> AgentMission:
        statement = select(AgentMission).where(
            AgentMission.id == mission_id,
            AgentMission.organization_id == self.organization_id,
        )
        if lock:
            statement = statement.with_for_update()
        mission = (await self.session.execute(statement)).scalar_one_or_none()
        if mission is None:
            raise RecordNotFound("Agent mission was not found")
        return mission

    async def get_for_actor(
        self, mission_id: str, actor_id: str, *, lock: bool = False
    ) -> AgentMission:
        mission = await self.get(mission_id, lock=lock)
        if mission.actor_id != actor_id:
            raise PermissionError("mission belongs to another actor")
        return mission

    async def list_for_actor(self, actor_id: str, *, mode: str) -> tuple[AgentMission, ...]:
        records = (
            (
                await self.session.execute(
                    select(AgentMission)
                    .where(
                        AgentMission.organization_id == self.organization_id,
                        AgentMission.actor_id == actor_id,
                        AgentMission.mode == mode,
                    )
                    .order_by(AgentMission.updated_at.desc())
                )
            )
            .scalars()
            .all()
        )
        return tuple(records)

    async def snapshot(self, mission: AgentMission) -> MissionSnapshot:
        events = tuple(
            (
                await self.session.execute(
                    select(AgentMissionEvent)
                    .where(
                        AgentMissionEvent.organization_id == self.organization_id,
                        AgentMissionEvent.mission_id == mission.id,
                    )
                    .order_by(AgentMissionEvent.sequence)
                )
            )
            .scalars()
            .all()
        )
        tasks = tuple(
            (
                await self.session.execute(
                    select(AgentMissionTask)
                    .where(
                        AgentMissionTask.organization_id == self.organization_id,
                        AgentMissionTask.mission_id == mission.id,
                    )
                    .order_by(AgentMissionTask.created_at)
                )
            )
            .scalars()
            .all()
        )
        artifacts = tuple(
            (
                await self.session.execute(
                    select(AgentMissionArtifact)
                    .where(
                        AgentMissionArtifact.organization_id == self.organization_id,
                        AgentMissionArtifact.mission_id == mission.id,
                    )
                    .order_by(AgentMissionArtifact.created_at)
                )
            )
            .scalars()
            .all()
        )
        experiments = tuple(
            (
                await self.session.execute(
                    select(AgentExperiment)
                    .where(
                        AgentExperiment.organization_id == self.organization_id,
                        AgentExperiment.mission_id == mission.id,
                    )
                    .order_by(AgentExperiment.created_at)
                )
            )
            .scalars()
            .all()
        )
        grants = tuple(
            (
                await self.session.execute(
                    select(AgentCapabilityGrant)
                    .where(
                        AgentCapabilityGrant.organization_id == self.organization_id,
                        AgentCapabilityGrant.mission_id == mission.id,
                    )
                    .order_by(AgentCapabilityGrant.created_at)
                )
            )
            .scalars()
            .all()
        )
        effects = tuple(
            (
                await self.session.execute(
                    select(AgentEffect)
                    .where(
                        AgentEffect.organization_id == self.organization_id,
                        AgentEffect.mission_id == mission.id,
                    )
                    .order_by(AgentEffect.created_at)
                )
            )
            .scalars()
            .all()
        )
        checkpoint = None
        if mission.current_checkpoint_id is not None:
            checkpoint = (
                await self.session.execute(
                    select(AgentMissionCheckpoint).where(
                        AgentMissionCheckpoint.id == mission.current_checkpoint_id,
                        AgentMissionCheckpoint.organization_id == self.organization_id,
                    )
                )
            ).scalar_one_or_none()
        return MissionSnapshot(
            mission=mission,
            events=events,
            tasks=tasks,
            artifacts=artifacts,
            experiments=experiments,
            grants=grants,
            effects=effects,
            checkpoint=checkpoint,
        )

    async def append_event(
        self,
        mission: AgentMission,
        *,
        event_type: str,
        event_key: str,
        actor_type: str,
        actor_id: str,
        payload: dict[str, Any],
    ) -> AgentMissionEvent:
        if mission.organization_id != self.organization_id:
            raise PersistenceConflict("mission event tenant does not match transaction")
        existing = (
            await self.session.execute(
                select(AgentMissionEvent).where(
                    AgentMissionEvent.organization_id == self.organization_id,
                    AgentMissionEvent.event_key == event_key,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.payload_hash != content_hash(payload):
                raise PersistenceConflict("mission event key was reused with another payload")
            return existing
        sequence = (
            int(
                (
                    await self.session.execute(
                        select(func.coalesce(func.max(AgentMissionEvent.sequence), 0)).where(
                            AgentMissionEvent.organization_id == self.organization_id,
                            AgentMissionEvent.mission_id == mission.id,
                        )
                    )
                ).scalar_one()
            )
            + 1
        )
        event = AgentMissionEvent(
            id=new_id("mevt"),
            organization_id=self.organization_id,
            mission_id=mission.id,
            sequence=sequence,
            event_type=event_type,
            event_key=event_key,
            actor_type=actor_type,
            actor_id=actor_id,
            payload=payload,
            payload_hash=content_hash(payload),
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def has_event_key(self, event_key: str) -> bool:
        return (
            await self.session.scalar(
                select(AgentMissionEvent.id).where(
                    AgentMissionEvent.organization_id == self.organization_id,
                    AgentMissionEvent.event_key == event_key,
                )
            )
        ) is not None

    async def add_artifact(
        self,
        mission: AgentMission,
        *,
        kind: str,
        title: str,
        authority: str,
        payload: dict[str, Any],
        source_refs: list[dict[str, Any]],
        created_by: str,
        task_id: str | None = None,
    ) -> AgentMissionArtifact:
        artifact_hash = content_hash(
            {
                "kind": kind,
                "title": title,
                "authority": authority,
                "payload": payload,
                "source_refs": source_refs,
            }
        )
        existing = (
            await self.session.execute(
                select(AgentMissionArtifact).where(
                    AgentMissionArtifact.organization_id == self.organization_id,
                    AgentMissionArtifact.mission_id == mission.id,
                    AgentMissionArtifact.content_hash == artifact_hash,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        artifact = AgentMissionArtifact(
            id=new_id("mart"),
            organization_id=self.organization_id,
            mission_id=mission.id,
            task_id=task_id,
            kind=kind,
            title=title,
            status="READY",
            authority=authority,
            payload=payload,
            source_refs=source_refs,
            content_hash=artifact_hash,
            created_by=created_by,
        )
        self.session.add(artifact)
        await self.session.flush()
        return artifact

    async def add_task(
        self,
        mission: AgentMission,
        *,
        kind: str,
        title: str,
        owner_type: str,
        assigned_role: str | None,
        input_payload: dict[str, Any],
        budget: dict[str, Any],
        parent_task_id: str | None = None,
    ) -> AgentMissionTask:
        task = AgentMissionTask(
            id=new_id("mtask"),
            organization_id=self.organization_id,
            mission_id=mission.id,
            parent_task_id=parent_task_id,
            kind=kind,
            title=title,
            status="PENDING",
            owner_type=owner_type,
            assigned_role=assigned_role,
            input_payload=input_payload,
            budget=budget,
            output_artifact_id=None,
            attempt=0,
            safe_error_code=None,
            deadline_at=None,
        )
        self.session.add(task)
        await self.session.flush()
        return task

    async def plan_experiment(
        self,
        mission: AgentMission,
        *,
        spec: ExperimentSpec,
        task_id: str | None = None,
    ) -> AgentExperiment:
        """Create an idempotent, replayable experiment plan."""

        if mission.organization_id != self.organization_id:
            raise PersistenceConflict("experiment tenant does not match transaction")
        payload = spec.model_dump(mode="json")
        experiment_hash = content_hash(payload)
        existing = (
            await self.session.execute(
                select(AgentExperiment).where(
                    AgentExperiment.organization_id == self.organization_id,
                    AgentExperiment.mission_id == mission.id,
                    AgentExperiment.content_hash == experiment_hash,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        remaining = int(mission.budget.get("experiments_remaining", 0))
        if remaining < 1:
            raise PersistenceConflict("mission experiment budget is exhausted")
        experiment = AgentExperiment(
            id=new_id("mexp"),
            organization_id=self.organization_id,
            mission_id=mission.id,
            task_id=task_id,
            candidate_id=spec.candidate_id,
            status="PLANNED",
            procedure={"fixture_id": spec.fixture_id, "steps": spec.procedure},
            environment=spec.environment,
            success_signals=[item.model_dump(mode="json") for item in spec.success_signals],
            observations=[],
            limitations=[],
            replay_spec={
                "command": spec.replay_command,
                "egress_hosts": spec.egress_hosts,
                "timeout_seconds": spec.timeout_seconds,
                "max_output_bytes": spec.max_output_bytes,
            },
            cost={},
            result_artifact_id=None,
            content_hash=experiment_hash,
            started_at=None,
            completed_at=None,
        )
        self.session.add(experiment)
        mission.budget = {**mission.budget, "experiments_remaining": remaining - 1}
        await self.session.flush()
        await self.append_event(
            mission,
            event_type="experiment.planned",
            event_key=f"experiment-planned:{experiment.id}",
            actor_type="ROOT_AGENT",
            actor_id="sira-root-agent",
            payload={"experiment_id": experiment.id, "spec_hash": experiment_hash},
        )
        return experiment

    async def get_experiment(
        self, mission: AgentMission, experiment_id: str, *, lock: bool = False
    ) -> AgentExperiment:
        statement = select(AgentExperiment).where(
            AgentExperiment.id == experiment_id,
            AgentExperiment.organization_id == self.organization_id,
            AgentExperiment.mission_id == mission.id,
        )
        if lock:
            statement = statement.with_for_update()
        experiment = (await self.session.execute(statement)).scalar_one_or_none()
        if experiment is None:
            raise RecordNotFound("Agent experiment was not found")
        return experiment

    async def start_experiment(
        self, mission: AgentMission, experiment: AgentExperiment
    ) -> AgentExperiment:
        if experiment.status == "RUNNING":
            return experiment
        if experiment.status != "PLANNED":
            raise PersistenceConflict("only a planned experiment can start")
        experiment.status = "RUNNING"
        experiment.started_at = datetime.now(UTC)
        mission.state = "EXPERIMENTING"
        await self.append_event(
            mission,
            event_type="experiment.started",
            event_key=f"experiment-started:{experiment.id}",
            actor_type="SYSTEM",
            actor_id="experiment-coordinator",
            payload={"experiment_id": experiment.id},
        )
        return experiment

    async def finish_experiment(
        self,
        mission: AgentMission,
        experiment: AgentExperiment,
        *,
        result: ExperimentResult,
        cost: dict[str, Any] | None = None,
    ) -> AgentExperiment:
        if experiment.status in {"COMPLETED", "FAILED", "CANCELLED"}:
            if experiment.status != result.status:
                raise PersistenceConflict("experiment already has another terminal result")
            return experiment
        if experiment.status != "RUNNING":
            raise PersistenceConflict("only a running experiment can finish")
        experiment.status = result.status
        experiment.observations = [item.model_dump(mode="json") for item in result.observations]
        experiment.limitations = result.limitations
        experiment.cost = cost or {}
        experiment.completed_at = datetime.now(UTC)
        artifact = await self.add_artifact(
            mission,
            kind="experiment_result",
            title=f"Observed experiment for {experiment.candidate_id}",
            authority="OBSERVED",
            payload={
                "experiment_id": experiment.id,
                "status": result.status,
                "observations": experiment.observations,
                "limitations": result.limitations,
                "logs_reference": result.logs_reference,
                "artifact_hash": result.artifact_hash,
            },
            source_refs=[{"type": "experiment", "id": experiment.id}],
            created_by="experiment-coordinator",
            task_id=experiment.task_id,
        )
        experiment.result_artifact_id = artifact.id
        await self.append_event(
            mission,
            event_type="experiment.finished",
            event_key=f"experiment-finished:{experiment.id}:{result.artifact_hash}",
            actor_type="SYSTEM",
            actor_id="experiment-coordinator",
            payload={
                "experiment_id": experiment.id,
                "status": result.status,
                "result_artifact_id": artifact.id,
                "result_hash": result.artifact_hash,
            },
        )
        return experiment

    async def checkpoint(self, mission: AgentMission) -> AgentMissionCheckpoint:
        snapshot = await self.snapshot(mission)
        sequence = snapshot.events[-1].sequence if snapshot.events else 0
        unresolved = [
            item.id for item in snapshot.tasks if item.status not in {"COMPLETED", "CANCELLED"}
        ]
        projection = {
            "goal": mission.goal,
            "state": mission.state,
            "plan": mission.plan,
            "world_model": mission.world_model,
            "budget": mission.budget,
            "artifact_ids": [item.id for item in snapshot.artifacts],
            "effect_ids": [item.id for item in snapshot.effects],
        }
        checkpoint_hash = content_hash(
            {
                "mission_id": mission.id,
                "sequence": sequence,
                "mission_version": mission.version,
                "projection": projection,
                "unresolved_task_ids": unresolved,
            }
        )
        checkpoint = AgentMissionCheckpoint(
            id=new_id("mcp"),
            organization_id=self.organization_id,
            mission_id=mission.id,
            sequence=sequence,
            mission_version=mission.version,
            state=mission.state,
            projection=projection,
            unresolved_task_ids=unresolved,
            content_hash=checkpoint_hash,
        )
        self.session.add(checkpoint)
        await self.session.flush()
        mission.current_checkpoint_id = checkpoint.id
        mission.updated_at = datetime.now(UTC)
        return checkpoint
