"""Loader for the checked-in, fictional Decision Graph v1 fixture."""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from domain import DomainValidationError, content_hash
from domain.enums import CandidateStatus, PackAuthority, SolutionAction, StackRisk
from domain.money import Money

from .bounds import ExactRatio
from .graph_v1_models import (
    ActorConflictResolution,
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
    RecallPolicy,
    RiskRule,
)


def _actor_authority(role: str, kind: str) -> tuple[str, int]:
    if role == "requester":
        return "REQUESTER", 100
    if role == "cardholder":
        return "TRANSACTION_AUTHORITY", 200
    if role.endswith("_owner"):
        level = "POLICY_OWNER" if kind in {"hard_constraint", "authority"} else "DOMAIN_OWNER"
        return level, 300
    return "UNKNOWN", 0


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"fixture must be a JSON object: {path}")
    return value


@dataclass(frozen=True, slots=True)
class DecisionSourceBundle:
    """Credential-free, immutable source documents for one deterministic compilation."""

    buyer_passport: dict[str, Any]
    purchase_brief: dict[str, Any]
    requirement_brief: dict[str, Any]
    stack_lock: dict[str, Any]
    packs: tuple[dict[str, Any], ...]
    offers: dict[str, Any]
    evidence: dict[str, Any]
    transaction_fee_policy: dict[str, Any]
    contract: dict[str, Any]
    renewal_event: dict[str, Any]
    usage_outcomes: dict[str, Any]
    category_taxonomy: dict[str, Any]
    identity_normalization: dict[str, Any]
    versions: dict[str, str]

    @classmethod
    def from_directory(cls, root: Path) -> DecisionSourceBundle:
        return cls(
            buyer_passport=_json(root / "buyer_passport.json"),
            purchase_brief=_json(root / "purchase_brief.json"),
            requirement_brief=_json(root / "requirement_brief.json"),
            stack_lock=_json(root / "stackfile.lock.json"),
            packs=tuple(_json(path) for path in sorted((root / "packs").glob("*.json"))),
            offers=_json(root / "offers.json"),
            evidence=_json(root / "evidence.json"),
            transaction_fee_policy=_json(root / "transaction_fee_policy.json"),
            contract=_json(root / "contract.json"),
            renewal_event=_json(root / "renewal_event.json"),
            usage_outcomes=_json(root / "usage_outcomes.json"),
            category_taxonomy=_json(root / "category_taxonomy.json"),
            identity_normalization=_json(root / "identity_normalization.json"),
            versions={
                "registry": "demo_registry_v1",
                "pack_set": "demo_pack_set_v1",
                "offer_set": "demo_offer_set_v1_buyer_txn_demo_v1",
                "fx": "usd_identity_fx_v1",
                "pipeline": "decision_graph_v1",
                "engine": "engine_v1",
            },
        )

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> DecisionSourceBundle:
        required_documents = (
            "buyer_passport",
            "purchase_brief",
            "requirement_brief",
            "stack_lock",
            "offers",
            "evidence",
            "transaction_fee_policy",
            "contract",
            "renewal_event",
            "usage_outcomes",
            "category_taxonomy",
            "identity_normalization",
        )
        documents: dict[str, dict[str, Any]] = {}
        for name in required_documents:
            value = payload.get(name)
            if not isinstance(value, dict):
                raise ValueError(f"decision source {name} must be an object")
            documents[name] = deepcopy(value)
        raw_packs = payload.get("packs")
        if not isinstance(raw_packs, list) or not raw_packs or any(
            not isinstance(item, dict) for item in raw_packs
        ):
            raise ValueError("decision source packs must be a non-empty array of objects")
        raw_versions = payload.get("versions")
        if not isinstance(raw_versions, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in raw_versions.items()
        ):
            raise ValueError("decision source versions must be a string map")
        return cls(
            **documents,
            packs=tuple(deepcopy(item) for item in raw_packs),
            versions=deepcopy(raw_versions),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "buyer_passport": deepcopy(self.buyer_passport),
            "purchase_brief": deepcopy(self.purchase_brief),
            "requirement_brief": deepcopy(self.requirement_brief),
            "stack_lock": deepcopy(self.stack_lock),
            "packs": [deepcopy(item) for item in self.packs],
            "offers": deepcopy(self.offers),
            "evidence": deepcopy(self.evidence),
            "transaction_fee_policy": deepcopy(self.transaction_fee_policy),
            "contract": deepcopy(self.contract),
            "renewal_event": deepcopy(self.renewal_event),
            "usage_outcomes": deepcopy(self.usage_outcomes),
            "category_taxonomy": deepcopy(self.category_taxonomy),
            "identity_normalization": deepcopy(self.identity_normalization),
            "versions": deepcopy(self.versions),
        }


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
    horizon_days: int,
    line_items: tuple[CostLineItem, ...] = (),
    payment_required: bool = False,
) -> OfferCost:
    return OfferCost(
        identifier,
        Money(str(values["low"]), currency),
        Money(str(values["base"]), currency),
        Money(str(values["high"]), currency),
        horizon_days,
        line_items,
        payment_required,
    )


