from dataclasses import replace
from decimal import Decimal

import pytest

from decision_engine import (
    BuyerConstraint,
    CandidateDefinition,
    SellerAntiFitRule,
    evaluate_candidate,
    evaluate_candidate_set,
)
from domain.enums import CandidateStatus, RuleOperator, TruthValue
from domain.rules import RuleCondition, RuleExpression


def test_missing_field_is_unresolved_not_false() -> None:
    rule = RuleExpression(
        (RuleCondition("product.trains_on_customer_data", RuleOperator.EQ, False),)
    )
    result = rule.evaluate({"product": {}})

    assert result.value is TruthValue.UNRESOLVED
    assert result.unresolved_fields == ("product.trains_on_customer_data",)


def test_boolean_policy_values_do_not_coerce_to_numbers() -> None:
    assert (
        RuleCondition("policy.allowed", RuleOperator.EQ, False)
        .evaluate({"policy": {"allowed": 0}})
        .value
        is TruthValue.FALSE
    )


@pytest.mark.parametrize(
    ("condition", "context", "expected"),
    [
        (RuleCondition("x", RuleOperator.EQ, "a"), {"x": "a"}, TruthValue.TRUE),
        (RuleCondition("x", RuleOperator.NEQ, "a"), {"x": "a"}, TruthValue.FALSE),
        (RuleCondition("x", RuleOperator.IN, ["US", "CA"]), {"x": "US"}, TruthValue.TRUE),
        (
            RuleCondition("x", RuleOperator.CONTAINS_ALL, ["a", "b"]),
            {"x": ["b", "a", "c"]},
            TruthValue.TRUE,
        ),
        (RuleCondition("x", RuleOperator.LTE, "100"), {"x": Decimal("89")}, TruthValue.TRUE),
        (
            RuleCondition("x", RuleOperator.DATE_BEFORE, "2026-08-03"),
            {"x": "2026-08-02"},
            TruthValue.TRUE,
        ),
        (RuleCondition("x", RuleOperator.EXISTS, False), {}, TruthValue.TRUE),
    ],
)
def test_rule_operators_are_deterministic(
    condition: RuleCondition, context: dict[str, object], expected: TruthValue
) -> None:
    assert condition.evaluate(context).value is expected


def test_three_valued_all_and_any_logic() -> None:
    unknown = RuleCondition("missing", RuleOperator.EQ, True)
    true = RuleCondition("present", RuleOperator.EQ, True)
    false = RuleCondition("present", RuleOperator.EQ, False)

    assert (
        RuleExpression((unknown, true), "all").evaluate({"present": True}).value
        is TruthValue.UNRESOLVED
    )
    assert (
        RuleExpression((unknown, false), "all").evaluate({"present": True}).value
        is TruthValue.FALSE
    )
    assert (
        RuleExpression((unknown, true), "any").evaluate({"present": True}).value is TruthValue.TRUE
    )
    assert (
        RuleExpression((unknown, false), "any").evaluate({"present": True}).value
        is TruthValue.UNRESOLVED
    )


def _candidate() -> CandidateDefinition:
    buyer_rule = BuyerConstraint(
        rule_id="buyer_no_training",
        expression=RuleExpression(
            (RuleCondition("product.trains_on_customer_data", RuleOperator.EQ, False),)
        ),
        reason_code="CUSTOMER_TRAINING_PROHIBITED",
        display_reason="Customer content cannot be used for model training",
    )
    seller_rule = SellerAntiFitRule(
        rule_id="seller_shared_workspace",
        expression=RuleExpression(
            (
                RuleCondition("buyer.shared_client_workspace_required", RuleOperator.EQ, True),
                RuleCondition("buyer.client_conversations_restricted", RuleOperator.EQ, True),
            )
        ),
        reason_code="SHARED_CLIENT_WORKSPACE_UNSUPPORTED",
        display_reason="Restricted shared client workspaces are unsupported",
        evidence_claim_ids=("claim_workspace",),
    )
    return CandidateDefinition(
        candidate_id="candidate_demo",
        name="Fixture",
        pack_id="pack_demo",
        pack_version=1,
        buyer_constraints=(buyer_rule,),
        seller_anti_fit_rules=(seller_rule,),
    )


