"""Bounded capture-decide-authorize-execute-checkpoint-compose loop."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.cognitive_repository import CognitiveRepository, CognitiveRunSnapshot
from persistence.models import CognitiveRun
from sira_agents.cognitive_runtime import CognitiveRuntime
from sira_agents.context_assembler import ContextAssembler
from sira_agents.kernel_models import (
    ContextManifest,
    FailSafely,
    FailureCode,
    Party,
    Principal,
    ProposedToolCall,
    ProposeTools,
    ToolManifest,
    TurnBudget,
    TurnDecision,
    UserEvent,
)
from sira_agents.response_composer import ComposedResponse, ResponseComposer
from sira_agents.tool_broker import ToolBroker, ToolDenied

ToolHandler = Callable[[Mapping[str, Any]], Awaitable[dict[str, Any]]]
ResultT = TypeVar("ResultT")


class RuntimeDatabase(Protocol):
    async def run_retryable(
        self,
        organization_id: str,
        work: Callable[[AsyncSession], Awaitable[ResultT]],
        *,
        max_attempts: int = 5,
        base_delay_seconds: float = 0.025,
    ) -> ResultT: ...


@dataclass(frozen=True, slots=True)
class TurnCommand:
    organization_id: str
    actor_id: str
    principal: Principal
    party: Party
    purpose: str
    conversation_id: str
    turn_id: str
    idempotency_key: str
    message: str
    available_tools: tuple[str, ...] = ()
    recent_messages: tuple[dict[str, Any], ...] = ()
    private_context: dict[str, Any] = field(default_factory=dict)
    exchange_projection: dict[str, Any] = field(default_factory=dict)
    budget: TurnBudget = field(default_factory=TurnBudget)


@dataclass(frozen=True, slots=True)
class TurnResult:
    run_id: str
    status: str
    message: str
    duplicate: bool = False


@dataclass(slots=True)
class RunEngine:
    database: RuntimeDatabase
    runtime: CognitiveRuntime
    broker: ToolBroker
    handlers: Mapping[str, ToolHandler]
    composer: ResponseComposer = field(default_factory=ResponseComposer)
    assembler: ContextAssembler | None = None

    async def process(self, command: TurnCommand) -> TurnResult:
        run, duplicate = await self._capture(command)
        if duplicate and run.status in {"COMPLETED", "FAILED", "WAITING", "CANCELLED"}:
            return await self._existing_result(command.organization_id, run.id)

        manifest = (
            self.assembler.assemble(
                principal=command.principal,
                party=command.party,
                organization_id=command.organization_id,
                actor_id=command.actor_id,
                purpose=command.purpose,
                conversation_id=command.conversation_id,
                turn_id=command.turn_id,
                current_message=command.message,
                recent_messages=command.recent_messages,
                private_context=command.private_context,
                exchange_projection=command.exchange_projection,
                requested_tools=command.available_tools,
            )
            if self.assembler is not None
            else ContextManifest(
                principal=command.principal,
                party=command.party,
                organization_id=command.organization_id,
                actor_id=command.actor_id,
                purpose=command.purpose,
                conversation_id=command.conversation_id,
                turn_id=command.turn_id,
                current_message=command.message,
                recent_messages=command.recent_messages,
                exchange_projection=command.exchange_projection,
                available_tools=command.available_tools,
                budget=command.budget,
            ).sealed()
        )
        await self._bind_manifest(command.organization_id, run.id, manifest)

        tool_results: list[dict[str, Any]] = []
        mutations_used = 0
        for model_call in range(1, command.budget.max_model_calls + 1):
            decision_manifest = manifest
            if tool_results:
                decision_manifest = manifest.model_copy(
                    update={
                        "exchange_projection": {
                            **manifest.exchange_projection,
                            "authorized_tool_results": tool_results,
                        },
                        "manifest_hash": None,
                    }
                ).sealed()
            try:
                async with asyncio.timeout(command.budget.timeout_seconds):
                    decision = await self.runtime.decide(decision_manifest)
            except TimeoutError:
                return await self._fail(
                    command.organization_id,
                    run.id,
                    FailureCode.PROVIDER_UNAVAILABLE,
                    "I couldn't finish in time. Your confirmed work is saved; please try again.",
                    retryable=True,
                )
            except (ValidationError, ValueError):
                if model_call < command.budget.max_model_calls:
                    continue
                return await self._fail(
                    command.organization_id,
                    run.id,
                    FailureCode.INVALID_DECISION,
                    "I couldn't complete that safely. Please try again.",
                    retryable=True,
                )

            await self._record_decision(command.organization_id, run.id, decision)
            if not isinstance(decision, ProposeTools):
                composed = self.composer.compose(decision)
                await self._finish(command.organization_id, run.id, composed, decision)
                return TurnResult(run.id, composed.terminal_status, composed.message, duplicate)

            tool_results = []
            for call in decision.calls:
                try:
                    tool = self.broker.authorize(
                        call,
                        decision_manifest,
                        stage="evaluating",
                        mutations_used=mutations_used,
                    )
                    invocation_id = await self._authorize_tool(
                        command.organization_id, run.id, call, tool
                    )
                    output = await self._execute(tool, call.arguments)
                    await self._complete_tool(
                        command.organization_id, run.id, invocation_id, tool, output
                    )
                    tool_results.append(
                        {
                            "call_id": call.call_id,
                            "tool_name": call.tool_name,
                            "contract_version": call.contract_version,
                            "output": output,
                        }
                    )
                    if tool.risk.value == "mutation":
                        mutations_used += 1
                except ToolDenied:
                    return await self._fail(
                        command.organization_id,
                        run.id,
                        FailureCode.TOOL_DENIED,
                        (
                            "I don't have permission to do that. "
                            "I can continue with an allowed option."
                        ),
                    )
                except TimeoutError:
                    return await self._fail(
                        command.organization_id,
                        run.id,
                        FailureCode.TOOL_TIMEOUT,
                        "That action didn't respond in time. Your confirmed work is saved.",
                        retryable=True,
                    )

        return await self._fail(
            command.organization_id,
            run.id,
            FailureCode.BUDGET_EXHAUSTED,
            "I need a fresh turn to continue. Everything confirmed so far is saved.",
            retryable=True,
        )

    async def cancel(self, organization_id: str, run_id: str) -> None:
        async def work(session: AsyncSession) -> None:
            repository = CognitiveRepository(session, organization_id)
            run = await repository.get(run_id, lock=True)
            if run.status == "CANCELLED":
                return
            await repository.cancel(run)
            await repository.append_user_event(
                run,
                UserEvent(kind="could_not_complete", message="This work was cancelled."),
            )

        await self.database.run_retryable(organization_id, work)

    async def _capture(self, command: TurnCommand) -> tuple[CognitiveRun, bool]:
        async def work(session: AsyncSession) -> tuple[CognitiveRun, bool]:
            repository = CognitiveRepository(session, command.organization_id)
            before = await session.scalar(
                select(CognitiveRun.id).where(
                    CognitiveRun.organization_id == command.organization_id,
                    CognitiveRun.actor_id == command.actor_id,
                    CognitiveRun.idempotency_key == command.idempotency_key,
                )
            )
            run = await repository.capture(
                principal=command.principal.value,
                actor_id=command.actor_id,
                conversation_id=command.conversation_id,
                turn_id=command.turn_id,
                idempotency_key=command.idempotency_key,
                purpose=command.purpose,
                input_text=command.message,
                budget=command.budget,
            )
            return run, bool(before)

        return await self.database.run_retryable(command.organization_id, work)

    async def _bind_manifest(
        self, organization_id: str, run_id: str, manifest: ContextManifest
    ) -> None:
        async def work(session: AsyncSession) -> None:
            repository = CognitiveRepository(session, organization_id)
            run = await repository.get(run_id, lock=True)
            if run.manifest_hash is None:
                await repository.bind_manifest(run, manifest)
            elif run.manifest_hash != manifest.manifest_hash:
                raise ValueError("run is already bound to another context manifest")

        await self.database.run_retryable(organization_id, work)

    async def _record_decision(
        self, organization_id: str, run_id: str, decision: TurnDecision
    ) -> None:
        async def work(session: AsyncSession) -> None:
            repository = CognitiveRepository(session, organization_id)
            run = await repository.get(run_id, lock=True)
            await repository.record_decision(run, decision)
            await repository.checkpoint(
                run, projection={"last_decision": decision.model_dump(mode="json")}
            )

        await self.database.run_retryable(organization_id, work)

    async def _authorize_tool(
        self,
        organization_id: str,
        run_id: str,
        call: ProposedToolCall,
        tool: ToolManifest,
    ) -> str:
        async def work(session: AsyncSession) -> str:
            repository = CognitiveRepository(session, organization_id)
            run = await repository.get(run_id, lock=True)
            invocation = await repository.request_tool(
                run,
                call_id=call.call_id,
                tool_name=call.tool_name,
                contract_version=call.contract_version,
                risk=tool.risk,
                arguments=call.arguments,
            )
            await repository.authorize_tool(invocation)
            return invocation.id

        return await self.database.run_retryable(organization_id, work)

    async def _execute(self, tool: ToolManifest, arguments: Mapping[str, Any]) -> dict[str, Any]:
        handler = self.handlers.get(tool.name)
        if handler is None:
            raise ToolDenied("TOOL_HANDLER_MISSING")
        async with asyncio.timeout(tool.timeout_seconds):
            output = await handler(arguments)
        self.broker.validate_output(tool, output)
        return output

    async def _complete_tool(
        self,
        organization_id: str,
        run_id: str,
        invocation_id: str,
        tool: ToolManifest,
        output: dict[str, Any],
    ) -> None:
        async def work(session: AsyncSession) -> None:
            repository = CognitiveRepository(session, organization_id)
            run = await repository.get(run_id, lock=True)
            snapshot = await repository.snapshot(run)
            invocation = next(item for item in snapshot.tools if item.id == invocation_id)
            await repository.complete_tool(invocation, output=output)
            await repository.append_step(
                run,
                kind="TOOL_RESULT",
                status="COMPLETED",
                payload={"tool_name": tool.name, "output_hash": invocation.output_hash},
            )
            await repository.checkpoint(run, projection={"completed_tool": tool.name})

        await self.database.run_retryable(organization_id, work)

    async def _finish(
        self,
        organization_id: str,
        run_id: str,
        composed: ComposedResponse,
        decision: TurnDecision,
    ) -> None:
        async def work(session: AsyncSession) -> None:
            repository = CognitiveRepository(session, organization_id)
            run = await repository.get(run_id, lock=True)
            failure_code = decision.code.value if isinstance(decision, FailSafely) else None
            await repository.finish(
                run,
                status=composed.terminal_status,
                message=composed.message,
                event=composed.event,
                failure_code=failure_code,
            )
            await repository.checkpoint(run, projection={"status": composed.terminal_status})

        await self.database.run_retryable(organization_id, work)

    async def _fail(
        self,
        organization_id: str,
        run_id: str,
        code: FailureCode,
        message: str,
        *,
        retryable: bool = False,
    ) -> TurnResult:
        decision = FailSafely(kind="fail_safely", code=code, message=message, retryable=retryable)
        composed = self.composer.compose(decision)
        await self._finish(organization_id, run_id, composed, decision)
        return TurnResult(run_id, "FAILED", message)

    async def _existing_result(self, organization_id: str, run_id: str) -> TurnResult:
        async def work(session: AsyncSession) -> CognitiveRunSnapshot:
            repository = CognitiveRepository(session, organization_id)
            run = await repository.get(run_id)
            return await repository.snapshot(run)

        snapshot = await self.database.run_retryable(organization_id, work)
        output = next(
            (
                step.payload.get("message")
                for step in reversed(snapshot.steps)
                if "message" in step.payload
            ),
            "Your previous result is available.",
        )
        return TurnResult(run_id, snapshot.run.status, str(output), duplicate=True)
