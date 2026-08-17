"""Deterministic selection of one question that can materially change a decision."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ClarificationCandidate:
    fact_id: str
    question: str
    affects_hard_gate: bool = False
    can_change_rank: bool = False
    affects_disclosure: bool = False
    affects_execution: bool = False
    expected_uncertainty_reduction: float = 0
    user_effort: float = 1

    def __post_init__(self) -> None:
        if not self.fact_id.strip() or not self.question.strip():
            raise ValueError("clarification fact and question are required")
        if self.expected_uncertainty_reduction < 0:
            raise ValueError("uncertainty reduction cannot be negative")
        if self.user_effort <= 0:
            raise ValueError("clarification user effort must be positive")

    @property
    def material(self) -> bool:
        return any(
            (
                self.affects_hard_gate,
                self.can_change_rank,
                self.affects_disclosure,
                self.affects_execution,
            )
        )

    @property
    def value(self) -> float:
        consequence = (
            4 * int(self.affects_hard_gate)
            + 3 * int(self.can_change_rank)
            + 3 * int(self.affects_disclosure)
            + 4 * int(self.affects_execution)
        )
        return (consequence + self.expected_uncertainty_reduction) / self.user_effort


def select_material_clarification(
    candidates: tuple[ClarificationCandidate, ...],
) -> ClarificationCandidate | None:
    """Return one highest-value material question with a stable tie-break."""

    material = [candidate for candidate in candidates if candidate.material]
    if not material:
        return None
    return sorted(material, key=lambda item: (-item.value, item.fact_id))[0]
