"""Snowpark stored-procedure entrypoint for the SIRA decision ledger."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from decimal import Decimal
from typing import Any
from uuid import uuid4


def _hash_normalize(value: object) -> object:
    if isinstance(value, Decimal):
        rendered = format(value.normalize(), "f")
        return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered
    if isinstance(value, dict):
        return {str(key): _hash_normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_hash_normalize(item) for item in value]
    return value


def _content_hash(value: object) -> str:
    payload = json.dumps(
        _hash_normalize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


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
                        if _decimal(item["unit_price"]) >= minimum_price
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
    frozen = deepcopy(source)
    base = _evaluate_once(frozen)
    generic_source = deepcopy(frozen)
    generic_source["facts"] = [
        item
        for item in generic_source["facts"]
        if item["fact_key"] not in {"CRM_SYNC_REQUIRED", "CURRENT_CRM"}
    ]
    generic = _evaluate_once(generic_source)
    counterfactual = {
        "outcome": (
            "WINNER_CHANGED"
            if base["selected_product_id"] != generic["selected_product_id"]
            else "WINNER_UNCHANGED"
        ),
        "removed_fact_keys": ["CRM_SYNC_REQUIRED", "CURRENT_CRM"],
        "before_selected_product_id": base["selected_product_id"],
        "after_selected_product_id": generic["selected_product_id"],
    }
    input_hash = _content_hash(frozen)
    decision_hash = _content_hash(
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


def _rows(session: Any, sql: str, params: list[Any]) -> list[dict[str, Any]]:
    return [row.as_dict(recursive=True) for row in session.sql(sql, params=params).collect()]


def _json_value(value: object) -> object:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def run_sira_decision(session: Any, request_id: str) -> dict[str, Any]:
    """Idempotently evaluate a request and persist its frozen audit trail."""

    prior = _rows(
        session,
        "SELECT output FROM SIRA_HACKATHON.DECISION.RUNS WHERE request_id = ? "
        "ORDER BY created_at DESC LIMIT 1",
        [request_id],
    )
    if prior:
        return _json_value(prior[0]["OUTPUT"])  # type: ignore[return-value]

    requests = _rows(
        session,
        "SELECT request_id, company_id, mission_id, context_version, created_by "
        "FROM SIRA_HACKATHON.DECISION.REQUESTS WHERE request_id = ?",
        [request_id],
    )
    if not requests:
        raise ValueError("decision request does not exist")
    request = requests[0]
    company_id = str(request["COMPANY_ID"])
    context_version = int(request["CONTEXT_VERSION"])

    facts = _rows(
        session,
        "SELECT fact_id, fact_key, typed_value, visibility, source_kind, source_ref "
        "FROM SIRA_HACKATHON.GOVERNED.COMPANY_FACTS "
        "WHERE company_id = ? AND context_version = ? ORDER BY fact_id",
        [company_id, context_version],
    )
    products = _rows(
        session,
        "SELECT product_id, seller_id, name, category, product_version "
        "FROM SIRA_HACKATHON.GOVERNED.PRODUCTS WHERE status = 'ACTIVE' ORDER BY product_id",
        [],
    )
    offers = _rows(
        session,
        "SELECT offer_id, product_id, tier, unit_price, billing_unit, currency, "
        "min_seats, max_seats "
        "FROM SIRA_HACKATHON.GOVERNED.OFFERS ORDER BY product_id, unit_price",
        [],
    )
    claims = _rows(
        session,
        "SELECT b.claim_id, b.product_id, b.claim_key, b.operator, b.typed_value, "
        "b.chunk_id, c.document_id, c.page_number, c.chunk_text, c.chunk_hash "
        "FROM SIRA_HACKATHON.EVIDENCE.SELLER_CLAIM_BINDINGS b "
        "JOIN SIRA_HACKATHON.EVIDENCE.DOCUMENT_CHUNKS c ON c.chunk_id = b.chunk_id "
        "WHERE b.binding_status = 'REVIEWED' ORDER BY b.claim_id",
        [],
    )

    def normalize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{key.casefold(): _json_value(value) for key, value in row.items()} for row in rows]

    source: dict[str, Any] = {
        "company_id": company_id,
        "context_version": context_version,
        "facts": normalize(facts),
        "products": normalize(products),
        "offers": normalize(offers),
        "claims": normalize(claims),
    }
    result = evaluate_snowflake_decision(source)
    snapshot_id = f"snap_{uuid4().hex}"
    run_id = f"run_{uuid4().hex}"
    fact_ids = [item["fact_id"] for item in source["facts"]]
    claim_ids = [item["claim_id"] for item in source["claims"]]
    chunk_ids = sorted({item["chunk_id"] for item in source["claims"]})

    session.sql(
        "INSERT INTO SIRA_HACKATHON.DECISION.INPUT_SNAPSHOTS "
        "(snapshot_id, request_id, source_bundle, fact_ids, claim_ids, chunk_ids, input_hash) "
        "SELECT ?, ?, PARSE_JSON(?), PARSE_JSON(?), PARSE_JSON(?), PARSE_JSON(?), ?",
        params=[
            snapshot_id,
            request_id,
            json.dumps(source, default=str, separators=(",", ":")),
            json.dumps(fact_ids),
            json.dumps(claim_ids),
            json.dumps(chunk_ids),
            result["input_hash"],
        ],
    ).collect()
    session.sql(
        "INSERT INTO SIRA_HACKATHON.DECISION.RUNS "
        "(run_id, request_id, snapshot_id, evaluator_version, input_hash, decision_hash, "
        "selected_product_id, status, reason_codes, counterfactual, output, query_id) "
        "SELECT ?, ?, ?, ?, ?, ?, ?, ?, PARSE_JSON(?), PARSE_JSON(?), "
        "PARSE_JSON(?), LAST_QUERY_ID()",
        params=[
            run_id,
            request_id,
            snapshot_id,
            result["evaluator_version"],
            result["input_hash"],
            result["decision_hash"],
            result["selected_product_id"],
            result["status"],
            json.dumps(result["reason_codes"]),
            json.dumps(result["counterfactual"]),
            json.dumps({**result, "run_id": run_id, "request_id": request_id}),
        ],
    ).collect()

    decisive_fact_ids = {
        item["fact_id"]
        for item in source["facts"]
        if item["fact_key"] in {"CRM_SYNC_REQUIRED", "CURRENT_CRM", "MAX_UNIT_PRICE"}
    }
    for fact in source["facts"]:
        if fact["fact_id"] not in decisive_fact_ids:
            continue
        session.sql(
            "INSERT INTO SIRA_HACKATHON.DECISION.CITATIONS "
            "(citation_id, run_id, citation_type, fact_id, exact_excerpt, source_hash) "
            "SELECT ?, ?, 'BUYER_FACT', ?, ?, ?",
            params=[
                f"cit_{uuid4().hex}",
                run_id,
                fact["fact_id"],
                f"{fact['fact_key']}={fact['typed_value']}",
                result["input_hash"],
            ],
        ).collect()
    cited_claims = {
        claim_id for item in result["evaluated_products"] for claim_id in item["cited_claim_ids"]
    }
    for claim in source["claims"]:
        if claim["claim_id"] not in cited_claims:
            continue
        session.sql(
            "INSERT INTO SIRA_HACKATHON.DECISION.CITATIONS "
            "(citation_id, run_id, citation_type, document_id, chunk_id, page_number, "
            "exact_excerpt, source_hash) "
            "SELECT ?, ?, 'SELLER_DOCUMENT', ?, ?, ?, ?, ?",
            params=[
                f"cit_{uuid4().hex}",
                run_id,
                claim["document_id"],
                claim["chunk_id"],
                claim["page_number"],
                claim["chunk_text"],
                f"sha256:{claim['chunk_hash']}",
            ],
        ).collect()

    return {**result, "run_id": run_id, "request_id": request_id}


__all__ = ["run_sira_decision"]
