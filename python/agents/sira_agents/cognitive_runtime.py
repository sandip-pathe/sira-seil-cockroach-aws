"""Model-provider boundary for one typed cognitive decision."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import TypeAdapter

from sira_agents.kernel_models import ContextManifest, TurnDecision, TurnDecisionEnvelope
from sira_agents.runtime import AgentRole, AgentRunRequest, AgentRunResult

_DECISION_ADAPTER: TypeAdapter[TurnDecision] = TypeAdapter(TurnDecision)


class CognitiveRuntime(Protocol):
    async def decide(self, manifest: ContextManifest) -> TurnDecision: ...


class StructuredRuntime(Protocol):
    async def run(self, request: AgentRunRequest) -> AgentRunResult: ...


@dataclass(slots=True)
class DeterministicCognitiveRuntime:
    """Scripted provider double used by local development and deterministic tests."""

    decisions: list[Mapping[str, Any]] = field(default_factory=list)
    calls: list[ContextManifest] = field(default_factory=list)

    async def decide(self, manifest: ContextManifest) -> TurnDecision:
        if manifest.manifest_hash != manifest.calculate_hash():
            raise ValueError("cognitive runtime requires a sealed context manifest")
        self.calls.append(manifest)
        if self.decisions:
            return _DECISION_ADAPTER.validate_python(self.decisions.pop(0))
        return _DECISION_ADAPTER.validate_python(
            {
                "kind": "respond",
                "message": (
                    "Hello — I can help with this. Tell me the outcome you want, "
                    "and I'll ask only for details that could change the decision."
                ),
            }
        )


@dataclass(frozen=True, slots=True)
class BedrockCognitiveRuntime:
    """Use Bedrock only for typed decisions; the kernel owns all tool execution."""

    runtime: StructuredRuntime

    async def decide(self, manifest: ContextManifest) -> TurnDecision:
        if manifest.manifest_hash != manifest.calculate_hash():
            raise ValueError("Bedrock cognitive runtime requires a sealed context manifest")
        context = {
            "principal": manifest.principal.value,
            "party": manifest.party.value,
            "purpose": manifest.purpose,
            "context_hash": manifest.manifest_hash,
            "recent_messages": manifest.recent_messages,
            "summary": manifest.summary,
            "unresolved_questions": manifest.unresolved_questions,
            "references": [item.model_dump(mode="json") for item in manifest.references],
            "exchange_projection": manifest.exchange_projection,
            "available_tools": manifest.available_tools,
            "tool_contracts": manifest.tool_contracts,
            "budget": manifest.budget.model_dump(mode="json"),
        }
        result = await self.runtime.run(
            AgentRunRequest(
                role=AgentRole(manifest.principal.value),
                instructions=(
                    "Choose exactly one typed turn decision. Respond naturally to greetings. "
                    "Ask one material clarification when missing information could change the "
                    "decision. Propose a listed tool only when context is sufficient. Never invent "
                    "persistent states, records, authority, tool results, or successful effects."
                ),
                prompt=manifest.current_message,
                model_context=context,
                allowed_tools=(),
                output_type=TurnDecisionEnvelope,
            )
        )
        envelope = TurnDecisionEnvelope.model_validate(result.output)
        return envelope.decision
