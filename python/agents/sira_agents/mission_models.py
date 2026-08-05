"""Typed control-plane contracts for one resumable commerce-agent turn."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

MissionState = Literal[
    "ORIENTING",
    "PLANNING",
    "EXPLORING",
    "EXPERIMENTING",
    "SYNTHESIZING",
    "PROPOSING",
    "AWAITING_AUTHORITY",
    "EXECUTING",
    "VERIFYING",
    "MONITORING",
    "COMPLETED",
    "PAUSED",
    "BLOCKED",
    "FAILED",
]


class MissionPlanStep(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=240)
    status: Literal["pending", "active", "completed", "blocked"] = "pending"
    reason: str | None = Field(default=None, max_length=500)


class MissionClaim(BaseModel):
    subject: str = Field(min_length=1, max_length=160)
    predicate: str = Field(min_length=1, max_length=160)
    value: Any
    confidence: float = Field(ge=0, le=1)
    authority: Literal["OBSERVED", "VERIFIED", "INFERRED", "SELLER_ASSERTED", "USER_ASSERTED"]
    source_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=20)


class MissionEventDraft(BaseModel):
    event_type: str = Field(pattern=r"^agent\.[a-z0-9_.-]+$", max_length=80)
    summary: str = Field(min_length=1, max_length=500)
    details: dict[str, Any] = Field(default_factory=dict)


class MissionArtifactDraft(BaseModel):
    kind: Literal[
        "research",
        "requirement_brief",
        "candidate_set",
        "comparison",
        "experiment_plan",
        "experiment_result",
        "recommendation",
        "purchase_proposal",
        "seller_evidence",
    ]
    title: str = Field(min_length=1, max_length=240)
    authority: Literal["OBSERVED", "VERIFIED", "INFERRED", "SELLER_ASSERTED", "USER_ASSERTED"]
    payload: dict[str, Any]
    source_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=40)


class MissionTaskDraft(BaseModel):
    kind: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=240)
    owner_type: Literal["ROOT_AGENT", "SUBAGENT", "HUMAN", "SYSTEM"] = "ROOT_AGENT"
    assigned_role: str | None = Field(default=None, max_length=80)
    input: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, Any] = Field(default_factory=dict)


class AttentionRequest(BaseModel):
    kind: Literal["question", "approval", "credential", "choice", "blocked"]
    prompt: str = Field(min_length=1, max_length=800)
    reason: str = Field(min_length=1, max_length=500)
    options: list[str] = Field(default_factory=list, max_length=6)


class MissionTurnOutput(BaseModel):
    """One bounded root-agent decision; the server validates and persists it."""

    message: str = Field(min_length=1, max_length=8_000)
    mission_state: MissionState
    plan: list[MissionPlanStep] = Field(default_factory=list, max_length=24)
    claims: list[MissionClaim] = Field(default_factory=list, max_length=40)
    events: list[MissionEventDraft] = Field(default_factory=list, max_length=20)
    artifacts: list[MissionArtifactDraft] = Field(default_factory=list, max_length=12)
    tasks: list[MissionTaskDraft] = Field(default_factory=list, max_length=12)
    attention: AttentionRequest | None = None
    continue_autonomously: bool = False
    show_product_ids: list[str] = Field(default_factory=list, max_length=20)
    stop_reason: str | None = Field(default=None, max_length=120)
