"""Deterministic evaluator for the governed Snowflake decision slice.

This module deliberately accepts already-frozen facts, offers, and reviewed
seller claim bindings. Retrieval and language models are never allowed to
create eligibility or ranking state.
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from typing import Any

from domain import content_hash


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("boolean values are not prices")
    return Decimal(str(value))


def _evaluate_once(source: dict[str, Any]) -> dict[str, Any]:
    facts = {str(item["fact_key"]): item["typed_value"] for item in source["facts"]}
    max_price = _decimal(facts["MAX_UNIT_PRICE"])
    required_seats = int(facts["REQUIRED_SEATS"])
    crm_required = bool(facts.get("CRM_SYNC_REQUIRED", False))
    current_crm = str(facts.get("CURRENT_CRM", ""))

    claims_by_product: dict[str, dict[str, dict[str, Any]]] = {}
    for claim in source["claims"]:
        claims_by_product.setdefault(str(claim["product_id"]), {})[str(claim["claim_key"])] = claim

    offers_by_product: dict[str, list[dict[str, Any]]] = {}
    for offer in source["offers"]:
        offers_by_product.setdefault(str(offer["product_id"]), []).append(offer)

    evaluated: list[dict[str, Any]] = []
    for product in sorted(source["products"], key=lambda item: str(item["product_id"])):
        product_id = str(product["product_id"])
        offers = sorted(
            offers_by_product.get(product_id, []),
            key=lambda item: (_decimal(item["unit_price"]), str(item["offer_id"])),
        )
        eligible_offers = [
            item
            for item in offers
            if int(item["min_seats"]) <= required_seats <= int(item["max_seats"])
        ]
        reasons: list[str] = []
        cited_claim_ids: list[str] = []
        selected_offer: dict[str, Any] | None = eligible_offers[0] if eligible_offers else None

        if selected_offer is None:
            reasons.append("SEAT_RANGE_UNSUPPORTED")
        if selected_offer is not None and crm_required and current_crm.casefold() == "hubspot":
            claims = claims_by_product.get(product_id, {})
            included = claims.get("HUBSPOT_INCLUDED_IN_BASE")
            minimum = claims.get("HUBSPOT_MIN_TIER_PRICE")
            if included and included["typed_value"] is True:
                cited_claim_ids.append(str(included["claim_id"]))
                reasons.append("HUBSPOT_INCLUDED_IN_BASE")
            elif minimum:
                minimum_price = _decimal(minimum["typed_value"])
                cited_claim_ids.append(str(minimum["claim_id"]))
                selected_offer = next(
                    (
                        item
                        for item in eligible_offers
                        if _decimal(item["unit_price"])
                        >= minimum_price
                    ),
                    None,
                )
                reasons.append("HUBSPOT_REQUIRES_HIGHER_TIER")
            else:
                selected_offer = None
                reasons.append("HUBSPOT_SUPPORT_UNVERIFIED")

        price = _decimal(selected_offer["unit_price"]) if selected_offer else None
        eligible = selected_offer is not None and price is not None and price <= max_price
        if price is not None and price > max_price:
            reasons.append("UNIT_PRICE_EXCEEDS_BUDGET")
        elif eligible:
            reasons.append("WITHIN_BUDGET")

        evaluated.append(
            {
                "product_id": product_id,
                "product_name": str(product["name"]),
                "eligible": eligible,
                "status": "ELIGIBLE" if eligible else "SIRA_INELIGIBLE",
                "selected_offer_id": str(selected_offer["offer_id"]) if selected_offer else None,
                "unit_price": str(price) if price is not None else None,
                "reason_codes": sorted(set(reasons)),
                "cited_claim_ids": sorted(cited_claim_ids),
            }
        )

    ranked = sorted(
        (item for item in evaluated if item["eligible"]),
        key=lambda item: (_decimal(item["unit_price"]), item["product_id"]),
    )
    winner = ranked[0] if ranked else None
    return {
        "selected_product_id": winner["product_id"] if winner else None,
        "selected_product_name": winner["product_name"] if winner else None,
        "status": "DECIDED" if winner else "NO_ELIGIBLE_OPTION",
        "reason_codes": winner["reason_codes"] if winner else ["NO_ELIGIBLE_OPTION"],
        "evaluated_products": evaluated,
    }


def evaluate_snowflake_decision(source: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one frozen source bundle and its private-context counterfactual."""

    required = {"company_id", "context_version", "facts", "products", "offers", "claims"}
    missing = sorted(required - source.keys())
    if missing:
        raise ValueError(f"Snowflake decision source is missing: {', '.join(missing)}")

    frozen = deepcopy(source)
    base = _evaluate_once(frozen)
    generic_source = deepcopy(frozen)
    generic_source["facts"] = [
        item
        for item in generic_source["facts"]
        if item["fact_key"] not in {"CRM_SYNC_REQUIRED", "CURRENT_CRM"}
    ]
    generic = _evaluate_once(generic_source)
    changed = base["selected_product_id"] != generic["selected_product_id"]
    input_hash = content_hash(frozen)
    counterfactual = {
        "outcome": "WINNER_CHANGED" if changed else "WINNER_UNCHANGED",
        "removed_fact_keys": ["CRM_SYNC_REQUIRED", "CURRENT_CRM"],
        "before_selected_product_id": base["selected_product_id"],
        "after_selected_product_id": generic["selected_product_id"],
    }
    decision_hash = content_hash(
        {
            "input_hash": input_hash,
            "selected_product_id": base["selected_product_id"],
            "counterfactual": counterfactual,
            "evaluator_version": "snowflake_decision_v1",
        }
    )
    return {
        **base,
        "evaluator_version": "snowflake_decision_v1",
        "input_hash": input_hash,
        "decision_hash": decision_hash,
        "counterfactual": counterfactual,
    }


__all__ = ["evaluate_snowflake_decision"]