def _buyer_facts(
    source: DecisionSourceBundle, requirement: Mapping[str, Any]
) -> tuple[FrozenFact, ...]:
    passport = source.buyer_passport
    allowed_roles = {
        str(item["role"])
        for item in passport["stakeholders"]
    } | set(_field_owner_roles(source.purchase_brief).values())
    facts: list[FrozenFact] = []
    for item in passport["facts"]:
        role = str(item["stakeholder_role"])
        if role not in allowed_roles:
            raise DomainValidationError(f"buyer fact uses undeclared actor role {role}")
        authority_level, authority_rank = _actor_authority(role, str(item["kind"]))
        facts.append(
            FrozenFact(
                fact_id=str(item["fact_id"]),
                field=str(item["field"]),
                value=_value(item["value"]),
                private=str(item["sensitivity"]) != "public",
                version=f"buyer_passport_v{passport['version']}",
                asserted_by_role=role,
                authority_level=authority_level,
                authority_rank=authority_rank,
            )
        )
    data_profile = requirement["data_profile"]
    team = requirement["team"]
    usage = source.usage_outcomes
    facts.extend(
        (
            FrozenFact(
                "rf_shared_client_workspace",
                "buyer.shared_client_workspace_required",
                bool(data_profile["shared_client_workspace_required"]),
                True,
                f"requirement_brief_v{requirement['version']}",
                "requester",
                "REQUESTER",
                100,
            ),
            FrozenFact(
                "rf_seat_count",
                "buyer.seat_count",
                int(team["seat_count"]),
                False,
                f"requirement_brief_v{requirement['version']}",
                "requester",
                "REQUESTER",
                100,
            ),
            FrozenFact(
                "bf_required_integrations",
                "buyer.required_integrations",
                _value(passport["operational_preferences"]["required_integrations"]),
                True,
                f"buyer_passport_v{passport['version']}",
                "stack_owner",
                "DOMAIN_OWNER",
                300,
            ),
            FrozenFact(
                "bf_incumbent_outcome",
                "outcome.adoption_available",
                True,
                True,
                f"usage_outcomes_v{usage['version']}",
                "system_observation",
                "OBSERVATION",
                50,
            ),
        )
    )
    return tuple(sorted(facts, key=lambda item: item.fact_id))


def _field_owner_roles(purchase_brief: Mapping[str, Any]) -> dict[str, str]:
    owners: dict[str, str] = {}
    for item in (*purchase_brief["hard_gates"], *purchase_brief["preferences"]):
        field = str(item["field"])
        role = str(item["owner_role"])
        previous = owners.get(field)
        if previous is not None and previous != role:
            raise DomainValidationError(f"purchase brief has conflicting owners for {field}")
        owners[field] = role
    return owners


