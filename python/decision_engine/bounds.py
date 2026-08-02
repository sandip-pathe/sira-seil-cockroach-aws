"""Exact Decision Graph intervals and rank-stability calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext
from fractions import Fraction
from math import gcd
from typing import Any

from domain.enums import CandidateStatus, RankStability, StackRisk
from domain.errors import DomainValidationError
from domain.models import require_id
from domain.money import Money

type ExactInput = Fraction | Decimal | str | int


def _fraction(value: ExactInput, field_name: str) -> Fraction:
    if isinstance(value, bool) or isinstance(value, float):
        raise DomainValidationError(f"{field_name} requires exact input")
    if isinstance(value, Fraction):
        result = value
    else:
        try:
            decimal = value if isinstance(value, Decimal) else Decimal(value)
        except (InvalidOperation, ValueError) as exc:
            raise DomainValidationError(f"invalid {field_name}") from exc
        if not decimal.is_finite():
            raise DomainValidationError(f"{field_name} must be finite")
        numerator, denominator = decimal.as_integer_ratio()
        result = Fraction(numerator, denominator)
    return result


@dataclass(frozen=True, slots=True)
class ExactRatio:
    numerator: int
    denominator: int

    def __init__(self, numerator: int, denominator: int = 1) -> None:
        if isinstance(numerator, bool) or isinstance(denominator, bool) or denominator == 0:
            raise DomainValidationError("an exact ratio requires integer numerator/denominator")
        if not isinstance(numerator, int) or not isinstance(denominator, int):
            raise DomainValidationError("an exact ratio requires integer numerator/denominator")
        sign = -1 if denominator < 0 else 1
        divisor = gcd(numerator, denominator)
        object.__setattr__(self, "numerator", sign * numerator // divisor)
        object.__setattr__(self, "denominator", abs(denominator) // divisor)

    @classmethod
    def from_value(cls, value: ExactInput, field_name: str = "ratio") -> ExactRatio:
        exact = _fraction(value, field_name)
        return cls(exact.numerator, exact.denominator)

    @property
    def fraction(self) -> Fraction:
        return Fraction(self.numerator, self.denominator)

    def display(self) -> str:
        with localcontext() as context:
            context.prec = 50
            value = Decimal(self.numerator) / Decimal(self.denominator)
            return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN), ".2f")

    def to_dict(self, *, include_display: bool = False) -> dict[str, int | str]:
        result: dict[str, int | str] = {
            "numerator": self.numerator,
            "denominator": self.denominator,
        }
        if include_display:
            result["display"] = self.display()
        return result


@dataclass(frozen=True, slots=True)
class PreferenceCriterionBound:
    criterion_id: str
    weight: int
    conservative_satisfaction: ExactRatio
    optimistic_satisfaction: ExactRatio

    def __post_init__(self) -> None:
        require_id(self.criterion_id, "criterion_id")
        if isinstance(self.weight, bool) or not 1 <= self.weight <= 5:
            raise DomainValidationError("preference weight must be an integer from 1 to 5")
        lower = self.conservative_satisfaction.fraction
        upper = self.optimistic_satisfaction.fraction
        if not Fraction(0) <= lower <= upper <= Fraction(1):
            raise DomainValidationError(
                "preference satisfaction bounds must satisfy 0 <= low <= high <= 1"
            )


@dataclass(frozen=True, slots=True)
class PreferenceScoreBounds:
    conservative: ExactRatio
    optimistic: ExactRatio

    def __post_init__(self) -> None:
        if not Fraction(0) <= self.conservative.fraction <= self.optimistic.fraction <= 100:
            raise DomainValidationError("preference score bounds must be between zero and 100")

    def to_dict(self) -> dict[str, dict[str, int | str]]:
        return {
            "conservative": self.conservative.to_dict(include_display=True),
            "optimistic": self.optimistic.to_dict(include_display=True),
        }


def aggregate_preference_bounds(
    criteria: tuple[PreferenceCriterionBound, ...],
) -> PreferenceScoreBounds:
    if not criteria:
        raise DomainValidationError("a preference-capable plan requires at least one criterion")
    if len({item.criterion_id for item in criteria}) != len(criteria):
        raise DomainValidationError("preference criteria must be unique")
    denominator = sum(item.weight for item in criteria)
    conservative = (
        Fraction(100)
        * sum(
            (item.weight * item.conservative_satisfaction.fraction for item in criteria),
            start=Fraction(0),
        )
        / denominator
    )
    optimistic = (
        Fraction(100)
        * sum(
            (item.weight * item.optimistic_satisfaction.fraction for item in criteria),
            start=Fraction(0),
        )
        / denominator
    )
    return PreferenceScoreBounds(
        ExactRatio(conservative.numerator, conservative.denominator),
        ExactRatio(optimistic.numerator, optimistic.denominator),
    )


@dataclass(frozen=True, slots=True)
class CoverageCriterion:
    criterion_id: str
    weight: int
    conservative_covered: bool
    optimistic_covered: bool

    def __post_init__(self) -> None:
        require_id(self.criterion_id, "criterion_id")
        if isinstance(self.weight, bool) or not 1 <= self.weight <= 5:
            raise DomainValidationError("coverage weight must be an integer from 1 to 5")
        if self.conservative_covered and not self.optimistic_covered:
            raise DomainValidationError(
                "optimistic coverage cannot be lower than conservative coverage"
            )


@dataclass(frozen=True, slots=True)
class CoverageBounds:
    conservative: ExactRatio
    optimistic: ExactRatio


def aggregate_coverage_bounds(criteria: tuple[CoverageCriterion, ...]) -> CoverageBounds:
    if not criteria:
        one = ExactRatio(1)
        return CoverageBounds(one, one)
    if len({item.criterion_id for item in criteria}) != len(criteria):
        raise DomainValidationError("coverage criteria must be unique")
    denominator = sum(item.weight for item in criteria)
    conservative = Fraction(
        sum(item.weight for item in criteria if item.conservative_covered), denominator
    )
    optimistic = Fraction(
        sum(item.weight for item in criteria if item.optimistic_covered), denominator
    )
    return CoverageBounds(
        ExactRatio(conservative.numerator, conservative.denominator),
        ExactRatio(optimistic.numerator, optimistic.denominator),
    )


@dataclass(frozen=True, slots=True)
class RiskBounds:
    lower: StackRisk
    base: StackRisk
    upper: StackRisk

    def __post_init__(self) -> None:
        if not self.lower.rank <= self.base.rank <= self.upper.rank:
            raise DomainValidationError("risk bounds must satisfy lower <= base <= upper")


def aggregate_risk_bounds(components: tuple[RiskBounds, ...]) -> RiskBounds:
    if not components:
        raise DomainValidationError("risk aggregation requires a component or current-stack action")
    by_rank = {risk.rank: risk for risk in StackRisk}
    return RiskBounds(
        lower=by_rank[max(item.lower.rank for item in components)],
        base=by_rank[max(item.base.rank for item in components)],
        upper=by_rank[max(item.upper.rank for item in components)],
    )


@dataclass(frozen=True, slots=True)
class CostBounds:
    low: Money
    base: Money
    high: Money

    def __post_init__(self) -> None:
        currencies = {self.low.currency, self.base.currency, self.high.currency}
        if len(currencies) != 1 or not self.low.amount <= self.base.amount <= self.high.amount:
            raise DomainValidationError("TCO bounds require one currency and low <= base <= high")


@dataclass(frozen=True, slots=True)
class EvidenceAgeBounds:
    lower: ExactRatio
    upper: ExactRatio

    def __post_init__(self) -> None:
        if not Fraction(0) <= self.lower.fraction <= self.upper.fraction:
            raise DomainValidationError("evidence-age bounds must satisfy 0 <= lower <= upper")


def evidence_age_bounds(
    *,
    evaluated_at: datetime,
    observed_at_lower: datetime,
    observed_at_upper: datetime,
    sla_seconds: int,
) -> EvidenceAgeBounds:
    if (
        evaluated_at.tzinfo is None
        or observed_at_lower.tzinfo is None
        or observed_at_upper.tzinfo is None
    ):
        raise DomainValidationError("evidence times must be timezone-aware")
    if isinstance(sla_seconds, bool) or sla_seconds < 1:
        raise DomainValidationError("evidence SLA must be a positive integer number of seconds")
    if not observed_at_lower <= observed_at_upper <= evaluated_at:
        raise DomainValidationError("evidence time bounds must precede evaluation")

    def ratio(observed_at: datetime) -> ExactRatio:
        delta = evaluated_at - observed_at
        microseconds = delta.days * 86_400_000_000 + delta.seconds * 1_000_000 + delta.microseconds
        exact = Fraction(microseconds, sla_seconds * 1_000_000)
        return ExactRatio(exact.numerator, exact.denominator)

    return EvidenceAgeBounds(lower=ratio(observed_at_upper), upper=ratio(observed_at_lower))


def aggregate_evidence_age_bounds(items: tuple[EvidenceAgeBounds, ...]) -> EvidenceAgeBounds:
    if not items:
        zero = ExactRatio(0)
        return EvidenceAgeBounds(zero, zero)
    lower = max(item.lower.fraction for item in items)
    upper = max(item.upper.fraction for item in items)
    return EvidenceAgeBounds(
        ExactRatio(lower.numerator, lower.denominator),
        ExactRatio(upper.numerator, upper.denominator),
    )


@dataclass(frozen=True, slots=True)
class OrderingBounds:
    preference: PreferenceScoreBounds
    stack_risk: RiskBounds
    total_cost: CostBounds
    decision_material_coverage: CoverageBounds
    maximum_evidence_age_ratio: EvidenceAgeBounds


@dataclass(frozen=True, slots=True)
class BoundedPlan:
    plan_id: str
    status: CandidateStatus
    stable_action_ids: tuple[str, ...]
    bounds: OrderingBounds | None
    bound_unavailable_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_id(self.plan_id, "plan_id")
        if self.status not in {CandidateStatus.ELIGIBLE, CandidateStatus.ELIGIBLE_WITH_EXCEPTION}:
            raise DomainValidationError("only eligible plans receive authoritative ordering bounds")
        if not self.stable_action_ids:
            raise DomainValidationError("a bounded plan requires stable action IDs")
        for action_id in self.stable_action_ids:
            require_id(action_id, "stable_action_id")
        if (self.bounds is None) != bool(self.bound_unavailable_reasons):
            raise DomainValidationError("missing bounds require exact BOUND_UNAVAILABLE reasons")

    @property
    def status_rank(self) -> int:
        return 0 if self.status is CandidateStatus.ELIGIBLE else 1


def _require_bounds(plan: BoundedPlan) -> OrderingBounds:
    if plan.bounds is None:
        raise DomainValidationError("BOUND_UNAVAILABLE plans cannot receive an ordering key")
    return plan.bounds


def authoritative_ordering_key(plan: BoundedPlan) -> tuple[Any, ...]:
    bounds = _require_bounds(plan)
    return (
        plan.status_rank,
        -bounds.preference.conservative.fraction,
        bounds.stack_risk.base.rank,
        bounds.total_cost.base.amount,
        -bounds.decision_material_coverage.conservative.fraction,
        bounds.maximum_evidence_age_ratio.upper.fraction,
        plan.stable_action_ids,
        plan.plan_id,
    )


def conservative_envelope_key(plan: BoundedPlan) -> tuple[Any, ...]:
    bounds = _require_bounds(plan)
    return (
        plan.status_rank,
        -bounds.preference.conservative.fraction,
        bounds.stack_risk.upper.rank,
        bounds.total_cost.high.amount,
        -bounds.decision_material_coverage.conservative.fraction,
        bounds.maximum_evidence_age_ratio.upper.fraction,
        plan.stable_action_ids,
        plan.plan_id,
    )


def optimistic_envelope_key(plan: BoundedPlan) -> tuple[Any, ...]:
    bounds = _require_bounds(plan)
    return (
        plan.status_rank,
        -bounds.preference.optimistic.fraction,
        bounds.stack_risk.lower.rank,
        bounds.total_cost.low.amount,
        -bounds.decision_material_coverage.optimistic.fraction,
        bounds.maximum_evidence_age_ratio.lower.fraction,
        plan.stable_action_ids,
        plan.plan_id,
    )


@dataclass(frozen=True, slots=True)
class RankStabilityResult:
    status: RankStability
    ordering_frontier_plan_ids: tuple[str, ...]
    bound_unavailable_plan_ids: tuple[str, ...]


def assess_rank_stability(
    selected: BoundedPlan,
    competitors: tuple[BoundedPlan, ...],
) -> RankStabilityResult:
    all_plans = (selected, *competitors)
    unavailable = tuple(sorted(plan.plan_id for plan in all_plans if plan.bounds is None))
    if unavailable:
        return RankStabilityResult(RankStability.UNDETERMINED, (), unavailable)
    selected_worst = conservative_envelope_key(selected)
    frontier = tuple(
        sorted(
            plan.plan_id for plan in competitors if optimistic_envelope_key(plan) < selected_worst
        )
    )
    return RankStabilityResult(
        RankStability.UNSTABLE if frontier else RankStability.STABLE,
        frontier,
        (),
    )
