"""OpenAI Agents SDK adapter with explicit privacy and authority boundaries."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from sira_agents.guardrails import validate_agent_payload


class AgentRole(StrEnum):
    SIRA = "SIRA"
    SEIL = "SEIL"


class AuthorityMode(StrEnum):
    ADVISORY = "ADVISORY"
    MISSION_OPERATOR = "MISSION_OPERATOR"


@dataclass(frozen=True, slots=True)
class AgentRunContext:
    """Private application state available to tools, never serialized for the model."""

    organization_id: str
    actor_id: str
    actor_roles: frozenset[str] = frozenset()
    permissions: frozenset[str] = frozenset()
    party: str | None = None
    step_up_verified: bool = False
    request_id: str | None = None
    services: Mapping[str, object] = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self) -> None:
        if not self.organization_id.strip():
            raise ValueError("agent run context requires organization_id")
        if not self.actor_id.strip():
            raise ValueError("agent run context requires actor_id")


@dataclass(frozen=True, slots=True)
class AgentRunRequest:
    role: AgentRole
    instructions: str
    prompt: str
    model_context: Mapping[str, Any]
    run_context: AgentRunContext | None = None
    allowed_tools: tuple[str, ...] = ()
    output_type: type[Any] | None = None
    authority_mode: AuthorityMode = AuthorityMode.ADVISORY


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    output: object
    tool_calls: tuple[str, ...] = ()
    proposals: tuple[Mapping[str, Any], ...] = ()
    runtime: str = "openai-agents"
    advisory_only: bool = True
    ranking_effect: bool = False


class _SdkFacade(Protocol):
    def create_agent(
        self,
        *,
        name: str,
        instructions: str,
        model: str,
        tools: list[object],
        output_type: type[Any] | None,
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class _SdkRunOutcome:
    output: object
    tool_calls: tuple[str, ...]
    proposals: tuple[Mapping[str, Any], ...]

    async def run(
        self,
        agent: object,
        input_text: str,
        *,
        context: AgentRunContext | None,
        max_turns: int,
        workflow_name: str,
    ) -> object: ...


class _OpenAISdkFacade:
    """Lazy SDK import keeps the rest of the backend independent of the provider package."""

    def create_agent(
        self,
        *,
        name: str,
        instructions: str,
        model: str,
        tools: list[object],
        output_type: type[Any] | None,
    ) -> object:
        from agents import Agent

        agent_factory: Any = Agent
        agent: object = agent_factory(
            name=name,
            instructions=instructions,
            model=model,
            tools=tools,
            output_type=output_type,
        )
        return agent

    async def run(
        self,
        agent: object,
        input_text: str,
        *,
        context: AgentRunContext | None,
        max_turns: int,
        workflow_name: str,
    ) -> object:
        from agents import RunConfig, Runner, ToolCallItem, ToolCallOutputItem

        sdk_runner: Any = Runner
        result: Any = await sdk_runner.run(
            agent,
            input_text,
            context=context,
            max_turns=max_turns,
            run_config=RunConfig(
                tracing_disabled=True,
                trace_include_sensitive_data=False,
                workflow_name=workflow_name,
            ),
        )
        output: object = result.final_output
        tool_calls = tuple(
            item.tool_name
            for item in result.new_items
            if isinstance(item, ToolCallItem) and item.tool_name is not None
        )
        proposals: list[Mapping[str, Any]] = []
        for item in result.new_items:
            if not isinstance(item, ToolCallOutputItem):
                continue
            candidate = item.output
            model_dump = getattr(candidate, "model_dump", None)
            if callable(model_dump):
                candidate = model_dump(mode="json")
            elif isinstance(candidate, str):
                try:
                    candidate = json.loads(candidate)
                except json.JSONDecodeError:
                    continue
            if not isinstance(candidate, Mapping):
                continue
            if {
                "proposal_type",
                "proposal_hash",
                "payload",
                "requires_human_action",
            }.issubset(candidate):
                proposals.append(dict(candidate))
        return _SdkRunOutcome(
            output=output,
            tool_calls=tool_calls,
            proposals=tuple(proposals),
        )


@dataclass(slots=True)
class OpenAIAgentsRuntime:
    """Model control-plane adapter; protected effects remain server-authorized."""

    model: str
    tools: Mapping[str, object] = field(default_factory=dict)
    max_turns: int = 16
    _sdk: _SdkFacade = field(default_factory=_OpenAISdkFacade, repr=False)

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        seller_visible = request.role is AgentRole.SEIL
        payload = {
            "role": request.role.value,
            "prompt": request.prompt,
            "context": request.model_context,
        }
        validate_agent_payload(payload, seller_visible=seller_visible)

        unknown_tools = sorted(set(request.allowed_tools).difference(self.tools))
        if unknown_tools:
            joined = ", ".join(unknown_tools)
            raise ValueError(f"agent request contains unregistered tools: {joined}")

        resolved_tools = [self.tools[name] for name in request.allowed_tools]
        agent = self._sdk.create_agent(
            name=request.role.value,
            instructions=request.instructions,
            model=self.model,
            tools=resolved_tools,
            output_type=request.output_type,
        )
        outcome = await self._sdk.run(
            agent,
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str),
            context=request.run_context,
            max_turns=self.max_turns,
            workflow_name=f"sira-seil-{request.role.value.lower()}",
        )
        if isinstance(outcome, _SdkRunOutcome):
            return AgentRunResult(
                output=outcome.output,
                tool_calls=outcome.tool_calls,
                proposals=outcome.proposals,
                advisory_only=request.authority_mode is AuthorityMode.ADVISORY,
            )
        return AgentRunResult(
            output=outcome,
            advisory_only=request.authority_mode is AuthorityMode.ADVISORY,
        )
