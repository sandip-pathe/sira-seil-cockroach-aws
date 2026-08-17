from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError
from sira_agents.cognitive_runtime import DeterministicCognitiveRuntime
from sira_agents.kernel_models import (
    Clarify,
    ContextManifest,
    Principal,
    ProposedToolCall,
    ToolManifest,
    ToolRisk,
    TurnDecision,
)
from sira_agents.tool_broker import ToolBroker, ToolDenied


def _manifest(**changes: object) -> ContextManifest:
    values: dict[str, object] = {
        "principal": "SIRA",
        "organization_id": "org-buyer",
        "actor_id": "buyer-1",
        "purpose": "software_selection",
        "conversation_id": "conversation-1",
        "turn_id": "turn-1",
        "current_message": "Help us choose meeting intelligence software.",
        "available_tools": ("read_evidence",),
    }
    values.update(changes)
    return ContextManifest.model_validate(values).sealed()


def test_turn_decision_cannot_author_persistent_state_or_records() -> None:
    adapter = TypeAdapter(TurnDecision)
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                "kind": "respond",
                "message": "Done.",
                "mission_state": "COMPLETED",
                "artifacts": [{"kind": "decision"}],
            }
        )


def test_context_manifest_is_hash_bound_and_principal_specific() -> None:
    manifest = _manifest()
    assert manifest.manifest_hash == manifest.calculate_hash()
    assert manifest.principal is Principal.SIRA
    with pytest.raises(ValidationError, match="hash"):
        manifest.model_copy(update={"current_message": "tampered"}).model_validate(
            manifest.model_copy(update={"current_message": "tampered"})
        )


async def test_deterministic_runtime_returns_typed_clarification() -> None:
    runtime = DeterministicCognitiveRuntime(
        decisions=[
            {
                "kind": "clarify",
                "question": "Must recordings stay in the EU?",
                "reason": "This can change eligibility.",
            }
        ]
    )
    decision = await runtime.decide(_manifest())
    assert decision == Clarify(
        kind="clarify",
        question="Must recordings stay in the EU?",
        reason="This can change eligibility.",
    )


def test_tool_broker_filters_by_principal_purpose_stage_version_and_schema() -> None:
    tool = ToolManifest(
        name="read_evidence",
        contract_version="v1",
        description="Read an authorized evidence projection.",
        allowed_principals=frozenset({Principal.SIRA}),
        purposes=frozenset({"software_selection"}),
        allowed_stages=frozenset({"evaluating"}),
        risk=ToolRisk.READ,
        input_schema={
            "type": "object",
            "properties": {"evidence_id": {"type": "string"}},
            "required": ["evidence_id"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
    )
    broker = ToolBroker({tool.name: tool})
    manifest = _manifest()
    valid = ProposedToolCall(
        call_id="call-1",
        tool_name="read_evidence",
        contract_version="v1",
        arguments={"evidence_id": "evidence-1"},
    )
    assert broker.authorize(valid, manifest, stage="evaluating", mutations_used=0) == tool
    with pytest.raises(ToolDenied, match="TOOL_INPUT_INVALID"):
        broker.authorize(
            valid.model_copy(update={"arguments": {"evidence_id": "evidence-1", "admin": True}}),
            manifest,
            stage="evaluating",
            mutations_used=0,
        )
    with pytest.raises(ToolDenied, match="TOOL_NOT_VISIBLE"):
        broker.authorize(
            valid,
            _manifest(principal="SEIL"),
            stage="evaluating",
            mutations_used=0,
        )
