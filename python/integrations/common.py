"""Shared, non-secret metadata for provider adapters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AdapterMode(StrEnum):
    """Whether an adapter talks to a configured provider or deterministic fixtures."""

    PRODUCTION = "production"
    DEVELOPMENT_FIXTURE = "development_fixture"


@dataclass(frozen=True, slots=True)
class AdapterDescriptor:
    """Safe adapter identity suitable for API responses and logs.

    Development fixtures are structurally prevented from claiming either production
    capability or production verification.
    """

    provider: str
    mode: AdapterMode
    production_capable: bool
    production_verified: bool = False

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider must not be empty")
        if self.mode is AdapterMode.DEVELOPMENT_FIXTURE and (
            self.production_capable or self.production_verified
        ):
            raise ValueError("development fixtures cannot claim production status")
        if self.production_verified and not self.production_capable:
            raise ValueError("production verification requires a production-capable adapter")

    @classmethod
    def production(cls, provider: str) -> AdapterDescriptor:
        """Describe a real provider path without claiming a live certification run."""

        return cls(
            provider=provider,
            mode=AdapterMode.PRODUCTION,
            production_capable=True,
            production_verified=False,
        )

    @classmethod
    def development_fixture(cls, provider: str) -> AdapterDescriptor:
        """Describe an explicitly non-production deterministic adapter."""

        return cls(
            provider=provider,
            mode=AdapterMode.DEVELOPMENT_FIXTURE,
            production_capable=False,
            production_verified=False,
        )
