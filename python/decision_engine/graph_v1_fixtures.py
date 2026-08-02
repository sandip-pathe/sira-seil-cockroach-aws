"""Loader for the checked-in, fictional Decision Graph v1 fixture."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from domain.enums import CandidateStatus, PackAuthority, SolutionAction, StackRisk
from domain.money import Money

from .bounds import ExactRatio
from .graph_v1_models import (
    CostLineItem,
    CurrentActionRecord,
    DecisionGraphInput,
    EvidencePolicy,
    EvidenceRecord,
    FactValue,
    FrozenFact,
    FrozenVersions,
    GateMode,
    GateRule,
    IdentityNormalization,
    NormalizationKind,
    OfferCost,
    OutcomeObservation,
    Predicate,
    PreferenceCriterion,
    ProductFact,
    RawCandidateRecord,
    RiskRule,
)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"fixture must be a JSON object: {path}")
    return value


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(UTC)


def _value(value: object) -> FactValue:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(value)
    raise ValueError(f"unsupported frozen fixture fact value: {value!r}")


def _ratio(value: object) -> ExactRatio:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(isinstance(item, int) for item in value)
    ):
        raise ValueError("an exact fixture ratio must be [numerator, denominator]")
    return ExactRatio(value[0], value[1])


def _money_bounds(
    identifier: str,
    values: Mapping[str, object],
    *,
    currency: str,
    line_items: tuple[CostLineItem, ...] = (),
    payment_required: bool = False,
) -> OfferCost:
    return OfferCost(
        identifier,
        Money(str(values["low"]), currency),
        Money(str(values["base"]), currency),
        Money(str(values["high"]), currency),
        line_items,
        payment_required,
    )


def _buyer_facts(root: Path, requirement: Mapping[str, Any]) -> tuple[FrozenFact, ...]:
    passport = _json(root / "buyer_passport.json")
    facts = [
        FrozenFact(
            fact_id=str(item["fact_id"]),
            field=str(item["field"]),
            value=_value(item["value"]),
            private=str(item["sensitivity"]) != "public",
            version=f"buyer_passport_v{passport['version']}",
        )
        for item in passport["facts"]
    ]
    data_profile = requirement["data_profile"]
    team = requirement["team"]
    usage = _json(root / "usage_outcomes.json")
    facts.extend(
        (
            FrozenFact(
                "rf_shared_client_workspace",
                "buyer.shared_client_workspace_required",
                bool(data_profile["shared_client_workspace_required"]),
                True,
                f"requirement_brief_v{requirement['version']}",
            ),
            FrozenFact(
                "rf_seat_count",
                "buyer.seat_count",
                int(team["seat_count"]),
                False,
                f"requirement_brief_v{requirement['version']}",
            ),
            FrozenFact(
                "bf_incumbent_outcome",
                "outcome.adoption_available",
                True,
                True,
                f"usage_outcomes_v{usage['version']}",
            ),
        )
    )
    return tuple(sorted(facts, key=lambda item: item.fact_id))


def _fee_adjusted_offers(
    root: Path,
) -> tuple[tuple[OfferCost, ...], dict[str, str], dict[str, str]]:
    raw_offers = _json(root / "offers.json")["offers"]
    fee = _json(root / "transaction_fee_policy.json")
    amount = str(fee["amount"])
    currency = str(fee["currency"])
    schedule = str(fee["schedule_version"])
    subtotals = fee["merchant_subtotals"]
    costs: list[OfferCost] = []
    candidate_offer: dict[str, str] = {}
    offer_evidence: dict[str, str] = {}
    fixture_suffix = {
        "fixture_low_price_policy_fail": "a",
        "fixture_honest_anti_fit": "b",
        "fixture_eligible_runner_up": "c",
        "fixture_selected_fit": "d",
    }
    for raw in raw_offers:
        offer_id = str(raw["offer_id"])
        candidate_id = str(raw["candidate_id"])
        landed = Money(str(raw["amount"]), currency)
        merchant_base = Money(str(subtotals[offer_id]), currency)
        merchant_high = Money(merchant_base.amount + 20, currency)
        fee_money = Money(amount, currency)
        line_items = (
            CostLineItem(
                "MERCHANT_SUBTOTAL",
                merchant_base,
                merchant_base,
                merchant_high,
            ),
            CostLineItem(
                "SIRA_TRANSACTION_FEE",
                fee_money,
                fee_money,
                fee_money,
                schedule,
            ),
        )
        costs.append(
            OfferCost(
                offer_id,
                landed,
                landed,
                Money(landed.amount + 20, currency),
                line_items,
                True,
            )
        )
        candidate_offer[candidate_id] = offer_id
        suffix = fixture_suffix[candidate_id]
        offer_evidence[offer_id] = f"ev_fixture_{suffix}_merchant"
    return tuple(costs), candidate_offer, offer_evidence


def _pack_records(
    root: Path,
    candidate_offer: Mapping[str, str],
    offer_evidence: Mapping[str, str],
) -> tuple[RawCandidateRecord, ...]:
    records: list[RawCandidateRecord] = []
    for path in sorted((root / "packs").glob("*.json")):
        pack = _json(path)
        pack_id = str(pack["pack_id"])
        claims = {
            str(item["claim_id"]): tuple(str(value) for value in item["evidence_ids"])
            for item in pack["claims"]
        }
        facts: list[ProductFact] = []
        for raw_fact in pack["facts"]:
            evidence_ids = tuple(
                sorted(
                    {
                        evidence_id
                        for claim_id in raw_fact["evidence_claim_ids"]
                        for evidence_id in claims[str(claim_id)]
                    }
                )
            )
            facts.append(
                ProductFact(str(raw_fact["field"]), _value(raw_fact["value"]), evidence_ids)
            )
        offer_id = candidate_offer[pack_id]
        offer = next(
            item for item in _json(root / "offers.json")["offers"] if item["offer_id"] == offer_id
        )
        facts.append(
            ProductFact("offer.landed_total", str(offer["amount"]), (offer_evidence[offer_id],))
        )
        identity = pack["identity"]
        records.append(
            RawCandidateRecord(
                record_id=f"record_{pack_id}",
                pack_id=pack_id,
                pack_version=int(pack["version"]),
                seller_id=str(pack["seller_id"]),
                product_id=str(pack["product_id"]),
                edition=str(identity["edition"]),
                region=str(identity["geographies"][0]),
                offer_id=offer_id,
                authority=PackAuthority.SELLER_SEALED,
                available=True,
                facts=tuple(facts),
                seller_gate_ids=tuple(str(item["rule_id"]) for item in pack["anti_fit_rules"]),
            )
        )
    return tuple(records)


def _evidence(root: Path) -> tuple[EvidenceRecord, ...]:
    records = [
        EvidenceRecord(
            evidence_id=str(item["evidence_id"]),
            record_id=str(item["candidate_id"]),
            source_class=str(item["owner_side"]),
            verification_method=str(item["verification_method"]),
            verification_scope=str(item["verification_scope"]),
            reconstructable=True,
            observed_at_lower=_time(str(item["verified_at"])),
            observed_at_upper=_time(str(item["verified_at"])),
            disputed=str(item["verification_state"]) == "disputed",
            revoked=str(item["verification_state"]) == "revoked",
        )
        for item in _json(root / "evidence.json")["evidence"]
    ]
    contract = _json(root / "contract.json")
    renewal = _json(root / "renewal_event.json")
    usage = _json(root / "usage_outcomes.json")
    records.extend(
        (
            EvidenceRecord(
                str(contract["evidence_id"]),
                str(contract["contract_id"]),
                "contract",
                "contract_review",
                "incumbent contract and current cost",
                True,
                _time(str(contract["observed_at_lower"])),
                _time(str(contract["observed_at_upper"])),
            ),
            EvidenceRecord(
                str(renewal["evidence_id"]),
                str(renewal["renewal_event_id"]),
                "contract",
                "contract_review",
                "incumbent renewal and resize quote",
                True,
                _time(str(renewal["observed_at_lower"])),
                _time(str(renewal["observed_at_upper"])),
            ),
            EvidenceRecord(
                str(usage["evidence_id"]),
                str(usage["instance_id"]),
                "usage_outcome",
                "usage_aggregation",
                "safe aggregate incumbent adoption outcome",
                True,
                _time(str(usage["observed_at_lower"])),
                _time(str(usage["observed_at_upper"])),
            ),
        )
    )
    return tuple(records)


def _evidence_policies(
    taxonomy: Mapping[str, Any], candidates: tuple[RawCandidateRecord, ...]
) -> tuple[EvidencePolicy, ...]:
    defaults = taxonomy["evidence_defaults"]
    fields = {fact.field for candidate in candidates for fact in candidate.facts}
    fields.update({"outcome.adoption"})
    return tuple(
        EvidencePolicy(
            field,
            tuple(str(item) for item in defaults["allowed_source_classes"]),
            tuple(str(item) for item in defaults["allowed_verification_methods"]),
            str(defaults["required_scope"]),
            int(defaults["freshness_sla_seconds"]),
        )
        for field in sorted(fields)
    )


def _gate_actions() -> tuple[SolutionAction, ...]:
    return (
        SolutionAction.REUSE_EXISTING,
        SolutionAction.CONFIGURE_EXISTING,
        SolutionAction.NO_ACTION,
        SolutionAction.BUY,
        SolutionAction.RENEW,
        SolutionAction.RESIZE,
        SolutionAction.REPLACE,
        SolutionAction.CONSOLIDATE,
    )


def _gates(root: Path, buyer_facts: tuple[FrozenFact, ...]) -> tuple[GateRule, ...]:
    purchase = _json(root / "purchase_brief.json")
    source_by_field = {fact.field: fact.fact_id for fact in buyer_facts}
    gates = [
        GateRule(
            gate_id=str(item["gate_id"]),
            predicates=(
                Predicate(str(item["field"]), str(item["operator"]), _value(item["value"])),
            ),
            mode=GateMode.REQUIRE_MATCH,
            blocked_status=CandidateStatus.SIRA_INELIGIBLE,
            reason_code=f"BUYER_POLICY_{str(item['gate_id']).upper()}",
            source_fact_ids=tuple(str(value) for value in item["source_fact_ids"]),
            applies_to_actions=_gate_actions(),
            permitted_resolution="PROCUREMENT_GATE" if bool(item["overridable"]) else None,
            overridable=bool(item["overridable"]),
        )
        for item in purchase["hard_gates"]
    ]
    for path in sorted((root / "packs").glob("*.json")):
        pack = _json(path)
        claim_evidence = {
            str(claim["claim_id"]): tuple(str(value) for value in claim["evidence_ids"])
            for claim in pack["claims"]
        }
        for item in pack["anti_fit_rules"]:
            predicates = tuple(
                Predicate(str(condition["field"]), str(condition["op"]), _value(condition["value"]))
                for condition in item["all"]
            )
            gates.append(
                GateRule(
                    gate_id=str(item["rule_id"]),
                    predicates=predicates,
                    mode=GateMode.BLOCK_ON_MATCH,
                    blocked_status=CandidateStatus.SEIL_PASS,
                    reason_code=str(item["reason_code"]),
                    source_fact_ids=tuple(
                        sorted(source_by_field[predicate.field] for predicate in predicates)
                    ),
                    applies_to_actions=(SolutionAction.REPLACE, SolutionAction.BUY),
                    evidence_claim_ids=tuple(
                        sorted(
                            {
                                evidence_id
                                for claim_id in item["evidence_claim_ids"]
                                for evidence_id in claim_evidence[str(claim_id)]
                            }
                        )
                    ),
                    permitted_resolution=None,
                )
            )
    return tuple(gates)


def _preferences(taxonomy: Mapping[str, Any]) -> tuple[PreferenceCriterion, ...]:
    allowed = tuple(ExactRatio(numerator, 4) for numerator in range(5))
    results: list[PreferenceCriterion] = []
    product_actions = tuple(action for action in _gate_actions())
    for item in taxonomy["preference_contracts"]:
        points = tuple(
            (int(point["maximum"]), _ratio(point["satisfaction"]))
            for point in item.get("points", [])
        )
        results.append(
            PreferenceCriterion(
                criterion_id=str(item["criterion_id"]),
                field=str(item["field"]),
                weight=int(item["weight"]),
                coverage_weight=int(item["coverage_weight"]),
                normalization=NormalizationKind(str(item["normalization"])),
                expected=_value(item.get("expected")),
                source_fact_ids=tuple(str(value) for value in item["source_fact_ids"]),
                applies_to_actions=(
                    tuple(SolutionAction)
                    if str(item["normalization"]) == NormalizationKind.OUTCOME_RATE.value
                    else product_actions
                ),
                allowed_satisfactions=allowed,
                lower_is_better_points=points,
                unknown_upper=_ratio(item["unknown_upper"]) if item.get("unknown_upper") else None,
                permitted_evidence_resolution=item.get("permitted_evidence_resolution"),
                neutral_prior=_ratio(item["neutral_prior"]) if item.get("neutral_prior") else None,
            )
        )
    return tuple(results)


def _risk_rules(taxonomy: Mapping[str, Any]) -> tuple[RiskRule, ...]:
    return tuple(
        RiskRule(
            rule_id=str(item["rule_id"]),
            actions=tuple(SolutionAction(value) for value in item["actions"]),
            predicate=None,
            lower=StackRisk(str(item["lower"])),
            base=StackRisk(str(item["base"])),
            upper=StackRisk(str(item["upper"])),
        )
        for item in taxonomy["risk_rules"]
    )


def _cost_line(item_type: str, cost: OfferCost) -> tuple[CostLineItem, ...]:
    assert cost.low is not None and cost.base is not None and cost.high is not None
    return (CostLineItem(item_type, cost.low, cost.base, cost.high),)


def _current_actions(
    root: Path,
    candidates: tuple[RawCandidateRecord, ...],
) -> tuple[CurrentActionRecord, ...]:
    contract = _json(root / "contract.json")
    renewal = _json(root / "renewal_event.json")
    incumbent = next(item for item in candidates if item.pack_id == contract["pack_id"])
    currency = str(contract["currency"])
    contract_evidence = str(contract["evidence_id"])
    renewal_evidence = str(renewal["evidence_id"])
    instance_id = str(contract["instance_id"])

    def with_cost_fact(cost: OfferCost, evidence_id: str) -> tuple[ProductFact, ...]:
        assert cost.base is not None
        return (
            *(fact for fact in incumbent.facts if fact.field != "offer.landed_total"),
            ProductFact("offer.landed_total", str(cost.base.amount), (evidence_id,)),
        )

    raw_costs = {
        SolutionAction.REUSE_EXISTING: _money_bounds(
            "current_reuse_cost", contract["reuse_cost"], currency=currency
        ),
        SolutionAction.CONFIGURE_EXISTING: _money_bounds(
            "current_configure_cost", contract["configuration_cost"], currency=currency
        ),
        SolutionAction.NO_ACTION: _money_bounds(
            "current_no_action_cost", contract["no_action_cost"], currency=currency
        ),
        SolutionAction.RENEW: _money_bounds(
            "current_renew_quote", renewal["renew_quote"], currency=currency
        ),
        SolutionAction.RESIZE: _money_bounds(
            "current_resize_quote", renewal["resize_quote"], currency=currency
        ),
        SolutionAction.CANCEL: _money_bounds(
            "current_cancel_cost", contract["cancel_cost"], currency=currency
        ),
    }
    actions: list[CurrentActionRecord] = []
    for action, raw_cost in raw_costs.items():
        cost = OfferCost(
            raw_cost.offer_id,
            raw_cost.low,
            raw_cost.base,
            raw_cost.high,
            _cost_line("CONTRACT_COST", raw_cost),
            False,
        )
        evidence_id = (
            renewal_evidence
            if action in {SolutionAction.RENEW, SolutionAction.RESIZE}
            else contract_evidence
        )
        facts = () if action is SolutionAction.CANCEL else with_cost_fact(cost, evidence_id)
        actions.append(
            CurrentActionRecord(
                action_id=f"current_{action.value.casefold()}",
                action=action,
                instance_id=instance_id,
                facts=facts,
                cost=cost,
            )
        )
    return tuple(actions)


def load_demo_decision_graph_input(root: Path | None = None) -> DecisionGraphInput:
    """Load the frozen demo from raw Packs, evidence, policy, contract, and usage."""

    fixture_root = root or Path(__file__).resolve().parents[2] / "fixtures" / "demo"
    requirement = _json(fixture_root / "requirement_brief.json")
    taxonomy = _json(fixture_root / "category_taxonomy.json")
    buyer_facts = _buyer_facts(fixture_root, requirement)
    offers, candidate_offer, offer_evidence = _fee_adjusted_offers(fixture_root)
    candidates = _pack_records(fixture_root, candidate_offer, offer_evidence)
    current_actions = _current_actions(fixture_root, candidates)
    normalization = _json(fixture_root / "identity_normalization.json")
    usage = _json(fixture_root / "usage_outcomes.json")
    outcome_values = tuple(
        OutcomeObservation(
            subject_id=str(usage["instance_id"]),
            criterion_id=str(item["criterion_id"]),
            value=ExactRatio(int(item["value"]["numerator"]), int(item["value"]["denominator"])),
            evidence_ids=(str(usage["evidence_id"]),),
            source_fact_ids=("bf_incumbent_outcome",),
        )
        for item in usage["safe_outcomes"]
    )
    return DecisionGraphInput(
        versions=FrozenVersions(
            request_version="purchase_brief_v1",
            company_profile_version="buyer_passport_v1",
            stackfile_version="stackfile_snapshot_v1",
            registry_version="demo_registry_v1",
            pack_set_version="demo_pack_set_v1",
            offer_set_version="demo_offer_set_v1_buyer_txn_demo_v1",
            taxonomy_version=str(taxonomy["taxonomy_version"]),
            normalization_version=str(taxonomy["normalization_version"]),
            policy_version="consultco_policy_v1",
            fx_version="usd_identity_fx_v1",
            pipeline_version="decision_graph_v1",
            engine_version="engine_v1",
        ),
        evaluated_at=_time(str(taxonomy["evaluated_at"])),
        buyer_facts=buyer_facts,
        candidates=candidates,
        offers=offers,
        evidence=_evidence(fixture_root),
        evidence_policies=_evidence_policies(taxonomy, candidates),
        gates=_gates(fixture_root, buyer_facts),
        preferences=_preferences(taxonomy),
        risk_rules=_risk_rules(taxonomy),
        risk_rule_set_complete=bool(taxonomy["risk_rule_set_complete"]),
        current_actions=current_actions,
        identity_normalization=IdentityNormalization(
            str(normalization["version"]),
            tuple((str(item["source"]), str(item["target"])) for item in normalization["aliases"]),
        ),
        outcome_values=outcome_values,
    )


__all__ = ["load_demo_decision_graph_input"]