def _resolve_actor_conflicts(
    facts: tuple[FrozenFact, ...], purchase_brief: Mapping[str, Any]
) -> tuple[tuple[FrozenFact, ...], tuple[ActorConflictResolution, ...]]:
    by_field: dict[str, list[FrozenFact]] = {}
    for fact in facts:
        by_field.setdefault(fact.field, []).append(fact)

    raw_resolutions = purchase_brief.get("actor_conflict_resolutions", [])
    if not isinstance(raw_resolutions, list):
        raise DomainValidationError("actor_conflict_resolutions must be an array")
    explicit_by_field: dict[str, Mapping[str, Any]] = {}
    for item in raw_resolutions:
        if not isinstance(item, Mapping):
            raise DomainValidationError("actor conflict resolution must be an object")
        field = str(item.get("field", ""))
        if not field or field in explicit_by_field:
            raise DomainValidationError("actor conflict resolutions require unique fields")
        explicit_by_field[field] = item

    owner_roles = _field_owner_roles(purchase_brief)
    selected: list[FrozenFact] = []
    resolutions: list[ActorConflictResolution] = []
    conflicted_fields: set[str] = set()
    for field, field_facts in sorted(by_field.items()):
        value_groups = {
            content_hash(fact.value): fact.value
            for fact in field_facts
        }
        if len(value_groups) == 1:
            selected.extend(field_facts)
            continue

        conflicted_fields.add(field)
        ranked = sorted(
            field_facts,
            key=lambda item: (-item.authority_rank, item.fact_id),
        )
        highest_rank = ranked[0].authority_rank
        highest = [fact for fact in ranked if fact.authority_rank == highest_rank]
        chosen: FrozenFact
        strategy: str
        decided_by_role: str
        reason: str
        if len({content_hash(fact.value) for fact in highest}) == 1:
            chosen = highest[0]
            strategy = "AUTHORITY_PRECEDENCE"
            decided_by_role = chosen.asserted_by_role
            reason = "Unique highest-authority assertion controls this field."
        else:
            explicit = explicit_by_field.get(field)
            if explicit is None:
                raise DomainValidationError(
                    f"unresolved equal-authority actor conflict for {field}"
                )
            decided_by_role = str(explicit.get("decided_by_role", ""))
            required_owner = owner_roles.get(field)
            if required_owner is None or decided_by_role != required_owner:
                owner_label = required_owner or "declared field owner"
                raise DomainValidationError(
                    f"actor conflict for {field} requires decision by {owner_label}"
                )
            selected_fact_id = str(explicit.get("selected_fact_id", ""))
            matched = next(
                (fact for fact in field_facts if fact.fact_id == selected_fact_id),
                None,
            )
            if matched is None:
                raise DomainValidationError(
                    f"actor conflict for {field} selected an unknown fact"
                )
            chosen = matched
            strategy = "EXPLICIT_OWNER_DECISION"
            reason = str(explicit.get("reason", "")).strip()
            if not reason:
                raise DomainValidationError(
                    f"actor conflict for {field} requires a decision reason"
                )
        selected.append(chosen)
        resolutions.append(
            ActorConflictResolution(
                field=field,
                fact_ids=tuple(fact.fact_id for fact in field_facts),
                selected_fact_id=chosen.fact_id,
                selected_role=chosen.asserted_by_role,
                decided_by_role=decided_by_role,
                strategy=strategy,
                reason=reason,
            )
        )

    unexpected = set(explicit_by_field) - conflicted_fields
    if unexpected:
        raise DomainValidationError(
            "actor conflict resolutions reference non-conflicting fields: "
            + ", ".join(sorted(unexpected))
        )
    return (
        tuple(sorted(selected, key=lambda item: item.fact_id)),
        tuple(sorted(resolutions, key=lambda item: item.field)),
    )


def _fee_adjusted_offers(
    source: DecisionSourceBundle,
) -> tuple[tuple[OfferCost, ...], dict[str, str], dict[str, str]]:
    raw_offers = source.offers["offers"]
    fee = source.transaction_fee_policy
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
                int(raw["horizon_days"]),
                line_items,
                True,
            )
        )
        candidate_offer[candidate_id] = offer_id
        suffix = fixture_suffix[candidate_id]
        offer_evidence[offer_id] = f"ev_fixture_{suffix}_merchant"
    return tuple(costs), candidate_offer, offer_evidence


def _pack_records(
    source: DecisionSourceBundle,
    candidate_offer: Mapping[str, str],
    offer_evidence: Mapping[str, str],
) -> tuple[RawCandidateRecord, ...]:
    records: list[RawCandidateRecord] = []
    for pack in sorted(source.packs, key=lambda item: str(item["pack_id"])):
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
                ProductFact(
                    str(raw_fact["field"]),
                    _value(raw_fact["value"]),
                    evidence_ids,
                    str(pack["product_id"]),
                )
            )
        offer_id = candidate_offer[pack_id]
        offer = next(
            item for item in source.offers["offers"] if item["offer_id"] == offer_id
        )
        facts.append(
            ProductFact(
                "offer.landed_total",
                str(offer["amount"]),
                (offer_evidence[offer_id],),
                str(pack["product_id"]),
            )
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
                seller_gate_ids=tuple(
                    str(item["rule_id"])
                    for item in (*pack["anti_fit_rules"], *pack["dependency_rules"])
                ),
                category_ids=tuple(str(value) for value in pack["category_ids"]),
                jtbd_ids=tuple(str(value) for value in pack["jtbd_ids"]),
                pack_status=str(pack["status"]).upper(),
                required_product_ids=tuple(
                    str(item["required_product_id"])
                    for item in pack.get("component_dependencies", [])
                    if bool(item.get("required", True))
                ),
            )
        )
    return tuple(records)


