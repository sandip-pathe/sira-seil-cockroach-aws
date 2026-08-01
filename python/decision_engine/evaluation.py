"""Buyer-policy and seller anti-fit evaluation with separate provenance."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from domain.enums import CandidateStatus, TruthValue

from .models import CandidateDefinition, CandidateResult


def _result(
    candidate: CandidateDefinition,
    status: CandidateStatus,
    reason_code: str | None,
    reason: str,
    **extra: Any,
) -> CandidateResult:
    return CandidateResult(
        candidate_id=candidate.candidate_id,
        name=candidate.name,
        pack_id=candidate.pack_id,
        pack_version=candidate.pack_version,
        status=status,
        reason_code=reason_code,
        reason=reason,
        preference_results=candidate.preference_results,
        seller_positioning=candidate.seller_positioning,
        **extra,
    )


def evaluate_candidate(
    candidate: CandidateDefinition,
    *,
    buyer_evaluation_context: Mapping[str, Any],
    sanitized_seller_context: Mapping[str, Any],
) -> CandidateResult:
    """Evaluate the request-specific gate order without a model or provider.

    The anti-fit engine receives only the caller-supplied sanitized context. It
    cannot accidentally reach the richer buyer evaluation mapping.
    """

    if not candidate.available:
        return _result(candidate, CandidateStatus.UNAVAILABLE, "UNAVAILABLE", "Not available")
    if candidate.evidence_block is not None:
        return _result(
            candidate,
            candidate.evidence_block,
            candidate.evidence_block.value,
            "Required evidence is not currently actionable",
        )

    exception_used = False
    for constraint in candidate.buyer_constraints:
        evaluation = constraint.expression.evaluate(buyer_evaluation_context)
        if evaluation.value is TruthValue.UNRESOLVED:
            return _result(
                candidate,
                CandidateStatus.INSUFFICIENT_EVIDENCE,
                "BUYER_RULE_UNRESOLVED",
                "A required buyer-policy fact is unresolved",
                buyer_rule_id=constraint.rule_id,
                unresolved_fields=evaluation.unresolved_fields,
            )
        if evaluation.value is TruthValue.FALSE:
            has_exception = (
                constraint.exception_allowed
                and constraint.rule_id in candidate.approved_exception_rule_ids
            )
            if not has_exception:
                return _result(
                    candidate,
                    CandidateStatus.SIRA_INELIGIBLE,
                    constraint.reason_code,
                    constraint.display_reason,
                    buyer_rule_id=constraint.rule_id,
                )
            exception_used = True

    for anti_fit in candidate.seller_anti_fit_rules:
        evaluation = anti_fit.expression.evaluate(sanitized_seller_context)
        if evaluation.value is TruthValue.TRUE:
            return _result(
                candidate,
                CandidateStatus.SEIL_PASS,
                anti_fit.reason_code,
                anti_fit.display_reason,
                seller_rule_id=anti_fit.rule_id,
                evidence_claim_ids=anti_fit.evidence_claim_ids,
            )
        if evaluation.value is TruthValue.UNRESOLVED:
            return _result(
                candidate,
                CandidateStatus.CONDITIONAL,
                "SELLER_CONDITION_UNRESOLVED",
                "A published seller condition needs an allowed field or seller revision",
                seller_rule_id=anti_fit.rule_id,
                evidence_claim_ids=anti_fit.evidence_claim_ids,
                unresolved_fields=evaluation.unresolved_fields,
            )

    if candidate.dependency_state is TruthValue.FALSE:
        return _result(
            candidate,
            CandidateStatus.SIRA_INELIGIBLE,
            "DEPENDENCY_UNSATISFIED",
            "A required dependency cannot be satisfied",
            buyer_rule_id="dependency_plan",
        )
    if candidate.dependency_state is TruthValue.UNRESOLVED:
        return _result(
            candidate,
            CandidateStatus.CONDITIONAL,
            "DEPENDENCY_PLAN_REQUIRED",
            "A required dependency plan is unresolved",
            unresolved_fields=("dependency_plan",),
        )

    status = CandidateStatus.ELIGIBLE_WITH_EXCEPTION if exception_used else CandidateStatus.ELIGIBLE
    return _result(
        candidate,
        status,
        "APPROVED_EXCEPTION" if exception_used else None,
        (
            "Eligible with an approved buyer-policy exception"
            if exception_used
            else "Meets evaluated buyer and published seller gates"
        ),
    )


def evaluate_candidate_set(
    candidates: Sequence[CandidateDefinition],
    *,
    buyer_contexts: Mapping[str, Mapping[str, Any]],
    seller_contexts: Mapping[str, Mapping[str, Any]],
) -> tuple[CandidateResult, ...]:
    """Evaluate a candidate set in stable candidate-ID order."""

    return tuple(
        evaluate_candidate(
            candidate,
            buyer_evaluation_context=buyer_contexts.get(candidate.candidate_id, {}),
            sanitized_seller_context=seller_contexts.get(candidate.candidate_id, {}),
        )
        for candidate in sorted(candidates, key=lambda item: item.candidate_id)
    )
