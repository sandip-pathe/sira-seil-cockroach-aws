from __future__ import annotations

from sira_worker.qualification import QualificationAgentDecision
from sira_worker.qualification_eval import (
    QualificationEvalCase,
    run_qualification_eval,
)


def test_qualification_eval_scores_acceptance_and_rejection_labels() -> None:
    valid = QualificationAgentDecision(
        recommended_product_id="product-a",
        summary="Grounded recommendation.",
        cited_dependency_ids=["evidence-a"],
        confidence="0.9",
    )
    cases = (
        QualificationEvalCase(
            id="accept-grounded",
            expected="ACCEPT",
            allowed_products=frozenset({"product-a"}),
            dependency_products={"evidence-a": "product-a"},
            decision=valid,
        ),
        QualificationEvalCase(
            id="reject-invented-product",
            expected="REJECT",
            allowed_products=frozenset({"product-b"}),
            dependency_products={"evidence-a": "product-a"},
            decision=valid,
        ),
    )
    results = run_qualification_eval(cases)
    assert all(result.passed for result in results)
    assert [result.actual for result in results] == ["ACCEPT", "REJECT"]
