"""Provider-neutral agent request and execution contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class AgentRole(StrEnum):
    SIRA = "SIRA"
    SEIL = "SEIL"


class AuthorityMode(StrEnum):
    ADVISORY = "ADVISORY"
    MISSION_OPERATOR = "MISSION_OPERATOR"


@dataclass(frozen=True, slots=True)
class AgentToolContract:
    """A model-visible tool that can only be proposed, never provider-executed."""

    name: str
    contract_version: str
    description: str
    input_schema: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.contract_version.strip():
            raise ValueError("proposal tool identity is required")
        if not self.description.strip():
            raise ValueError("proposal tool description is required")
        if self.input_schema.get("type") != "object":
            raise ValueError("proposal tool input schema must describe an object")


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
    proposal_tools: tuple[AgentToolContract, ...] = ()
    output_type: type[Any] | None = None
    authority_mode: AuthorityMode = AuthorityMode.ADVISORY


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    output: object
    tool_calls: tuple[str, ...] = ()
    proposals: tuple[Mapping[str, Any], ...] = ()
    runtime: str = "unspecified"
    advisory_only: bool = True
    ranking_effect: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)


class AgentRuntime(Protocol):
    """Provider-neutral boundary used by API and worker orchestration."""

    async def run(self, request: AgentRunRequest) -> AgentRunResult: ...
