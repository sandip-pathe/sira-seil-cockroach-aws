"""Deterministic, labelled qualification-agent trust-boundary evaluation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from persistence.repositories import PersistenceConflict

from .qualification import QualificationAgentDecision, _validate_grounded_decision


@dataclass(frozen=True, slots=True)
class QualificationEvalCase:
    id: str
    expected: Literal["ACCEPT", "REJECT"]
    allowed_products: frozenset[str]
    dependency_products: Mapping[str, str]
    decision: QualificationAgentDecision


@dataclass(frozen=True, slots=True)
class QualificationEvalResult:
    case_id: str
    expected: str
    actual: str
    passed: bool


def run_qualification_eval(
    cases: Sequence[QualificationEvalCase],
) -> tuple[QualificationEvalResult, ...]:
    """Score grounded-decision enforcement without model or provider variability."""

    results: list[QualificationEvalResult] = []
    for case in cases:
        actual = "ACCEPT"
        try:
            _validate_grounded_decision(
                case.decision,
                allowed_products=case.allowed_products,
                dependency_products=case.dependency_products,
            )
        except PersistenceConflict:
            actual = "REJECT"
        results.append(
            QualificationEvalResult(
                case_id=case.id,
                expected=case.expected,
                actual=actual,
                passed=actual == case.expected,
            )
        )
    return tuple(results)