def _evidence(source: DecisionSourceBundle) -> tuple[EvidenceRecord, ...]:
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
        for item in source.evidence["evidence"]
    ]
    contract = source.contract
    renewal = source.renewal_event
    usage = source.usage_outcomes
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


def _gates(
    source: DecisionSourceBundle,
    buyer_facts: tuple[FrozenFact, ...],
    actor_conflicts: tuple[ActorConflictResolution, ...],
) -> tuple[GateRule, ...]:
    purchase = source.purchase_brief
    source_by_field = {fact.field: fact.fact_id for fact in buyer_facts}
    selected_conflict_fields = {item.field for item in actor_conflicts}
    fact_by_field = {fact.field: fact for fact in buyer_facts}
    fact_by_id = {fact.fact_id: fact for fact in buyer_facts}
    for item in purchase["hard_gates"]:
        field = str(item["field"])
        if field in selected_conflict_fields:
            continue
        source_ids = tuple(str(value) for value in item["source_fact_ids"])
        source_facts = [fact_by_id.get(fact_id) for fact_id in source_ids]
        if any(fact is None or fact.field != field for fact in source_facts):
            raise DomainValidationError(f"hard gate {item['gate_id']} has invalid fact lineage")
        expected_hash = content_hash(_value(item["value"]))
        if any(content_hash(fact.value) != expected_hash for fact in source_facts if fact):
            raise DomainValidationError(
                f"hard gate {item['gate_id']} disagrees with its source facts"
            )
    gates = [
        GateRule(
            gate_id=str(item["gate_id"]),
            predicates=(
                Predicate(
                    str(item["field"]),
                    str(item["operator"]),
                    fact_by_field[str(item["field"])].value
                    if str(item["field"]) in selected_conflict_fields
                    else _value(item["value"]),
                ),
            ),
            mode=GateMode.REQUIRE_MATCH,
            blocked_status=CandidateStatus.SIRA_INELIGIBLE,
            reason_code=f"BUYER_POLICY_{str(item['gate_id']).upper()}",
            source_fact_ids=(source_by_field[str(item["field"])],)
            if str(item["field"]) in selected_conflict_fields
            else tuple(str(value) for value in item["source_fact_ids"]),
            applies_to_actions=_gate_actions(),
            permitted_resolution="PROCUREMENT_GATE" if bool(item["overridable"]) else None,
            overridable=bool(item["overridable"]),
        )
        for item in purchase["hard_gates"]
    ]
    for pack in sorted(source.packs, key=lambda item: str(item["pack_id"])):
        claim_evidence = {
            str(claim["claim_id"]): tuple(str(value) for value in claim["evidence_ids"])
            for claim in pack["claims"]
        }
        for item in pack["anti_fit_rules"]:
            predicates = tuple(
                Predicate(
                    str(condition["field"]),
                    str(condition["op"]),
                    _value(condition["value"]),
                )
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
        for item in pack["dependency_rules"]:
            predicates = tuple(
                Predicate(
                    str(condition["field"]),
                    str(condition["op"]),
                    _value(condition["value"]),
                )
                for condition in item["all"]
            )
            gates.append(
                GateRule(
                    gate_id=str(item["rule_id"]),
                    predicates=predicates,
                    mode=GateMode.REQUIRE_MATCH,
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
                    permitted_resolution="SELLER_DEPENDENCY_RESOLUTION"
                    if str(item["severity"]) == "soft"
                    else None,
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
                aggregation=str(item.get("aggregation", "PRIMARY_COMPONENT")),
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
    source: DecisionSourceBundle,
    candidates: tuple[RawCandidateRecord, ...],
) -> tuple[CurrentActionRecord, ...]:
    contract = source.contract
    renewal = source.renewal_event
    incumbent = next(item for item in candidates if item.pack_id == contract["pack_id"])
    currency = str(contract["currency"])
    horizon_days = int(
        source.requirement_brief["team"]["comparison_horizon_days"]
    )
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
            "current_reuse_cost",
            contract["reuse_cost"],
            currency=currency,
            horizon_days=horizon_days,
        ),
        SolutionAction.CONFIGURE_EXISTING: _money_bounds(
            "current_configure_cost",
            contract["configuration_cost"],
            currency=currency,
            horizon_days=horizon_days,
        ),
        SolutionAction.NO_ACTION: _money_bounds(
            "current_no_action_cost",
            contract["no_action_cost"],
            currency=currency,
            horizon_days=horizon_days,
        ),
        SolutionAction.RENEW: _money_bounds(
            "current_renew_quote",
            renewal["renew_quote"],
            currency=currency,
            horizon_days=horizon_days,
        ),
        SolutionAction.RESIZE: _money_bounds(
            "current_resize_quote",
            renewal["resize_quote"],
            currency=currency,
            horizon_days=horizon_days,
        ),
        SolutionAction.CANCEL: _money_bounds(
            "current_cancel_cost",
            contract["cancel_cost"],
            currency=currency,
            horizon_days=horizon_days,
        ),
    }
    actions: list[CurrentActionRecord] = []
    for action, raw_cost in raw_costs.items():
        cost = OfferCost(
            raw_cost.offer_id,
            raw_cost.low,
            raw_cost.base,
            raw_cost.high,
            raw_cost.horizon_days,
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


def compile_decision_graph_input(source: DecisionSourceBundle) -> DecisionGraphInput:
    """Compile typed deterministic input from a complete credential-free source bundle."""

    requirement = source.requirement_brief
    taxonomy = source.category_taxonomy
    buyer_facts, actor_conflicts = _resolve_actor_conflicts(
        _buyer_facts(source, requirement), source.purchase_brief
    )
    offers, candidate_offer, offer_evidence = _fee_adjusted_offers(source)
    candidates = _pack_records(source, candidate_offer, offer_evidence)
    current_actions = _current_actions(source, candidates)
    normalization = source.identity_normalization
    usage = source.usage_outcomes
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
            request_version=f"purchase_brief_v{source.purchase_brief['version']}",
            company_profile_version=f"buyer_passport_v{source.buyer_passport['version']}",
            stackfile_version=f"stackfile_snapshot_v{source.stack_lock['snapshot']}",
            registry_version=source.versions["registry"],
            pack_set_version=source.versions["pack_set"],
            offer_set_version=source.versions["offer_set"],
            taxonomy_version=str(taxonomy["taxonomy_version"]),
            normalization_version=str(taxonomy["normalization_version"]),
            policy_version="consultco_policy_v1",
            fx_version=source.versions["fx"],
            pipeline_version=source.versions["pipeline"],
            engine_version=source.versions["engine"],
        ),
        evaluated_at=_time(str(taxonomy["evaluated_at"])),
        buyer_facts=buyer_facts,
        candidates=candidates,
        offers=offers,
        evidence=_evidence(source),
        evidence_policies=_evidence_policies(taxonomy, candidates),
        gates=_gates(source, buyer_facts, actor_conflicts),
        preferences=_preferences(taxonomy),
        risk_rules=_risk_rules(taxonomy),
        risk_rule_set_complete=bool(taxonomy["risk_rule_set_complete"]),
        current_actions=current_actions,
        identity_normalization=IdentityNormalization(
            str(normalization["version"]),
            tuple((str(item["source"]), str(item["target"])) for item in normalization["aliases"]),
        ),
        outcome_values=outcome_values,
        actor_conflict_resolutions=actor_conflicts,
        recall_policy=RecallPolicy(
            category_id=str(source.purchase_brief["category_id"]),
            jtbd_id=str(source.purchase_brief["desired_outcome"]["jtbd_id"]),
            allowed_regions=(str(source.buyer_passport["company_profile"]["region"]),),
        ),
    )


def load_demo_decision_source(root: Path | None = None) -> DecisionSourceBundle:
    fixture_root = root or Path(__file__).resolve().parents[2] / "fixtures" / "demo"
    return DecisionSourceBundle.from_directory(fixture_root)


def load_demo_decision_graph_input(root: Path | None = None) -> DecisionGraphInput:
    """Load the checked-in demo through the same compiler used by persisted sources."""

    return compile_decision_graph_input(load_demo_decision_source(root))


__all__ = [
    "DecisionSourceBundle",
    "compile_decision_graph_input",
    "load_demo_decision_graph_input",
    "load_demo_decision_source",
]
