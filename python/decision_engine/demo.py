"""Path-based loader for the checked-in, fictional deterministic demo.

This module is deliberately a fixture compiler, not a production provider.  It
turns the versioned JSON artifacts into the same pure rule and ranking objects
used by API and persistence adapters.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from domain.enums import (
    CandidateStatus,
    RuleOperator,
    SolutionAction,
    StackRisk,
    TruthValue,
)
from domain.errors import DomainValidationError
from domain.money import Money
from domain.publication import assert_public_payload
from domain.rules import RuleCondition, RuleExpression, resolve_field

from .counterfactual import build_counterfactual
from .evaluation import evaluate_candidate
from .models import (
    BuyerConstraint,
    CandidateDefinition,
    CandidateResult,
    Counterfactual,
    PreferenceResult,
    SellerAntiFitRule,
    SolutionPlan,
)
from .ranking import rank_solution_plans


@dataclass(frozen=True, slots=True)
class DemoDecision:
    candidate_results: tuple[CandidateResult, ...]
    generic_plans: tuple[SolutionPlan, ...]
    company_aware_plans: tuple[SolutionPlan, ...]
    generic_winner: SolutionPlan
    selected_plan: SolutionPlan
    counterfactual: Counterfactual


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DomainValidationError(f"fixture root must be an object: {path}")
    return value


def _set_dotted(target: dict[str, Any], path: str, value: Any) -> None:
    segments = path.split(".")
    current = target
    for segment in segments[:-1]:
        child = current.setdefault(segment, {})
        if not isinstance(child, dict):
            raise DomainValidationError(f"conflicting fixture field: {path}")
        current = child
    current[segments[-1]] = value


def _expression(raw: Mapping[str, Any]) -> RuleExpression:
    condition_values = raw.get("all") if "all" in raw else raw.get("any")
    mode: Literal["all", "any"] = "all" if "all" in raw else "any"
    if not isinstance(condition_values, list):
        raise DomainValidationError("fixture rule must contain all or any conditions")
    return RuleExpression(
        tuple(
            RuleCondition(
                field=str(condition["field"]),
                operator=RuleOperator(str(condition.get("op", condition.get("operator")))),
                value=condition.get("value"),
            )
            for condition in condition_values
        ),
        mode=mode,
    )


def _buyer_constraints(purchase_brief: Mapping[str, Any]) -> tuple[BuyerConstraint, ...]:
    constraints: list[BuyerConstraint] = []
    for gate in purchase_brief.get("hard_gates", ()):
        expression = RuleExpression(
            (
                RuleCondition(
                    field=str(gate["field"]),
                    operator=RuleOperator(str(gate["operator"])),
                    value=gate.get("value"),
                ),
            )
        )
        constraints.append(
            BuyerConstraint(
                rule_id=str(gate["gate_id"]),
                expression=expression,
                reason_code=str(gate["gate_id"]).upper(),
                display_reason=f"Buyer requirement failed: {gate['field']}",
                exception_allowed=bool(gate.get("overridable", False)),
            )
        )
    return tuple(constraints)


def _anti_fit_rules(pack: Mapping[str, Any]) -> tuple[SellerAntiFitRule, ...]:
    return tuple(
        SellerAntiFitRule(
            rule_id=str(rule["rule_id"]),
            expression=_expression(rule),
            reason_code=str(rule["reason_code"]),
            display_reason=str(rule["display_reason"]),
            evidence_claim_ids=tuple(str(value) for value in rule["evidence_claim_ids"]),
        )
        for rule in pack.get("anti_fit_rules", ())
    )


def _seller_context(requirement_brief: Mapping[str, Any]) -> dict[str, Any]:
    team = requirement_brief.get("team", {})
    data_profile = requirement_brief.get("data_profile", {})
    stack = requirement_brief.get("allowed_stack_context", {})
    return {
        "buyer": {
            "seat_count": team.get("seat_count"),
            "shared_client_workspace_required": data_profile.get(
                "shared_client_workspace_required"
            ),
            "client_conversations_restricted": data_profile.get("client_conversations_restricted"),
            "required_integrations": stack.get("required_integrations"),
        }
    }


def _dependency_state(pack: Mapping[str, Any], seller_context: Mapping[str, Any]) -> TruthValue:
    state = TruthValue.TRUE
    for rule in pack.get("dependency_rules", ()):
        # A soft dependency affects implementation/risk but does not make the
        # plan non-executable in the frozen first-build fixture.
        if rule.get("severity") != "hard":
            continue
        value = _expression(rule).evaluate(seller_context).value
        if value is TruthValue.FALSE:
            return TruthValue.FALSE
        if value is TruthValue.UNRESOLVED:
            state = TruthValue.UNRESOLVED
    return state


def _facts(pack: Mapping[str, Any], offer: Mapping[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for fact in pack.get("facts", ()):
        _set_dotted(context, str(fact["field"]), fact.get("value"))
    _set_dotted(context, "offer.landed_total", offer["amount"])
    return context


def _preference_results(
    purchase_brief: Mapping[str, Any],
    context: Mapping[str, Any],
) -> tuple[PreferenceResult, ...]:
    output: list[PreferenceResult] = []
    for preference in purchase_brief.get("preferences", ()):
        found, actual = resolve_field(context, str(preference["field"]))
        unknown = not found or actual is None
        satisfaction = Decimal(0)
        if not unknown:
            normalization = preference["normalization"]
            if normalization["kind"] == "boolean":
                satisfaction = Decimal(1) if bool(actual) else Decimal(0)
            elif normalization["kind"] == "lower_is_better":
                actual_value = Decimal(str(actual))
                best = Decimal(str(normalization["best_at_or_below"]))
                acceptable = Decimal(str(normalization["acceptable_at_or_below"]))
                if actual_value <= best:
                    satisfaction = Decimal(1)
                elif actual_value <= acceptable:
                    satisfaction = Decimal("0.75")
                else:
                    satisfaction = Decimal(0)
            else:
                raise DomainValidationError("unsupported fixture normalization")
        output.append(
            PreferenceResult(
                criterion_id=str(preference["criterion_id"]),
                weight=int(preference["weight"]),
                satisfaction=satisfaction,
                unknown=unknown,
            )
        )
    return tuple(output)


def _stack_risk(context: Mapping[str, Any]) -> StackRisk:
    _, admin_hours = resolve_field(context, "product.admin_hours_per_month")
    _, deployment_days = resolve_field(context, "product.deployment_days")
    if admin_hours is not None and deployment_days is not None:
        if Decimal(str(admin_hours)) <= 2 and Decimal(str(deployment_days)) <= 1:
            return StackRisk.LOW
    return StackRisk.MEDIUM


def _positioning(pack: Mapping[str, Any]) -> str | None:
    angles = pack.get("positioning_angles", ())
    return str(angles[0]["text"]) if angles else None


def _plan(
    candidate: CandidateDefinition,
    result: CandidateResult,
    offer: Mapping[str, Any],
    context: Mapping[str, Any],
) -> SolutionPlan:
    return SolutionPlan(
        plan_id=f"sol_{candidate.candidate_id}",
        action=SolutionAction.BUY,
        component_ids=(candidate.candidate_id,),
        status=result.status,
        preference_results=candidate.preference_results,
        stack_risk=_stack_risk(context),
        total_cost=Money(str(offer["amount"]), str(offer["currency"])),
        horizon_days=int(offer["horizon_days"]),
        required_evidence_coverage=1,
        maximum_evidence_age_ratio=Decimal("0.01"),
        seller_positioning=candidate.seller_positioning,
    )


def _generic_plan(plan: SolutionPlan) -> SolutionPlan:
    # Generic shopping has no private policy rubric. Give each product the same
    # neutral supported-JTBD score so exact price becomes the next tie-breaker.
    return SolutionPlan(
        plan_id=plan.plan_id,
        action=plan.action,
        component_ids=plan.component_ids,
        status=CandidateStatus.ELIGIBLE,
        preference_results=(PreferenceResult("generic_jtbd", 1, 1),),
        stack_risk=StackRisk.LOW,
        total_cost=plan.total_cost,
        horizon_days=plan.horizon_days,
        required_evidence_coverage=1,
        maximum_evidence_age_ratio=Decimal("0.01"),
    )


def evaluate_demo(
    fixtures_directory: str | Path,
    *,
    purchase_brief_override: Mapping[str, Any] | None = None,
    requirement_brief_override: Mapping[str, Any] | None = None,
) -> DemoDecision:
    """Replay the four-Pack narrative against a supplied or checked-in buyer rubric.

    The override keeps policy-version evaluation inside the pure decision layer.  It is
    an already-validated Purchase Brief mapping; provider, persistence, and API objects
    remain outside this module.
    """

    root = Path(fixtures_directory)
    purchase_brief = (
        purchase_brief_override
        if purchase_brief_override is not None
        else _load_object(root / "purchase_brief.json")
    )
    requirement_brief = (
        requirement_brief_override
        if requirement_brief_override is not None
        else _load_object(root / "requirement_brief.json")
    )
    assert_public_payload(requirement_brief)
    offers_document = _load_object(root / "offers.json")
    offers = {str(offer["candidate_id"]): offer for offer in offers_document.get("offers", ())}
    pack_paths = sorted((root / "packs").glob("*.json"))
    if len(pack_paths) != 4:
        raise DomainValidationError("the deterministic demo requires exactly four Packs")

    constraints = _buyer_constraints(purchase_brief)
    seller_context = _seller_context(requirement_brief)
    candidates: list[CandidateDefinition] = []
    contexts: dict[str, dict[str, Any]] = {}
    for pack_path in pack_paths:
        pack = _load_object(pack_path)
        candidate_id = str(pack["pack_id"])
        if candidate_id not in offers:
            raise DomainValidationError(f"demo offer missing for {candidate_id}")
        context = _facts(pack, offers[candidate_id])
        contexts[candidate_id] = context
        candidate = CandidateDefinition(
            candidate_id=candidate_id,
            name=str(pack["identity"]["product_name"]),
            pack_id=candidate_id,
            pack_version=int(pack["version"]),
            buyer_constraints=constraints,
            seller_anti_fit_rules=_anti_fit_rules(pack),
            dependency_state=_dependency_state(pack, seller_context),
            preference_results=_preference_results(purchase_brief, context),
            seller_positioning=_positioning(pack),
        )
        candidates.append(candidate)

    results = tuple(
        evaluate_candidate(
            candidate,
            buyer_evaluation_context=contexts[candidate.candidate_id],
            sanitized_seller_context=seller_context,
        )
        for candidate in sorted(candidates, key=lambda value: value.candidate_id)
    )
    result_by_id = {result.candidate_id: result for result in results}
    company_plans = tuple(
        _plan(
            candidate,
            result_by_id[candidate.candidate_id],
            offers[candidate.candidate_id],
            contexts[candidate.candidate_id],
        )
        for candidate in sorted(candidates, key=lambda value: value.candidate_id)
    )
    generic_plans = tuple(_generic_plan(plan) for plan in company_plans)
    generic_ranked = rank_solution_plans(generic_plans)
    company_ranked = rank_solution_plans(company_plans)
    if not generic_ranked or not company_ranked:
        raise DomainValidationError("demo must produce generic and company-aware winners")

    generic_candidate_id = generic_ranked[0].component_ids[0]
    generic_result = result_by_id[generic_candidate_id]
    decisive_fact_ids: tuple[str, ...] = ()
    if generic_result.buyer_rule_id:
        for gate in purchase_brief.get("hard_gates", ()):
            if gate["gate_id"] == generic_result.buyer_rule_id:
                decisive_fact_ids = tuple(str(value) for value in gate["source_fact_ids"])
                break
    counterfactual = build_counterfactual(
        generic_plans=generic_plans,
        company_aware_plans=company_plans,
        company_candidate_results=results,
        decisive_private_fact_ids=decisive_fact_ids,
        coverage_statement="Best supported action among four executable Packs",
    )
    return DemoDecision(
        candidate_results=results,
        generic_plans=generic_plans,
        company_aware_plans=company_plans,
        generic_winner=generic_ranked[0],
        selected_plan=company_ranked[0],
        counterfactual=counterfactual,
    )
