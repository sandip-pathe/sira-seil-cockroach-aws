from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any, cast

from sira_agents.cognitive_runtime import DeterministicCognitiveRuntime
from sira_agents.kernel_models import (
    ContextManifest,
    Party,
    Principal,
    ToolManifest,
    ToolRisk,
    TurnBudget,
)
from sira_agents.tool_broker import ToolBroker
from sira_api.cognitive_engine import RunEngine, RuntimeDatabase, TurnCommand

from persistence.cognitive_repository import CognitiveRepository
from persistence.database import Database, DatabaseSettings
from persistence.models import Base, Organization


async def _database() -> Database:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.transaction("org-buyer") as session:
        session.add(Organization(id="org-buyer", name="Buyer"))
    return database


def _command(**changes: object) -> TurnCommand:
    values: dict[str, object] = {
        "organization_id": "org-buyer",
        "actor_id": "buyer-1",
        "principal": Principal.SIRA,
        "party": Party.BUYER,
        "purpose": "software_selection",
        "conversation_id": "conversation-1",
        "turn_id": "turn-1",
        "idempotency_key": "submit-1",
        "message": "Help us compare meeting assistants.",
    }
    values.update(changes)
    return TurnCommand(**values)  # type: ignore[arg-type]


def _read_tool() -> ToolManifest:
    return ToolManifest(
        name="read_evidence",
        contract_version="v1",
        description="Read a permitted evidence record.",
        allowed_principals=frozenset({Principal.SIRA}),
        allowed_parties=frozenset({Party.BUYER}),
        purposes=frozenset({"software_selection"}),
        allowed_stages=frozenset({"evaluating"}),
        risk=ToolRisk.READ,
        input_schema={
            "type": "object",
            "properties": {"evidence_id": {"type": "string"}},
            "required": ["evidence_id"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {"claim": {"type": "string"}},
            "required": ["claim"],
            "additionalProperties": False,
        },
    )


async def test_engine_captures_executes_checkpoints_and_composes() -> None:
    database = await _database()
    observed: list[Mapping[str, Any]] = []

    async def read_evidence(
        arguments: Mapping[str, Any], _manifest: ContextManifest
    ) -> dict[str, Any]:
        observed.append(arguments)
        return {"claim": "Recordings can remain in the EU."}

    runtime = DeterministicCognitiveRuntime(
        decisions=[
            {
                "kind": "propose_tools",
                "calls": [
                    {
                        "call_id": "call-1",
                        "tool_name": "read_evidence",
                        "contract_version": "v1",
                        "arguments": {"evidence_id": "evidence-1"},
                    }
                ],
            },
            {"kind": "respond", "message": "Both options support EU-hosted recordings."},
        ]
    )
    tool = _read_tool()
    engine = RunEngine(
        database=cast(RuntimeDatabase, database),
        runtime=runtime,
        broker=ToolBroker({tool.name: tool}),
        handlers={tool.name: read_evidence},
    )
    try:
        result = await engine.process(_command(available_tools=(tool.name,)))
        duplicate = await engine.process(_command(available_tools=(tool.name,)))
        assert result.status == "COMPLETED"
        assert result.message == "Both options support EU-hosted recordings."
        assert duplicate == result.__class__(
            run_id=result.run_id,
            status="COMPLETED",
            message=result.message,
            duplicate=True,
        )
        assert observed == [{"evidence_id": "evidence-1"}]
        assert len(runtime.calls) == 2
        assert runtime.calls[0].tool_contracts[0]["name"] == "read_evidence"
        assert runtime.calls[0].tool_contracts[0]["input_schema"] == tool.input_schema
        assert runtime.calls[1].exchange_projection["authorized_tool_results"][0]["output"] == {
            "claim": "Recordings can remain in the EU."
        }

        async with database.transaction("org-buyer") as session:
            repository = CognitiveRepository(session, "org-buyer")
            run = await repository.get(result.run_id)
            snapshot = await repository.snapshot(run)
        assert [item.kind for item in snapshot.steps] == [
            "INPUT",
            "DECISION",
            "TOOL_RESULT",
            "DECISION",
            "OUTPUT",
        ]
        assert snapshot.tools[0].status == "COMPLETED"
        assert len(snapshot.checkpoints) == 4
        assert "tool" not in snapshot.user_events[-1].message.lower()
    finally:
        await database.close()


async def test_engine_clarifies_without_calling_business_tools() -> None:
    database = await _database()
    runtime = DeterministicCognitiveRuntime(
        decisions=[
            {
                "kind": "clarify",
                "question": "Must all recordings stay in the EU?",
                "reason": "This can change which products qualify.",
            }
        ]
    )
    engine = RunEngine(
        database=cast(RuntimeDatabase, database),
        runtime=runtime,
        broker=ToolBroker({}),
        handlers={},
    )
    try:
        result = await engine.process(_command(message="hello"))
        assert result.status == "WAITING"
        assert result.message == "Must all recordings stay in the EU?"
    finally:
        await database.close()


async def test_engine_turns_denial_timeout_and_malformed_output_into_safe_results() -> None:
    for suffix, runtime, expected in (
        (
            "denied",
            DeterministicCognitiveRuntime(
                decisions=[
                    {
                        "kind": "propose_tools",
                        "calls": [
                            {
                                "call_id": "call-1",
                                "tool_name": "read_evidence",
                                "contract_version": "v1",
                                "arguments": {"evidence_id": "evidence-1"},
                            }
                        ],
                    }
                ]
            ),
            "I don't have permission",
        ),
        (
            "malformed",
            DeterministicCognitiveRuntime(
                decisions=[{"kind": "respond", "message": "ok", "mission_state": "COMPLETED"}] * 3
            ),
            "complete that safely",
        ),
    ):
        database = await _database()
        engine = RunEngine(
            database=cast(RuntimeDatabase, database),
            runtime=runtime,
            broker=ToolBroker({_read_tool().name: _read_tool()}),
            handlers={},
        )
        try:
            result = await engine.process(
                _command(turn_id=f"turn-{suffix}", idempotency_key=f"submit-{suffix}")
            )
            assert result.status == "FAILED"
            assert expected in result.message
            assert "TOOL_" not in result.message
        finally:
            await database.close()

    class SlowRuntime:
        async def decide(self, _manifest: object) -> object:
            await asyncio.sleep(0.02)
            return {"kind": "respond", "message": "late"}

    database = await _database()
    engine = RunEngine(
        database=cast(RuntimeDatabase, database),
        runtime=cast(Any, SlowRuntime()),
        broker=ToolBroker({}),
        handlers={},
    )
    try:
        result = await engine.process(
            _command(
                turn_id="turn-timeout",
                idempotency_key="submit-timeout",
                budget=TurnBudget(timeout_seconds=0.001),
            )
        )
        assert result.status == "FAILED"
        assert "finish in time" in result.message
    finally:
        await database.close()


async def test_engine_cancel_is_durable_and_idempotent() -> None:
    database = await _database()
    engine = RunEngine(
        database=cast(RuntimeDatabase, database),
        runtime=DeterministicCognitiveRuntime(
            decisions=[
                {
                    "kind": "clarify",
                    "question": "Which region?",
                    "reason": "Region affects eligibility.",
                }
            ]
        ),
        broker=ToolBroker({}),
        handlers={},
    )
    try:
        result = await engine.process(_command())
        await engine.cancel("org-buyer", result.run_id)
        await engine.cancel("org-buyer", result.run_id)
        async with database.transaction("org-buyer") as session:
            run = await CognitiveRepository(session, "org-buyer").get(result.run_id)
        assert run.status == "CANCELLED"
        assert run.cancelled_at is not None
    finally:
        await database.close()
