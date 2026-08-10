"""Contracts for the persistent chat-first commerce workspace."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class WorkspaceMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12_000)
    tool_calls: list[str] = Field(default_factory=list)
    proposals: list[AgentProposalView] = Field(default_factory=list)


class WorkspaceChatCreate(BaseModel):
    conversation_id: str | None = Field(
        default=None, pattern=r"^(?:wc_[a-f0-9]{32}|msn_[a-f0-9]{32})$"
    )
    mission_id: str | None = Field(default=None, pattern=r"^msn_[a-f0-9]{32}$")
    mode: Literal["sira", "seil"] = "sira"
    message: str = Field(min_length=1, max_length=8_000)
    history: list[WorkspaceMessage] = Field(default_factory=list, max_length=20)


class CatalogProductView(BaseModel):
    id: str
    name: str
    seller: str
    edition: str
    price: str
    billing_unit: str
    status: str
    summary: str
    fit: str | None = None
    why_company: str | None = None
    requirement_coverage: str | None = None
    claims: list[str]
    integrations: list[str]
    website: str | None = None
    logo: str | None = None
    evidence_freshness: str | None = None
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    listing_origin: Literal["SELLER_PUBLISHED", "SEIL_RESEARCHED"] | None = None
    evidence_status: Literal["PUBLISHED", "RESEARCH_ONLY"] | None = None
    seller_attested: bool | None = None


class AgentProposalView(BaseModel):
    proposal_type: str
    proposal_hash: str
    payload: dict[str, Any]
    advisory_only: bool = True
    ranking_effect: bool = False
    requires_human_action: bool = True


class MissionEventView(BaseModel):
    id: str
    sequence: int
    type: str
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    occurred_at: str | None = None
    verified: bool = False


class MissionArtifactView(BaseModel):
    id: str
    kind: str
    title: str
    status: str = "READY"
    authority: str
    payload: dict[str, Any]
    source_refs: list[dict[str, Any]] = Field(default_factory=list)


class AttentionView(BaseModel):
    kind: Literal["question", "approval", "credential", "choice", "blocked"]
    prompt: str
    reason: str
    options: list[str] = Field(default_factory=list)


class MissionSummaryView(BaseModel):
    id: str
    mode: Literal["sira", "seil"]
    goal: str
    state: str
    version: int
    plan: list[dict[str, Any]] = Field(default_factory=list)
    stop_reason: str | None = None


class WorkspaceChatView(BaseModel):
    conversation_id: str
    mission_id: str
    message: str
    follow_up_required: bool = False
    panel: Literal["catalog", "connectors", "decisions", "inbox"] | None = None
    products: list[CatalogProductView] = Field(default_factory=list)
    tool_calls: list[str] = Field(default_factory=list)
    proposals: list[AgentProposalView] = Field(default_factory=list)
    mission: MissionSummaryView
    events: list[MissionEventView] = Field(default_factory=list)
    artifacts: list[MissionArtifactView] = Field(default_factory=list)
    attention: AttentionView | None = None
    advisory_only: bool = False


class MissionSnapshotView(BaseModel):
    mission: MissionSummaryView
    events: list[MissionEventView]
    artifacts: list[MissionArtifactView]
    open_tasks: list[dict[str, Any]] = Field(default_factory=list)
    handoffs: list[dict[str, Any]] = Field(default_factory=list)


class WorkspaceConversationView(BaseModel):
    id: str
    mode: Literal["sira", "seil"]
    title: str
    messages: list[WorkspaceMessage]
    updated_at: str
    mission: MissionSummaryView
    events: list[MissionEventView] = Field(default_factory=list)
    artifacts: list[MissionArtifactView] = Field(default_factory=list)
    open_tasks: list[dict[str, Any]] = Field(default_factory=list)


class ConnectorView(BaseModel):
    id: str
    name: str
    purpose: str
    status: Literal["Healthy", "Needs setup", "Not connected", "Proof workspace"]
    meta: str


class CapabilityView(BaseModel):
    id: str
    label: str
    status: Literal["disabled", "misconfigured", "ready", "degraded", "offline"]
    reason_code: str
    remediation: str | None = None
