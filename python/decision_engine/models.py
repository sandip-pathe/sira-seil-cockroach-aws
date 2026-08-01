"""Value objects used by the deterministic decision engine."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction

from domain.enums import CandidateStatus, SolutionAction, StackRisk, TruthValue
from domain.errors import DomainValidationError
from domain.models import require_id
from domain.money import Money
from domain.rules import RuleExpression

_SATISFACTION_VALUES = frozenset(
    {Decimal("0"), Decimal("0.25"), Decimal("0.5"), Decimal("0.75"), Decimal("1")}
)


def _decimal(value: Decimal | str | int, name: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise DomainValidationError(f"{name} must use exact decimal input")
    try:
        result = value if isinstance(value, Decimal) else Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise DomainValidationError(f"invalid {name}") from exc
    if not result.is_finite():
        raise DomainValidationError(f"{name} must be finite")
    return result


def _fraction(value: Decimal) -> Fraction:
    numerator, denominator = value.as_integer_ratio()
    return Fraction(numerator, denominator)


@dataclass(frozen=True, slots=True)
class BuyerConstraint:
    rule_id: str
    expression: RuleExpression
    reason_code: str
    display_reason: str
    exception_allowed: bool = False

    def __post_init__(self) -> None:
        require_id(self.rule_id, "rule_id")
        if not self.reason_code or not self.display_reason:
            raise DomainValidationError("buyer constraint reason is required")


@dataclass(frozen=True, slots=True)
class SellerAntiFitRule:
    rule_id: str
    expression: RuleExpression
    reason_code: str
    display_reason: str
    evidence_claim_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        require_id(self.rule_id, "rule_id")
        object.__setattr__(self, "evidence_claim_ids", tuple(self.evidence_claim_ids))
        if not self.reason_code or not self.display_reason:
            raise DomainValidationError("seller anti-fit reason is required")
        if not self.evidence_claim_ids:
            raise DomainValidationError("published hard anti-fit needs evidence claims")
        for claim_id in self.evidence_claim_ids:
            require_id(claim_id, "evidence_claim_id")


@dataclass(frozen=True, slots=True)
class PreferenceResult:
    criterion_id: str
    weight: int
    satisfaction: Decimal
    evidence_ids: tuple[str, ...] = ()
    unknown: bool = False

    def __init__(
        self,
        criterion_id: str,
        weight: int,
        satisfaction: Decimal | str | int,
        evidence_ids: tuple[str, ...] = (),
        unknown: bool = False,
    ) -> None:
        require_id(criterion_id, "criterion_id")
        if isinstance(weight, bool) or not isinstance(weight, int) or not 1 <= weight <= 5:
            raise DomainValidationError("preference weight must be an integer from 1 to 5")
        exact = _decimal(satisfaction, "satisfaction")
        if exact not in _SATISFACTION_VALUES:
            raise DomainValidationError("satisfaction must be one of 0, .25, .5, .75, 1")
        if unknown and exact != 0:
            raise DomainValidationError("unknown evidence must contribute zero")
        object.__setattr__(self, "criterion_id", criterion_id)
        object.__setattr__(self, "weight", weight)
        object.__setattr__(self, "satisfaction", exact)
        object.__setattr__(self, "evidence_ids", tuple(evidence_ids))
        object.__setattr__(self, "unknown", unknown)

    @property
    def contribution(self) -> Decimal:
        return Decimal(self.weight) * self.satisfaction


def exact_preference_score(results: tuple[PreferenceResult, ...]) -> Fraction:
    if not results:
        raise DomainValidationError("an eligible plan needs at least one preference criterion")
    numerator = sum(
        (Fraction(result.weight) * _fraction(result.satisfaction) for result in results),
        start=Fraction(0),
    )
    denominator = sum(result.weight for result in results)
    return Fraction(100) * numerator / denominator


@dataclass(frozen=True, slots=True)
class CandidateDefinition:
    candidate_id: str
    name: str
    pack_id: str
    pack_version: int
    available: bool = True
    evidence_block: CandidateStatus | None = None
    buyer_constraints: tuple[BuyerConstraint, ...] = ()
    seller_anti_fit_rules: tuple[SellerAntiFitRule, ...] = ()
    approved_exception_rule_ids: frozenset[str] = frozenset()
    dependency_state: TruthValue = TruthValue.TRUE
    preference_results: tuple[PreferenceResult, ...] = ()
    seller_positioning: str | None = None

    def __post_init__(self) -> None:
        require_id(self.candidate_id, "candidate_id")
        require_id(self.pack_id, "pack_id")
        if not self.name or self.pack_version < 1:
            raise DomainValidationError("candidate name and positive Pack version are required")
        if self.evidence_block not in {
            None,
            CandidateStatus.STALE_EVIDENCE,
            CandidateStatus.INSUFFICIENT_EVIDENCE,
            CandidateStatus.CONFLICTING_EVIDENCE,
        }:
            raise DomainValidationError("evidence_block must be an evidence blocking status")
        object.__setattr__(self, "buyer_constraints", tuple(self.buyer_constraints))
        object.__setattr__(self, "seller_anti_fit_rules", tuple(self.seller_anti_fit_rules))
        object.__setattr__(self, "preference_results", tuple(self.preference_results))
        object.__setattr__(
            self, "approved_exception_rule_ids", frozenset(self.approved_exception_rule_ids)
        )
        known_rules = {rule.rule_id for rule in self.buyer_constraints}
        if not self.approved_exception_rule_ids <= known_rules:
            raise DomainValidationError("an exception references an unknown buyer constraint")


@dataclass(frozen=True, slots=True)
class CandidateResult:
    candidate_id: str
    name: str
    pack_id: str
    pack_version: int
    status: CandidateStatus
    reason_code: str | None
    reason: str
    preference_results: tuple[PreferenceResult, ...]
    buyer_rule_id: str | None = None
    seller_rule_id: str | None = None
    evidence_claim_ids: tuple[str, ...] = ()
    unresolved_fields: tuple[str, ...] = ()
    seller_positioning: str | None = None

    def __post_init__(self) -> None:
        if self.status is CandidateStatus.SIRA_INELIGIBLE and not self.buyer_rule_id:
            raise DomainValidationError("SIRA_INELIGIBLE must identify the buyer rule")
        if self.status is CandidateStatus.SEIL_PASS and not self.seller_rule_id:
            raise DomainValidationError("SEIL_PASS must identify the published seller rule")
        if self.buyer_rule_id and self.seller_rule_id:
            raise DomainValidationError("buyer and seller rejection provenance cannot be conflated")
        object.__setattr__(self, "preference_results", tuple(self.preference_results))
        object.__setattr__(self, "evidence_claim_ids", tuple(self.evidence_claim_ids))
        object.__setattr__(self, "unresolved_fields", tuple(sorted(set(self.unresolved_fields))))


@dataclass(frozen=True, slots=True)
class SolutionPlan:
    plan_id: str
    action: SolutionAction
    component_ids: tuple[str, ...]
    status: CandidateStatus
    preference_results: tuple[PreferenceResult, ...]
    stack_risk: StackRisk
    total_cost: Money
    horizon_days: int
    required_evidence_coverage: Decimal
    maximum_evidence_age_ratio: Decimal
    seller_positioning: str | None = None
    stable_action_ids: tuple[str, ...] = ()

    def __init__(
        self,
        plan_id: str,
        action: SolutionAction,
        component_ids: tuple[str, ...],
        status: CandidateStatus,
        preference_results: tuple[PreferenceResult, ...],
        stack_risk: StackRisk,
        total_cost: Money,
        horizon_days: int,
        required_evidence_coverage: Decimal | str | int,
        maximum_evidence_age_ratio: Decimal | str | int,
        seller_positioning: str | None = None,
        stable_action_ids: tuple[str, ...] = (),
    ) -> None:
        require_id(plan_id, "plan_id")
        if horizon_days < 1:
            raise DomainValidationError("comparison horizon must be positive")
        coverage = _decimal(required_evidence_coverage, "required_evidence_coverage")
        age = _decimal(maximum_evidence_age_ratio, "maximum_evidence_age_ratio")
        if not Decimal(0) <= coverage <= Decimal(1):
            raise DomainValidationError("evidence coverage must be between zero and one")
        if age < 0:
            raise DomainValidationError("evidence age ratio cannot be negative")
        components = tuple(component_ids)
        for component_id in components:
            require_id(component_id, "component_id")
        if action is SolutionAction.BUY and not components:
            raise DomainValidationError("a BUY plan requires at least one component")
        stable = tuple(stable_action_ids) or (action.value, *components)
        object.__setattr__(self, "plan_id", plan_id)
        object.__setattr__(self, "action", action)
        object.__setattr__(self, "component_ids", components)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "preference_results", tuple(preference_results))
        object.__setattr__(self, "stack_risk", stack_risk)
        object.__setattr__(self, "total_cost", total_cost)
        object.__setattr__(self, "horizon_days", horizon_days)
        object.__setattr__(self, "required_evidence_coverage", coverage)
        object.__setattr__(self, "maximum_evidence_age_ratio", age)
        object.__setattr__(self, "seller_positioning", seller_positioning)
        object.__setattr__(self, "stable_action_ids", stable)

    @property
    def preference_score_exact(self) -> Fraction:
        return exact_preference_score(self.preference_results)

    @property
    def preference_score(self) -> Decimal:
        score = self.preference_score_exact
        with localcontext() as context:
            context.prec = 28
            return Decimal(score.numerator) / Decimal(score.denominator)


@dataclass(frozen=True, slots=True)
class Counterfactual:
    generic_winner_plan_id: str | None
    company_aware_winner_plan_id: str | None
    changed: bool
    decisive_private_fact_ids: tuple[str, ...]
    buyer_eliminations: tuple[tuple[str, str, str], ...]
    seller_passes: tuple[tuple[str, str, str], ...]
    coverage_statement: str
    uncertainties: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.changed and not self.decisive_private_fact_ids:
            raise DomainValidationError(
                "a changed counterfactual must identify decisive private facts"
            )
