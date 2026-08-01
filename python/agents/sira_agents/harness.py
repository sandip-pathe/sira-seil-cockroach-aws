"""Narrow SIRA and SEIL orchestration helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from sira_agents.runtime import AgentRole, AgentRunRequest, AgentRunResult


class AgentRuntime(Protocol):
    async def run(self, request: AgentRunRequest) -> AgentRunResult: ...


@dataclass(frozen=True, slots=True)
class SiraSeilHarness:
    runtime: AgentRuntime

    async def extract_buyer_facts(
        self, *, prompt: str, private_context: Mapping[str, Any]
    ) -> AgentRunResult:
        return await self.runtime.run(
            AgentRunRequest(
                role=AgentRole.SIRA,
                instructions=(
                    "Extract supported facts and provenance only. Do not evaluate eligibility, "
                    "rank plans, approve purchases, or initiate payment. Mark uncertainty."
                ),
                prompt=prompt,
                context=private_context,
            )
        )

    async def explain_seller_fit(
        self,
        *,
        prompt: str,
        requirement_brief: Mapping[str, Any],
        published_pack: Mapping[str, Any],
    ) -> AgentRunResult:
        return await self.runtime.run(
            AgentRunRequest(
                role=AgentRole.SEIL,
                instructions=(
                    "Explain only the supplied sanitized requirement and published Pack. "
                    "Positioning is labelled seller content and has zero ranking effect."
                ),
                prompt=prompt,
                context={
                    "requirement_brief": requirement_brief,
                    "published_pack": published_pack,
                },
            )
        )
