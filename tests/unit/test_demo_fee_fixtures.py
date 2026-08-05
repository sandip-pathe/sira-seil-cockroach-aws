from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from domain import content_hash

DEMO = Path(__file__).resolve().parents[2] / "fixtures" / "demo"


def _load(name: str) -> dict[str, Any]:
    value = json.loads((DEMO / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _assert_fee_split(document: dict[str, Any], *, total_field: str) -> None:
    line_items = document["line_items"]
    merchant = [item for item in line_items if item["type"] == "MERCHANT_SUBTOTAL"]
    fees = [item for item in line_items if item["type"] == "SIRA_TRANSACTION_FEE"]

    assert len(merchant) == 1
    assert len(fees) == 1
    assert merchant[0]["total_amount"] == "980.00"
    assert merchant[0]["schedule_version"] is None
    assert merchant[0]["demo_policy_label"] is None
    assert fees[0]["total_amount"] == "10.00"
    assert fees[0]["schedule_version"] == "buyer_txn_demo_v1"
    assert fees[0]["demo_policy_label"] == "DEMO_ONLY"
    assert sum(Decimal(item["total_amount"]) for item in line_items) == Decimal(
        document[total_field]
    )


def test_charge_bearing_demo_fixtures_bind_one_disclosed_buyer_fee() -> None:
    quote = _load("live_quote.json")
    intent = _load("expected_purchase_intent.json")
    receipt = _load("expected_receipt.json")
    offers = _load("offers.json")

    _assert_fee_split(quote, total_field="landed_total")
    _assert_fee_split(intent, total_field="landed_total")
    _assert_fee_split(receipt, total_field="amount")

    assert quote["fee_amount"] == intent["fee_amount"] == "10.00"
    assert intent["merchant_subtotal"] == receipt["merchant_subtotal"] == "980.00"
    assert receipt["buyer_transaction_fee"] == "10.00"
    assert intent["fee_schedule_version"] == receipt["fee_schedule_version"]
    assert intent["fee_schedule_version"] == "buyer_txn_demo_v1"
    assert intent["amount"] == quote["amount"] == receipt["amount"] == "990.00"

    selected_offer = next(
        item for item in offers["offers"] if item["offer_id"] == "offer_fixture_d_monthly"
    )
    assert selected_offer["amount"] == "990.00"


def test_fee_fixture_hashes_and_links_are_exact_and_non_production() -> None:
    quote = _load("live_quote.json")
    intent = _load("expected_purchase_intent.json")
    receipt = _load("expected_receipt.json")

    assert quote["content_hash"] == content_hash(
        {key: value for key, value in quote.items() if key != "content_hash"}
    )
    assert intent["intent_hash"] == content_hash(
        {key: value for key, value in intent.items() if key != "intent_hash"}
    )
    assert receipt["approval_intent_hash"] == intent["intent_hash"]
    assert receipt["quote_id"] == intent["quote_id"] == quote["quote_id"]
    assert receipt["selection_id"] == intent["selection_id"]
    assert receipt["solution_plan_id"] == intent["solution_plan_id"]
    assert receipt["stack_patch_id"] == intent["stack_patch_id"]
    assert receipt["adapter_label"] == "DEVELOPMENT_FIXTURE_NOT_PRODUCTION"
    assert receipt["production_success"] is False

    serialized = json.dumps((quote, intent, receipt), sort_keys=True).casefold()
    assert "seller_commission" not in serialized
    assert "referral_commission" not in serialized
    assert "ranking_weight" not in serialized
