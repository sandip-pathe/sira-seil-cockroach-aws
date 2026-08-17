"""Cockroach-backed journal for contextual runtime turns."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sira_agents.kernel_models import ContextManifest, ToolRisk, TurnBudget, UserEvent
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domain import content_hash

from .models import (
    CognitiveCheckpoint,
    CognitiveRun,
    CognitiveStep,
    CognitiveToolInvocation,
    CognitiveUserEvent,
)
from .repositories import PersistenceConflict, RecordNotFound, new_id


@dataclass(frozen=True, slots=True)
class CognitiveRunSnapshot:
    run: CognitiveRun
    steps: tuple[CognitiveStep, ...]
    checkpoints: tuple[CognitiveCheckpoint, ...]
    tools: tuple[CognitiveToolInvocation, ...]
    user_events: tuple[CognitiveUserEvent, ...]


class CognitiveRepository:
    def __init__(self, session: AsyncSession, organization_id: str) -> None:
        self.session = session
        self.organization_id = organization_id

    async def capture(
        self,
        *,
        principal: str,
        actor_id: str,
        conversation_id: str,
        turn_id: str,
        idempotency_key: str,
        purpose: str,
        input_text: str,
        budget: TurnBudget,
    ) -> CognitiveRun:
        request_hash = content_hash(
            {
                "principal": principal,
                "actor_id": actor_id,
                "conversation_id": conversation_id,
                "turn_id": turn_id,
                "purpose": purpose,
                "input_text": input_text,
            }
        )
        existing = (
            await self.session.execute(
                select(CognitiveRun).where(
                    CognitiveRun.organization_id == self.organization_id,
                    CognitiveRun.actor_id == actor_id,
                    CognitiveRun.idempotency_key == idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.input_hash != request_hash:
                raise PersistenceConflict("idempotency key was reused with different input")
            return existing
        run = CognitiveRun(
            id=new_id("crun"),
            organization_id=self.organization_id,
            principal=principal,
            actor_id=actor_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
            idempotency_key=idempotency_key,
            purpose=purpose,
            input_text=input_text,
            input_hash=request_hash,
            manifest_hash=None,
            status="CAPTURED",
            version=1,
            budget=budget.model_dump(mode="json"),
            failure_code=None,
            cancelled_at=None,
        )
        self.session.add(run)
        await self.session.flush()
        await self.append_step(
            run,
            kind="INPUT",
            status="RECORDED",
            payload={"input_hash": request_hash},
        )
        await self.append_user_event(
            run,
            UserEvent(kind="message_received", message="Your message is saved."),
        )
        return run

    async def get(self, run_id: str, *, lock: bool = False) -> CognitiveRun:
        statement = select(CognitiveRun).where(
            CognitiveRun.organization_id == self.organization_id,
            CognitiveRun.id == run_id,
        )
        if lock:
            statement = statement.with_for_update()
        run = (await self.session.execute(statement)).scalar_one_or_none()
        if run is None:
            raise RecordNotFound("cognitive run was not found")
        return run

    async def append_step(
        self,
        run: CognitiveRun,
        *,
        kind: str,
        status: str,
        payload: dict[str, Any],
    ) -> CognitiveStep:
        sequence = (
            int(
                await self.session.scalar(
                    select(func.coalesce(func.max(CognitiveStep.sequence), 0)).where(
                        CognitiveStep.organization_id == self.organization_id,
                        CognitiveStep.run_id == run.id,
                    )
                )
                or 0
            )
            + 1
        )
        step = CognitiveStep(
            id=new_id("cstep"),
            organization_id=self.organization_id,
            run_id=run.id,
            sequence=sequence,
            kind=kind,
            status=status,
            payload=payload,
            payload_hash=content_hash(payload),
        )
        self.session.add(step)
        await self.session.flush()
        return step

    async def append_user_event(self, run: CognitiveRun, event: UserEvent) -> CognitiveUserEvent:
        sequence = (
            int(
                await self.session.scalar(
                    select(func.coalesce(func.max(CognitiveUserEvent.sequence), 0)).where(
                        CognitiveUserEvent.organization_id == self.organization_id,
                        CognitiveUserEvent.run_id == run.id,
                    )
                )
                or 0
            )
            + 1
        )
        record = CognitiveUserEvent(
            id=new_id("cuevt"),
            organization_id=self.organization_id,
            run_id=run.id,
            sequence=sequence,
            kind=event.kind,
            message=event.message,
            retryable=event.retryable,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def bind_manifest(self, run: CognitiveRun, manifest: ContextManifest) -> None:
        if manifest.manifest_hash is None or manifest.manifest_hash != manifest.calculate_hash():
            raise PersistenceConflict("only a sealed context manifest can be bound")
        if manifest.principal.value != run.principal or manifest.actor_id != run.actor_id:
            raise PersistenceConflict("context principal does not own this run")
        run.manifest_hash = manifest.manifest_hash
        run.status = "DECIDING"
        run.version += 1

    async def request_tool(
        self,
        run: CognitiveRun,
        *,
        call_id: str,
        tool_name: str,
        contract_version: str,
        risk: ToolRisk,
        arguments: dict[str, Any],
    ) -> CognitiveToolInvocation:
        existing = (
            await self.session.execute(
                select(CognitiveToolInvocation).where(
                    CognitiveToolInvocation.organization_id == self.organization_id,
                    CognitiveToolInvocation.run_id == run.id,
                    CognitiveToolInvocation.call_id == call_id,
                )
            )
        ).scalar_one_or_none()
        arguments_hash = content_hash(arguments)
        if existing is not None:
            if existing.arguments_hash != arguments_hash:
                raise PersistenceConflict("tool call id was reused with different arguments")
            return existing
        invocation = CognitiveToolInvocation(
            id=new_id("ctool"),
            organization_id=self.organization_id,
            run_id=run.id,
            call_id=call_id,
            tool_name=tool_name,
            contract_version=contract_version,
            risk=risk.value,
            arguments=arguments,
            arguments_hash=arguments_hash,
            status="REQUESTED",
            output=None,
            output_hash=None,
            safe_error_code=None,
        )
        self.session.add(invocation)
        await self.session.flush()
        return invocation

    async def checkpoint(
        self, run: CognitiveRun, *, projection: dict[str, Any]
    ) -> CognitiveCheckpoint:
        sequence = (
            int(
                await self.session.scalar(
                    select(func.coalesce(func.max(CognitiveCheckpoint.sequence), 0)).where(
                        CognitiveCheckpoint.organization_id == self.organization_id,
                        CognitiveCheckpoint.run_id == run.id,
                    )
                )
                or 0
            )
            + 1
        )
        record = CognitiveCheckpoint(
            id=new_id("ccp"),
            organization_id=self.organization_id,
            run_id=run.id,
            sequence=sequence,
            run_version=run.version,
            projection=projection,
            content_hash=content_hash(projection),
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def cancel(self, run: CognitiveRun) -> None:
        if run.status in {"COMPLETED", "FAILED", "CANCELLED"}:
            return
        run.status = "CANCELLED"
        run.cancelled_at = datetime.now(UTC)
        run.version += 1

    async def snapshot(self, run: CognitiveRun) -> CognitiveRunSnapshot:
        async def records(model: Any) -> tuple[Any, ...]:
            values = (
                await self.session.execute(
                    select(model)
                    .where(model.organization_id == self.organization_id, model.run_id == run.id)
                    .order_by(model.sequence if hasattr(model, "sequence") else model.created_at)
                )
            ).scalars()
            return tuple(values)

        return CognitiveRunSnapshot(
            run=run,
            steps=await records(CognitiveStep),
            checkpoints=await records(CognitiveCheckpoint),
            tools=await records(CognitiveToolInvocation),
            user_events=await records(CognitiveUserEvent),
        )