def test_buyer_policy_failure_is_sira_ineligible() -> None:
    result = evaluate_candidate(
        _candidate(),
        buyer_evaluation_context={"product": {"trains_on_customer_data": True}},
        sanitized_seller_context={"buyer": {}},
    )
    assert result.status is CandidateStatus.SIRA_INELIGIBLE
    assert result.buyer_rule_id == "buyer_no_training"
    assert result.seller_rule_id is None


def test_published_seller_anti_fit_is_seil_pass() -> None:
    result = evaluate_candidate(
        _candidate(),
        buyer_evaluation_context={"product": {"trains_on_customer_data": False}},
        sanitized_seller_context={
            "buyer": {
                "shared_client_workspace_required": True,
                "client_conversations_restricted": True,
            }
        },
    )
    assert result.status is CandidateStatus.SEIL_PASS
    assert result.seller_rule_id == "seller_shared_workspace"
    assert result.buyer_rule_id is None


def test_seller_rule_cannot_reach_unsanitized_buyer_context() -> None:
    result = evaluate_candidate(
        _candidate(),
        buyer_evaluation_context={
            "product": {"trains_on_customer_data": False},
            "buyer": {
                "shared_client_workspace_required": True,
                "client_conversations_restricted": True,
            },
        },
        sanitized_seller_context={"buyer": {}},
    )
    assert result.status is CandidateStatus.CONDITIONAL
    assert set(result.unresolved_fields) == {
        "buyer.client_conversations_restricted",
        "buyer.shared_client_workspace_required",
    }


def test_candidate_gate_short_circuits_are_explicit() -> None:
    candidate = _candidate()
    unavailable = evaluate_candidate(
        replace(candidate, available=False),
        buyer_evaluation_context={},
        sanitized_seller_context={},
    )
    assert unavailable.status is CandidateStatus.UNAVAILABLE

    stale = evaluate_candidate(
        replace(candidate, evidence_block=CandidateStatus.STALE_EVIDENCE),
        buyer_evaluation_context={},
        sanitized_seller_context={},
    )
    assert stale.status is CandidateStatus.STALE_EVIDENCE

    unresolved = evaluate_candidate(
        candidate,
        buyer_evaluation_context={"product": {}},
        sanitized_seller_context={},
    )
    assert unresolved.status is CandidateStatus.INSUFFICIENT_EVIDENCE


def test_only_explicitly_allowed_and_approved_buyer_exception_changes_status() -> None:
    candidate = _candidate()
    exceptionable = replace(
        candidate.buyer_constraints[0],
        exception_allowed=True,
    )
    result = evaluate_candidate(
        replace(
            candidate,
            buyer_constraints=(exceptionable,),
            seller_anti_fit_rules=(),
            approved_exception_rule_ids=frozenset({exceptionable.rule_id}),
        ),
        buyer_evaluation_context={"product": {"trains_on_customer_data": True}},
        sanitized_seller_context={},
    )
    assert result.status is CandidateStatus.ELIGIBLE_WITH_EXCEPTION


def test_candidate_set_output_is_stably_ordered() -> None:
    first = replace(
        _candidate(), candidate_id="candidate_z", pack_id="pack_z", seller_anti_fit_rules=()
    )
    second = replace(
        _candidate(), candidate_id="candidate_a", pack_id="pack_a", seller_anti_fit_rules=()
    )
    results = evaluate_candidate_set(
        (first, second),
        buyer_contexts={
            "candidate_z": {"product": {"trains_on_customer_data": False}},
            "candidate_a": {"product": {"trains_on_customer_data": False}},
        },
        seller_contexts={},
    )
    assert tuple(result.candidate_id for result in results) == ("candidate_a", "candidate_z")
