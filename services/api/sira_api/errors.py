"""Stable public errors with redacted details."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ApiProblem(Exception):
    code: str
    message: str
    status_code: int
    retryable: bool = False
    next_action: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class SetupBlocked(ApiProblem):
    def __init__(self, provider: str, missing: list[str]) -> None:
        super().__init__(
            code="PROVIDER_SETUP_BLOCKED",
            message=f"{provider} is not configured for a real provider operation.",
            status_code=503,
            retryable=False,
            next_action="configure_provider",
            details={"provider": provider, "missing_configuration": sorted(missing)},
        )
