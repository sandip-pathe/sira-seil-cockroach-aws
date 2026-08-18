"""Scripted cognitive runtime used only by deterministic tests."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from pydantic import TypeAdapter
from sira_agents.kernel_models import ContextManifest, TurnDecision

_DECISION_ADAPTER: TypeAdapter[TurnDecision] = TypeAdapter(TurnDecision)


@dataclass(slots=True)
class ScriptedCognitiveRuntime:
    decisions: list[Mapping[str, Any]] = field(default_factory=list)
    decision_factory: Callable[[ContextManifest], Mapping[str, Any]] | None = None
    calls: list[ContextManifest] = field(default_factory=list)

    async def decide(self, manifest: ContextManifest) -> TurnDecision:
        if manifest.manifest_hash != manifest.calculate_hash():
            raise ValueError("scripted cognitive runtime requires a sealed context manifest")
        self.calls.append(manifest)
        if self.decisions:
            decision = self.decisions.pop(0)
        elif self.decision_factory is not None:
            decision = self.decision_factory(manifest)
        else:
            raise AssertionError("scripted cognitive runtime exhausted its explicit decisions")
        return _DECISION_ADAPTER.validate_python(decision)
