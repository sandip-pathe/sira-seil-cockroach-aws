"""Bind executable commercial terms to one immutable Solution Plan."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from decision_engine.graph_v1_models import DecisionGraphDecision, DecisionGraphInput
from domain import content_hash

from .fixtures import DemoFixtureBundle

_TERM_FIELDS = (
    "purchase_intent_group_id",
    "procurement_plan_id",
    "procurement_gate_result_hash",
    "pack_id",
    "pack_version",
    "offer_id",
    "offer_version",
    "quote_id",
    "quote_version",
    "quote_expires_at",
    "merchant",
    "approved_merchant_chain_id",
    "amount",
    "currency",
    "line_items",
    "expected_fulfillments",
    "fulfillment_completion_policy",
    "buyer_legal_entity_id",
    "seller_contracting_entity_id",
    "billing_identity_id",
    "cost_center_id",
    "purchase_order_ref",
    "merchant_subtotal",
    "tax_amount",
    "fee_amount",
    "fee_schedule_version",
    "contract_version_id",
    "landed_total",
    "approval_policy_version",
    "approval_requirement_set_id",
    "approval_plan_hash",
)


class CommercialTermsConflict(ValueError):
    """A quote or persisted plan is not bound to the expected commercial terms."""


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise CommercialTermsConflict(f"{label} must be an object")
    return deepcopy(dict(cast(Mapping[str, Any], value)))


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CommercialTermsConflict(f"{label} must be a non-empty string")
    return value


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise CommercialTermsConflict(f"{label} must be an exact decimal")
    try:
        return Decimal(str(value))
    except InvalidOperation:
        raise CommercialTermsConflict(f"{label} must be an exact decimal") from None


def _line_totals(lines: object, label: str) -> dict[str, Decimal]:
    if not isinstance(lines, list):
        raise CommercialTermsConflict(f"{label} must be an array")
    totals: dict[str, Decimal] = {}
    for index, raw in enumerate(lines):
        item = _object(raw, f"{label}[{index}]")
        line_type = _text(item.get("type"), f"{label}[{index}].type")
        amount = _decimal(item.get("total_amount"), f"{label}[{index}].total_amount")
        totals[line_type] = totals.get(line_type, Decimal(0)) + amount
    return totals


def _validate_quote_hash(quote: dict[str, Any]) -> str:
    supplied = _text(quote.get("content_hash"), "quote.content_hash")
    calculated = content_hash({key: value for key, value in quote.items() if key != "content_hash"})
    if supplied != calculated:
        raise CommercialTermsConflict("quote content hash does not match its payload")
    return supplied


def build_demo_plan_commercial_terms(
    fixtures: DemoFixtureBundle,
    graph_input: DecisionGraphInput,
    graph_decision: DecisionGraphDecision,
    *,
    stack_patch_id: str,
) -> dict[str, dict[str, Any]]:
    """Build the labelled demo quote snapshot and prove it matches the selected plan."""

    selected_plan_id = graph_decision.base.selected_plan_id
    if selected_plan_id is None:
        return {}
    plan = next(
        (item for item in graph_decision.base.plans if item.plan_id == selected_plan_id), None
    )
    if plan is None:
        raise CommercialTermsConflict("selected Solution Plan is absent from the evaluation")
    if plan.lifecycle.value != "EXECUTABLE" or not plan.dimensions.total_cost.payment_required:
        return {}
    if len(plan.components) != 1 or plan.components[0].source_type != "PACK":
        raise CommercialTermsConflict("demo checkout requires one executable Pack component")

    candidate = next(
        (
            item
            for item in graph_input.candidates
            if item.product_id == plan.components[0].component_id
            and item.offer_id == plan.dimensions.total_cost.offer_id
        ),
        None,
    )
    if candidate is None:
        raise CommercialTermsConflict("selected Solution Plan has no exact frozen Pack and offer")

    quote = deepcopy(fixtures.live_quote)
    quote_hash = _validate_quote_hash(quote)
    template = deepcopy(fixtures.expected_purchase_intent)
    for field in _TERM_FIELDS:
        if field not in template:
            raise CommercialTermsConflict(f"purchase terms are missing {field}")

    exact_bindings = (
        (quote.get("candidate_id"), candidate.pack_id, "quote Pack"),
        (quote.get("offer_id"), candidate.offer_id, "quote offer"),
        (quote.get("offer_version"), template["offer_version"], "offer version"),
        (quote.get("quote_id"), template["quote_id"], "quote ID"),
        (quote.get("version"), template["quote_version"], "quote version"),
        (quote.get("expires_at"), template["quote_expires_at"], "quote expiry"),
        (quote.get("merchant"), template["merchant"], "merchant"),
        (
            quote.get("merchant_chain_id"),
            template["approved_merchant_chain_id"],
            "merchant chain",
        ),
        (quote.get("line_items"), template["line_items"], "line items"),
        (quote.get("landed_total"), template["landed_total"], "landed total"),
        (quote.get("amount"), template["amount"], "authorized amount"),
        (quote.get("currency"), template["currency"], "currency"),
        (quote.get("tax_amount"), template["tax_amount"], "tax"),
        (quote.get("fee_amount"), template["fee_amount"], "fee"),
        (template["pack_id"], candidate.pack_id, "Pack ID"),
        (template["pack_version"], candidate.pack_version, "Pack version"),
        (template["offer_id"], candidate.offer_id, "intent offer"),
    )
    for actual, expected, label in exact_bindings:
        if actual != expected:
            raise CommercialTermsConflict(f"{label} is not bound to the selected Solution Plan")

    quote_expiry = datetime.fromisoformat(
        _text(quote["expires_at"], "quote.expires_at").replace("Z", "+00:00")
    )
    if quote_expiry.tzinfo is None:
        raise CommercialTermsConflict("quote expiry must include a timezone")

    cost = plan.dimensions.total_cost
    if cost.base is None:
        raise CommercialTermsConflict("selected Solution Plan has no exact base cost")
    if (
        cost.offer_id != candidate.offer_id
        or cost.base.amount != _decimal(quote["landed_total"], "quote.landed_total")
        or cost.base.currency != quote["currency"]
    ):
        raise CommercialTermsConflict("quote total is not the selected Solution Plan base cost")

    plan_lines = {
        item.line_item_type: item.base.amount for item in plan.dimensions.total_cost.line_items
    }
    if plan_lines != _line_totals(quote["line_items"], "quote.line_items"):
        raise CommercialTermsConflict("quote line items do not match the selected Solution Plan")

    terms = {
        "schema_version": "plan_commercial_terms_v1",
        "solution_plan_id": selected_plan_id,
        "stack_patch_id": stack_patch_id,
        "source_quote_hash": quote_hash,
        **{field: deepcopy(template[field]) for field in _TERM_FIELDS},
    }
    terms["commercial_terms_hash"] = content_hash(terms)
    return {selected_plan_id: terms}


def validate_plan_commercial_terms(
    value: object,
    *,
    solution_plan_id: str,
    stack_patch_id: str,
) -> dict[str, Any]:
    terms = _object(value, "commercial terms")
    supplied_hash = _text(terms.get("commercial_terms_hash"), "commercial_terms_hash")
    calculated_hash = content_hash(
        {key: item for key, item in terms.items() if key != "commercial_terms_hash"}
    )
    if supplied_hash != calculated_hash:
        raise CommercialTermsConflict("commercial terms hash does not match its payload")
    if terms.get("schema_version") != "plan_commercial_terms_v1":
        raise CommercialTermsConflict("commercial terms schema is unsupported")
    if terms.get("solution_plan_id") != solution_plan_id:
        raise CommercialTermsConflict("commercial terms are bound to another Solution Plan")
    if terms.get("stack_patch_id") != stack_patch_id:
        raise CommercialTermsConflict("commercial terms are bound to another Stackfile patch")
    for field in _TERM_FIELDS:
        if field not in terms:
            raise CommercialTermsConflict(f"commercial terms are missing {field}")
    return terms


def build_purchase_intent_payload(
    *,
    organization_id: str,
    decision_id: str,
    decision_version: int,
    decision_hash: str,
    selection_id: str,
    solution_plan_id: str,
    stack_patch_id: str,
    purchase_intent_id: str,
    commercial_terms: Mapping[str, Any],
    locked_at: datetime,
) -> dict[str, Any]:
    terms = validate_plan_commercial_terms(
        commercial_terms,
        solution_plan_id=solution_plan_id,
        stack_patch_id=stack_patch_id,
    )
    if locked_at.tzinfo is None:
        raise CommercialTermsConflict("purchase lock time must include a timezone")
    payload = {
        "schema_version": "1.0.0",
        "purchase_intent_id": purchase_intent_id,
        "organization_id": organization_id,
        "decision_id": decision_id,
        "decision_version": decision_version,
        "decision_hash": decision_hash,
        "selection_id": selection_id,
        "solution_plan_id": solution_plan_id,
        "stack_patch_id": stack_patch_id,
        **{field: deepcopy(terms[field]) for field in _TERM_FIELDS},
        "locked_at": locked_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
    }
    payload["intent_hash"] = content_hash(payload)
    return payload
