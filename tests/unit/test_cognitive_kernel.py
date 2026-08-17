from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest
import rfc8785
from pydantic import TypeAdapter, ValidationError
from sira_agents.cognitive_runtime import DeterministicCognitiveRuntime
from sira_agents.kernel_models import (
    CapabilityGrant,
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
        "party": "BUYER",
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
        allowed_parties=frozenset({"BUYER"}),
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
            _manifest(principal="SEIL", party="SELLER"),
            stage="evaluating",
            mutations_used=0,
        )


def test_protected_effect_requires_exact_live_payload_bound_capability() -> None:
    tool = ToolManifest(
        name="open_payment_handoff",
        contract_version="v1",
        description="Open an approved external payment handoff.",
        allowed_principals=frozenset({Principal.SIRA}),
        allowed_parties=frozenset({"BUYER"}),
        purposes=frozenset({"software_selection"}),
        allowed_stages=frozenset({"evaluating"}),
        risk=ToolRisk.PROTECTED_EFFECT,
        input_schema={
            "type": "object",
            "properties": {"handoff_id": {"type": "string"}},
            "required": ["handoff_id"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
    )
    arguments = {"handoff_id": "handoff-1"}
    call = ProposedToolCall(
        call_id="call-protected",
        tool_name=tool.name,
        contract_version="v1",
        arguments=arguments,
    )
    grant = CapabilityGrant(
        id="grant-1",
        capability="payment_handoff.open",
        principal="SIRA",
        party="BUYER",
        actor_id="buyer-1",
        purpose="software_selection",
        tool_name=tool.name,
        contract_version="v1",
        scope=arguments,
        payload_hash=f"sha256:{sha256(rfc8785.dumps(arguments)).hexdigest()}",
        object_versions={"handoff": 1, "approval": 1},
        status="ACTIVE",
        expires_at=datetime.now(UTC) + timedelta(minutes=2),
    )
    broker = ToolBroker({tool.name: tool})
    manifest = _manifest(available_tools=(tool.name,))

    assert (
        broker.authorize(call, manifest, stage="evaluating", mutations_used=0, grant=grant) == tool
    )
    with pytest.raises(ToolDenied, match="SCOPE_MISMATCH"):
        broker.authorize(
            call.model_copy(update={"arguments": {"handoff_id": "handoff-2"}}),
            manifest,
            stage="evaluating",
            mutations_used=0,
            grant=grant,
        )
