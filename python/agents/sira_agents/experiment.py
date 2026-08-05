"""Reproducible evaluation contracts for real product experiments."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ExperimentSignal(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    measurement: str = Field(min_length=1, max_length=300)
    success_threshold: str = Field(min_length=1, max_length=200)


class ExperimentSpec(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=100)
    fixture_id: str = Field(min_length=1, max_length=160)
    procedure: list[str] = Field(min_length=1, max_length=40)
    environment: dict[str, Any]
    success_signals: list[ExperimentSignal] = Field(min_length=1, max_length=20)
    replay_command: list[str] = Field(min_length=1, max_length=40)
    egress_hosts: list[str] = Field(default_factory=list, max_length=20)
    timeout_seconds: int = Field(default=300, ge=1, le=1_800)
    max_output_bytes: int = Field(default=2_000_000, ge=1_024, le=20_000_000)

    @model_validator(mode="after")
    def reject_secret_material(self) -> ExperimentSpec:
        forbidden = {"token", "secret", "password", "api_key", "credential"}
        serialized = str(self.model_dump()).lower()
        if any(name in serialized for name in forbidden):
            raise ValueError(
                "experiment specs must reference server-held credentials, not contain them"
            )
        return self


class ExperimentObservation(BaseModel):
    signal: str
    value: Any
    source: str


class ExperimentResult(BaseModel):
    status: Literal["COMPLETED", "FAILED", "CANCELLED"]
    observations: list[ExperimentObservation] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    logs_reference: str | None = None
    artifact_hash: str
