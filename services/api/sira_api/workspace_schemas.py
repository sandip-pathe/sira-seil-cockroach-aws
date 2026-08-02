"""Contracts for the persistent chat-first commerce workspace."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class WorkspaceMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12_000)


class WorkspaceChatCreate(BaseModel):
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


class WorkspaceChatView(BaseModel):
    message: str
    follow_up_required: bool = False
    panel: Literal["run", "catalog", "connectors", "decisions", "inbox"] = "run"
    products: list[CatalogProductView] = Field(default_factory=list)
    tool_calls: list[str] = Field(default_factory=list)
    advisory_only: bool = True


class ConnectorView(BaseModel):
    id: str
    name: str
    purpose: str
    status: Literal["Healthy", "Needs setup", "Not connected"]
    meta: str
