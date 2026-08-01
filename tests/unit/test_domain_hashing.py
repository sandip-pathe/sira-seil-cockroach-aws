from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from domain import DomainValidationError, Money, canonical_json, content_hash
from domain.enums import ApprovalStatus
from domain.models import (
    ApprovalBinding,
    BuyerFact,
    ExpectedFulfillment,
    MerchantIdentity,
    PurchaseIntent,
    SourceRef,
    Verification,
)
from domain.state_machines import ApprovalTransitionService


def test_canonical_hash_ignores_mapping_insertion_order() -> None:
    left = {"schema_version": "1.0.0", "nested": {"b": 2, "a": Decimal("89.00")}}
    right = {"nested": {"a": Decimal("89"), "b": 2}, "schema_version": "1.0.0"}

    assert canonical_json(left) == canonical_json(right)
    assert content_hash(left) == content_hash(right)
    assert content_hash(left).startswith("sha256:")


def test_canonical_hash_rejects_binary_float_and_naive_time() -> None:
    with pytest.raises(DomainValidationError, match="binary floating point"):
        canonical_json({"amount": 0.1})
    with pytest.raises(DomainValidationError, match="naive"):
        canonical_json({"created_at": datetime(2026, 8, 2)})


def test_money_is_exact_and_cross_currency_addition_is_rejected() -> None:
    assert Money("89.00", "usd") == Money(89, "USD")
    assert Money("89.00", "USD").to_dict() == {"amount": "89.00", "currency": "USD"}
    with pytest.raises(DomainValidationError, match="different currencies"):
        _ = Money(1, "USD") + Money(1, "EUR")
    with pytest.raises(DomainValidationError, match="binary"):
        Money(0.1, "USD")  # type: ignore[arg-type]
    with pytest.raises(DomainValidationError, match="two decimal"):
        Money("1.001", "USD")
    assert Money.from_dict({"amount": "1.00", "currency": "USD"}) == Money(1, "USD")
    with pytest.raises(DomainValidationError, match="exactly"):
        Money.from_dict({"amount": "1.00"})


def test_hard_buyer_fact_requires_owner_approved_verification() -> None:
    source = SourceRef(
        provider="senso",
        content_id="content_demo",
        version_id="version_demo",
        fragment_hash=content_hash({"fragment": "policy"}),
        retrieved_at=datetime(2026, 8, 2, tzinfo=UTC),
    )
    unverified = Verification("unverified", "source_document_review", None, None)
    with pytest.raises(DomainValidationError, match="hard constraints"):
        BuyerFact(
            fact_id="fact_demo",
            organization_id="org_demo",
            subject_type="policy",
            subject_id="policy_demo",
            field="trains_on_customer_data",
            operator="eq",
            value=False,
            kind="hard_constraint",
            stakeholder_role="security",
            source=source,
            verification=unverified,
            valid_from=datetime(2026, 8, 1, tzinfo=UTC),
            valid_until=None,
            sensitivity="confidential",
            confidence="inferred",
        )

    approved = Verification(
        "human_approved",
        "policy_owner_confirmation",
        "user_security",
        datetime(2026, 8, 2, tzinfo=UTC),
    )
    fact = BuyerFact(
        fact_id="fact_demo",
        organization_id="org_demo",
        subject_type="policy",
        subject_id="policy_demo",
        field="trains_on_customer_data",
        operator="eq",
        value=False,
        kind="hard_constraint",
        stakeholder_role="security",
        source=source,
        verification=approved,
        valid_from=datetime(2026, 8, 1, tzinfo=UTC),
        valid_until=datetime(2026, 9, 1, tzinfo=UTC),
        sensitivity="confidential",
        confidence="confirmed",
    )
    assert fact.is_current(datetime(2026, 8, 15, tzinfo=UTC))
    assert not fact.is_current(datetime(2026, 9, 2, tzinfo=UTC))


def _purchase_intent() -> PurchaseIntent:
    return PurchaseIntent(
        schema_version="1.0.0",
        purchase_intent_id="pi_demo",
        organization_id="org_demo",
        decision_id="dec_demo",
        decision_hash=content_hash({"decision": "demo"}),
        solution_plan_id="sol_demo",
        procurement_plan_id="pp_demo",
        procurement_gate_result_hash=content_hash({"gates": "complete"}),
        pack_id="pack_demo",
        pack_version=1,
        offer_id="offer_demo",
        offer_version=1,
        quote_id="quote_demo",
        quote_expires_at=datetime(2026, 8, 2, 12, tzinfo=UTC),
        merchant=MerchantIdentity(
            merchant_id="merchant_demo",
            name="Demo merchant",
            url="https://merchant.example.test",
            country="US",
        ),
        approved_merchant_chain_id="chain_demo",
        amount=Money("89.00", "USD"),
        line_items=({"line_item_id": "line_demo", "amount": "89.00"},),
        expected_fulfillments=(
            ExpectedFulfillment(
                fulfillment_item_id="fulfillment_workspace",
                line_item_id="line_demo",
                type="workspace_entitlement",
                subject_type="organization",
                required=True,
                minimum_quantity=1,
                expected_quantity=1,
                verification_method="merchant_api_plus_access_probe",
            ),
        ),
        approval_policy_version=1,
        approval_plan_hash=content_hash({"approval": "plan"}),
        buyer_legal_entity_id="buyer_entity",
        seller_contracting_entity_id="seller_entity",
        billing_identity_id="billing_demo",
        cost_center_id="cost_center_demo",
        contract_version_id="contract_demo",
    )


def test_purchase_intent_hash_binds_every_material_field() -> None:
    intent = _purchase_intent()
    assert intent.intent_hash == content_hash(intent.to_hash_payload())

    with pytest.raises(DomainValidationError, match="intent_hash does not match"):
        replace(intent, amount=Money("90", "USD"))

    changed = replace(intent, amount=Money("90", "USD"), intent_hash="")
    approval = ApprovalBinding("approval_demo", intent.intent_hash, ApprovalStatus.APPROVED)
    reconciled = ApprovalTransitionService.reconcile_payload(approval, changed.intent_hash)
    assert reconciled.status is ApprovalStatus.SUPERSEDED
