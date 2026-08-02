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
    conversation_id: str | None = Field(default=None, pattern=r"^wc_[a-f0-9]{32}$")
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
    claims: list[str]
    integrations: list[str]


class AgentProposalView(BaseModel):
    proposal_type: str
    proposal_hash: str
    payload: dict[str, Any]
    advisory_only: bool = True
    ranking_effect: bool = False
    requires_human_action: bool = True


class WorkspaceChatView(BaseModel):
    conversation_id: str
    message: str
    follow_up_required: bool = False
    panel: Literal["run", "catalog", "connectors", "decisions", "inbox"] = "run"
    products: list[CatalogProductView] = Field(default_factory=list)
    tool_calls: list[str] = Field(default_factory=list)
    proposals: list[AgentProposalView] = Field(default_factory=list)
    advisory_only: bool = True


class WorkspaceConversationView(BaseModel):
    id: str
    mode: Literal["sira", "seil"]
    title: str
    messages: list[WorkspaceMessage]
    updated_at: str


class ConnectorView(BaseModel):
    id: str
    name: str
    purpose: str
    status: Literal["Healthy", "Needs setup", "Not connected"]
    meta: str
