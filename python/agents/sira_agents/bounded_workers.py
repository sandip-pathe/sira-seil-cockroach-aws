"""Fail-closed contracts for bounded research and evaluation workers."""

from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field


class WorkerBudget(BaseModel):
    max_turns: int = Field(default=8, ge=1, le=32)
    timeout_seconds: int = Field(default=300, ge=1, le=1_800)
    max_artifacts: int = Field(default=4, ge=1, le=12)


class WorkerTask(BaseModel):
    id: str
    role: Literal["researcher", "evaluator", "seller_twin_builder", "critic"]
    objective: str = Field(min_length=1, max_length=1_000)
    inputs: dict[str, Any] = Field(default_factory=dict)
    budget: WorkerBudget = Field(default_factory=WorkerBudget)
    allowed_tools: list[str] = Field(default_factory=list, max_length=20)
    protected_effects_allowed: Literal[False] = False


class WorkerArtifact(BaseModel):
    kind: str
    title: str
    payload: dict[str, Any]
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class WorkerResult(BaseModel):
    task_id: str
    status: Literal["COMPLETED", "FAILED", "BLOCKED"]
    artifacts: list[WorkerArtifact] = Field(default_factory=list)
    safe_error_code: str | None = None


class BoundedWorker(Protocol):
    async def run(self, task: WorkerTask) -> WorkerResult: ...
