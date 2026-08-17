"""Model-provider boundary for one typed cognitive decision."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import TypeAdapter

from sira_agents.kernel_models import ContextManifest, TurnDecision

_DECISION_ADAPTER: TypeAdapter[TurnDecision] = TypeAdapter(TurnDecision)


class CognitiveRuntime(Protocol):
    async def decide(self, manifest: ContextManifest) -> TurnDecision: ...


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
