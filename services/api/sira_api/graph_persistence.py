"""Translate the pure Decision Graph v1 result into canonical persistence rows.

The adapter is intentionally one-way. Pure graph types do not import SQLAlchemy,
and persistence payloads contain frozen hashes and derived results rather than
private Buyer Passport fact values.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, cast

from decision_engine.bounds import ExactRatio
from decision_engine.graph_v1 import evaluation_canonical_payload
from decision_engine.graph_v1_models import (
    DecisionGraphDecision,
    DecisionGraphEvaluation,
    DecisionGraphInput,
    EvaluatedPlan,
)
from domain import content_hash
from domain.hashing import canonical_json
from domain.models import require_id
from persistence.models import (
    CandidateSetMember,
    CounterfactualRecordModel,
    DecisionGateResult,
    DiscoveryRun,
    EvaluationPipelineVersion,
    EvaluationRun,
    EvaluationSolutionPlan,
    EvidenceAssessmentRecord,
    IdentityMerge,
    RobustnessFrontier,
    ScoreBound,
    ScoreComponentRecord,
    SolutionPlanComponent,
)
from persistence.repositories import (
    EvaluationGraphWrite,
    PersistenceConflict,
    RecordNotFound,
    WorkflowRepository,
)

_CURRENT_STACK_ACTIONS = frozenset({"REUSE_EXISTING", "CONFIGURE_EXISTING"})
_BOUND_DIMENSIONS = (
    "PREFERENCE",
    "STACK_RISK",
    "TCO",
    "DECISION_MATERIAL_COVERAGE",
    "EVIDENCE_AGE",
    "HARD_COVERAGE",
    "UNIVERSE_COVERAGE",
)


@dataclass(frozen=True, slots=True)
class EvaluationPersistenceMetadata:
    """Database bindings and frozen versions absent from the pure graph input."""

    organization_id: str
    purchase_request_id: str
    purchase_brief_id: str
    decision_id: str | None
    candidate_set_version: str
    quote_set_version: str
    risk_rule_set_version: str
    valuation_currency: str

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.organization_id, "organization_id"),
            (self.purchase_request_id, "purchase_request_id"),
            (self.purchase_brief_id, "purchase_brief_id"),
        ):
            require_id(value, field_name)
        if self.decision_id is not None:
            require_id(self.decision_id, "decision_id")
        for value, field_name in (
            (self.candidate_set_version, "candidate_set_version"),
            (self.quote_set_version, "quote_set_version"),
            (self.risk_rule_set_version, "risk_rule_set_version"),
        ):
            if not value or value.strip() != value:
                raise ValueError(f"{field_name} must be a non-empty frozen version")
        if (
            len(self.valuation_currency) != 3
            or self.valuation_currency != self.valuation_currency.upper()
        ):
            raise ValueError("valuation_currency must be an uppercase three-letter code")


def _json_document(value: object) -> dict[str, Any]:
    normalized = json.loads(canonical_json(value))
    if not isinstance(normalized, dict):
        raise ValueError("a persistence JSON document must be an object")
    return cast(dict[str, Any], normalized)


def _stable_id(prefix: str, *parts: object) -> str:
    digest = content_hash({"namespace": prefix, "parts": parts}).removeprefix("sha256:")
    return f"{prefix}_{digest[:40]}"


def _pipeline_payload(
    decision_input: DecisionGraphInput,
    metadata: EvaluationPersistenceMetadata,
) -> dict[str, Any]:
    versions = decision_input.versions
    return {
        "schema_version": "decision_graph_pipeline_v1",
        "pipeline_version": versions.pipeline_version,
        "engine_version": versions.engine_version,
        "taxonomy_version": versions.taxonomy_version,
        "normalization_version": versions.normalization_version,
        "policy_version": versions.policy_version,
        "risk_rule_set_version": metadata.risk_rule_set_version,
        "risk_rule_set_complete": decision_input.risk_rule_set_complete,
        "risk_rule_ids": sorted(rule.rule_id for rule in decision_input.risk_rules),
        "risk_rule_set_hash": content_hash(
            tuple(sorted(decision_input.risk_rules, key=lambda rule: rule.rule_id))
        ),
    }


def build_evaluation_pipeline_version(
    decision_input: DecisionGraphInput,
    metadata: EvaluationPersistenceMetadata,
) -> EvaluationPipelineVersion:
    """Build the same immutable pipeline row for every retry of the same input."""

    payload = _pipeline_payload(decision_input, metadata)
    payload_hash = content_hash(payload)
    versions = decision_input.versions
    return EvaluationPipelineVersion(
        id=_stable_id("epv", metadata.organization_id, payload_hash),
        organization_id=metadata.organization_id,
        pipeline_version=versions.pipeline_version,
        engine_version=versions.engine_version,
        taxonomy_version=versions.taxonomy_version,
        normalization_version=versions.normalization_version,
        policy_version=versions.policy_version,
        risk_rule_set_version=metadata.risk_rule_set_version,
        content_hash=payload_hash,
        payload=payload,
    )


async def ensure_evaluation_pipeline_version(
    repository: WorkflowRepository,
    decision_input: DecisionGraphInput,
    metadata: EvaluationPersistenceMetadata,
) -> EvaluationPipelineVersion:
    """Get or stage the deterministic pipeline row in the caller's transaction."""

    if repository.organization_id != metadata.organization_id:
        raise PersistenceConflict("Pipeline metadata does not match the repository tenant")
    expected = build_evaluation_pipeline_version(decision_input, metadata)
    try:
        existing = await repository.get_evaluation_pipeline_version(expected.id)
    except RecordNotFound:
        return await repository.add_evaluation_pipeline_version(expected)
    if existing.content_hash != expected.content_hash or existing.payload != expected.payload:
        raise PersistenceConflict("The deterministic pipeline ID is bound to different content")
    return existing


def _ledger_document(
    ledger: Mapping[str, Any],
    *,
    evaluation: DecisionGraphEvaluation,
    metadata: EvaluationPersistenceMetadata,
) -> dict[str, Any]:
    document = _json_document(ledger)
    supplied_hash = document.get("decision_hash")
    unhashed = {key: value for key, value in document.items() if key != "decision_hash"}
    if not isinstance(supplied_hash, str) or supplied_hash != content_hash(unhashed):
        raise ValueError("Decision Ledger decision_hash does not match its payload")

    ledger_evaluation = document.get("evaluation")
    if not isinstance(ledger_evaluation, dict):
        raise ValueError("Decision Ledger evaluation must be an object")
    expected_bindings: tuple[tuple[object, object, str], ...] = (
        (
            ledger_evaluation.get("evaluation_payload_hash"),
            evaluation.evaluation_payload_hash,
            "evaluation_payload_hash",
        ),
        (document.get("selected_solution_plan_id"), evaluation.selected_plan_id, "selection"),
        (document.get("request_id"), metadata.purchase_request_id, "purchase request"),
        (document.get("purchase_brief_id"), metadata.purchase_brief_id, "purchase brief"),
    )
    if metadata.decision_id is not None:
        expected_bindings += ((document.get("decision_id"), metadata.decision_id, "decision"),)
    for actual, expected, label in expected_bindings:
        if actual != expected:
            raise ValueError(f"Decision Ledger {label} does not match persistence metadata")

    plans = document.get("solution_plans")
    if not isinstance(plans, list) or any(not isinstance(item, dict) for item in plans):
        raise ValueError("Decision Ledger solution_plans must be an array of objects")
    plan_ids = [item.get("solution_plan_id") for item in plans]
    expected_plan_ids = [item.plan_id for item in evaluation.plans]
    if len(plan_ids) != len(set(plan_ids)) or set(plan_ids) != set(expected_plan_ids):
        raise ValueError("Decision Ledger Solution Plans do not match the graph evaluation")
    return document


def _input_payload(
    evaluation: DecisionGraphEvaluation,
    metadata: EvaluationPersistenceMetadata,
) -> dict[str, Any]:
    return _json_document(
        {
            "schema_version": "decision_graph_input_hashes_v1",
            "run_kind": "BASE",
            "versions": evaluation.versions,
            "evaluated_at": evaluation.evaluated_at,
            "candidate_set_version": metadata.candidate_set_version,
            "quote_set_version": metadata.quote_set_version,
            "risk_rule_set_version": metadata.risk_rule_set_version,
            "frozen_input_hashes": evaluation.frozen_input_hashes,
            "removed_private_fact_ids": evaluation.removed_private_fact_ids,
        }
    )


def _candidate_members(
    *,
    evaluation: DecisionGraphEvaluation,
    decision_input: DecisionGraphInput,
    metadata: EvaluationPersistenceMetadata,
    discovery_run_id: str,
) -> tuple[CandidateSetMember, ...]:
    identity_by_record = {
        record_id: identity
        for identity in evaluation.identity_records
        for record_id in identity.record_ids
    }
    duplicate_ids = {item.merged_record_id for item in evaluation.identity_merges}
    exclusion_by_record = {
        item.record_id: item for item in evaluation.recall_exclusions
    }
    rows: list[CandidateSetMember] = []
    ordinal = 0
    for candidate in sorted(decision_input.candidates, key=lambda item: item.record_id):
        identity = identity_by_record.get(candidate.record_id)
        exclusion = exclusion_by_record.get(candidate.record_id)
        if identity is None and exclusion is None:
            raise ValueError(f"Candidate {candidate.record_id} is absent from graph discovery")
        if exclusion is not None:
            canonical_identity_id = "excluded_" + content_hash(
                candidate.record_id
            ).split(":", 1)[1][:20]
            disposition = "EXCLUDED"
            canonical_identity: dict[str, Any] | None = None
            exclusion_payload: dict[str, str] | None = {
                "reason_code": exclusion.reason_code,
                "detail": exclusion.detail,
            }
        else:
            assert identity is not None
            canonical_identity_id = identity.canonical_id
            disposition = "DEDUPLICATED" if candidate.record_id in duplicate_ids else "INCLUDED"
            canonical_identity = {
                "seller_id": identity.seller_id,
                "product_id": identity.product_id,
                "edition": identity.edition,
                "region": identity.region,
                "record_ids": list(identity.record_ids),
                "pack_ids": list(identity.pack_ids),
                "offer_ids": list(identity.offer_ids),
            }
            exclusion_payload = None
        payload = {
            "canonical_identity_id": canonical_identity_id,
            "source_record_id": candidate.record_id,
            "member_kind": "PACK",
            "disposition": disposition,
            "ordinal": ordinal,
            "pack_id": candidate.pack_id,
            "pack_version": candidate.pack_version,
            "offer_id": candidate.offer_id,
            "offer_version": None,
            "authority": candidate.authority.value,
            "available": candidate.available,
            "seller_gate_ids": list(candidate.seller_gate_ids),
            "canonical_identity": canonical_identity,
            "exclusion": exclusion_payload,
        }
        member_hash = content_hash(payload)
        rows.append(
            CandidateSetMember(
                id=_stable_id(
                    "csm", metadata.organization_id, discovery_run_id, candidate.record_id
                ),
                organization_id=metadata.organization_id,
                discovery_run_id=discovery_run_id,
                canonical_identity_id=canonical_identity_id,
                source_record_id=candidate.record_id,
                member_kind="PACK",
                disposition=disposition,
                ordinal=ordinal,
                pack_id=candidate.pack_id,
                pack_version=candidate.pack_version,
                offer_id=candidate.offer_id,
                offer_version=None,
                current_action_id=None,
                member_hash=member_hash,
                payload=payload,
            )
        )
        ordinal += 1

    for action in sorted(decision_input.current_actions, key=lambda item: item.action_id):
        if action.action.value == "NO_ACTION":
            member_kind = "NO_ACTION"
        elif action.action.value in _CURRENT_STACK_ACTIONS:
            member_kind = "CURRENT_STACK"
        else:
            member_kind = "CONTRACT_ACTION"
        canonical_identity_id = action.instance_id
        payload = {
            "canonical_identity_id": canonical_identity_id,
            "source_record_id": action.action_id,
            "member_kind": member_kind,
            "disposition": "INCLUDED",
            "ordinal": ordinal,
            "current_action_id": action.action_id,
            "instance_id": action.instance_id,
            "action": action.action.value,
            "available": action.available,
        }
        member_hash = content_hash(payload)
        rows.append(
            CandidateSetMember(
                id=_stable_id("csm", metadata.organization_id, discovery_run_id, action.action_id),
                organization_id=metadata.organization_id,
                discovery_run_id=discovery_run_id,
                canonical_identity_id=canonical_identity_id,
                source_record_id=action.action_id,
                member_kind=member_kind,
                disposition="INCLUDED",
                ordinal=ordinal,
                pack_id=None,
                pack_version=None,
                offer_id=None,
                offer_version=None,
                current_action_id=action.action_id,
                member_hash=member_hash,
                payload=payload,
            )
        )
        ordinal += 1
    if len({row.source_record_id for row in rows}) != len(rows):
        raise ValueError("Candidate and current-action source IDs must be globally unique")
    return tuple(rows)


def _identity_merges(
    *,
    evaluation: DecisionGraphEvaluation,
    metadata: EvaluationPersistenceMetadata,
    discovery_run_id: str,
) -> tuple[IdentityMerge, ...]:
    rows: list[IdentityMerge] = []
    for merge in evaluation.identity_merges:
        payload = {
            "canonical_identity_id": merge.canonical_id,
            "merged_record_id": merge.merged_record_id,
            "reason_codes": list(merge.reasons),
        }
        rows.append(
            IdentityMerge(
                id=_stable_id(
                    "idm", metadata.organization_id, discovery_run_id, merge.merged_record_id
                ),
                organization_id=metadata.organization_id,
                discovery_run_id=discovery_run_id,
                canonical_identity_id=merge.canonical_id,
                merged_record_id=merge.merged_record_id,
                reason_codes=list(merge.reasons),
                merge_hash=content_hash(payload),
            )
        )
    return tuple(rows)


def _solution_plan_records(
    *,
    evaluation: DecisionGraphEvaluation,
    ledger: dict[str, Any],
    metadata: EvaluationPersistenceMetadata,
    evaluation_run_id: str,
    commercial_terms_by_plan_id: Mapping[str, Mapping[str, Any]],
) -> tuple[EvaluationSolutionPlan, ...]:
    raw_plans = cast(list[dict[str, Any]], ledger["solution_plans"])
    ledger_plan_by_id = {cast(str, item["solution_plan_id"]): item for item in raw_plans}
    rank_by_id = {
        plan_id: position for position, plan_id in enumerate(evaluation.ranked_plan_ids, start=1)
    }
    rows: list[EvaluationSolutionPlan] = []
    for plan in evaluation.plans:
        payload = _json_document(ledger_plan_by_id[plan.plan_id])
        commercial_terms = commercial_terms_by_plan_id.get(plan.plan_id)
        if commercial_terms is not None:
            payload["commercial_terms"] = _json_document(commercial_terms)
        rows.append(
            EvaluationSolutionPlan(
                id=_stable_id("esp", metadata.organization_id, evaluation_run_id, plan.plan_id),
                organization_id=metadata.organization_id,
                evaluation_run_id=evaluation_run_id,
                solution_plan_id=plan.plan_id,
                action=plan.action.value,
                component_hash=plan.component_hash,
                plan_hash=content_hash(payload),
                construction_lifecycle=plan.construction_lifecycle.value,
                lifecycle=plan.lifecycle.value,
                candidate_status=plan.status.value,
                primary_reason_code=(
                    plan.primary_reason.reason_code if plan.primary_reason is not None else None
                ),
                rank_position=rank_by_id.get(plan.plan_id),
                selected=plan.plan_id == evaluation.selected_plan_id,
                ordering_frontier_member=plan.ordering_frontier_member,
                resolution_frontier_member=plan.resolution_frontier_member,
                quote_required=plan.quote_required,
                quote_policy_reason=plan.quote_policy_reason,
                permitted_resolution=plan.permitted_resolution,
                autonomous_execution_allowed=plan.autonomous_execution_allowed,
                stable_action_ids=list(plan.stable_action_ids),
                payload=payload,
            )
        )
    return tuple(rows)


def _component_source(
    plan: EvaluatedPlan,
    component_index: int,
    evaluation: DecisionGraphEvaluation,
    decision_input: DecisionGraphInput,
) -> tuple[str, str | None]:
    component = plan.components[component_index]
    if component.source_type == "PACK":
        identity = next(
            (
                item
                for item in evaluation.identity_records
                if item.product_id == component.component_id
            ),
            None,
        )
        if identity is None:
            raise ValueError(f"Plan component {component.component_id} has no canonical identity")
        return "PACK", identity.record_ids[0]
    if component.source_type != "CURRENT_INSTANCE":
        raise ValueError(f"Unsupported graph component source type: {component.source_type}")
    matching_action = next(
        (
            item
            for item in decision_input.current_actions
            if item.instance_id == component.component_id and item.action == component.action
        ),
        None,
    )
    if matching_action is None:
        raise ValueError(
            f"Plan component {component.component_id} has no matching frozen current action"
        )
    source_record_id = matching_action.action_id
    if component.action.value == "NO_ACTION":
        return "NO_ACTION", source_record_id
    if component.action.value in _CURRENT_STACK_ACTIONS:
        return "CURRENT_STACK", source_record_id
    return "CONTRACT_ACTION", source_record_id


def _plan_components(
    *,
    evaluation: DecisionGraphEvaluation,
    decision_input: DecisionGraphInput,
    metadata: EvaluationPersistenceMetadata,
    evaluation_run_id: str,
    plan_record_ids: Mapping[str, str],
) -> tuple[SolutionPlanComponent, ...]:
    rows: list[SolutionPlanComponent] = []
    for plan in evaluation.plans:
        plan_record_id = plan_record_ids[plan.plan_id]
        for ordinal, component in enumerate(plan.components):
            source_type, source_record_id = _component_source(
                plan, ordinal, evaluation, decision_input
            )
            payload = {
                "component_id": component.component_id,
                "ordinal": ordinal,
                "source_type": source_type,
                "source_record_id": source_record_id,
                "action": component.action.value,
            }
            rows.append(
                SolutionPlanComponent(
                    id=_stable_id(
                        "spc",
                        metadata.organization_id,
                        plan_record_id,
                        component.component_id,
                        ordinal,
                    ),
                    organization_id=metadata.organization_id,
                    evaluation_run_id=evaluation_run_id,
                    solution_plan_record_id=plan_record_id,
                    component_id=component.component_id,
                    ordinal=ordinal,
                    source_type=source_type,
                    action=component.action.value,
                    source_record_id=source_record_id,
                    component_hash=content_hash(payload),
                    payload=payload,
                )
            )
    return tuple(rows)


def _gate_results(
    *,
    evaluation: DecisionGraphEvaluation,
    decision_input: DecisionGraphInput,
    metadata: EvaluationPersistenceMetadata,
    evaluation_run_id: str,
    plan_record_ids: Mapping[str, str],
) -> tuple[DecisionGateResult, ...]:
    rules = {item.gate_id: item for item in decision_input.gates}
    rows: list[DecisionGateResult] = []
    for plan in evaluation.plans:
        plan_record_id = plan_record_ids[plan.plan_id]
        for result in plan.gate_results:
            rule = rules.get(result.gate_id)
            reason_codes = [item.reason_code for item in result.reasons]
            derived_status = result.reasons[0].status.value if result.reasons else None
            payload = {
                "gate_id": result.gate_id,
                "truth": result.truth.value,
                "derived_status": derived_status,
                "is_primary": plan.primary_reason in result.reasons,
                "reason_codes": reason_codes,
                "reasons": [
                    {
                        "reason_code": reason.reason_code,
                        "status": reason.status.value,
                        "detail": reason.detail,
                    }
                    for reason in result.reasons
                ],
                "evaluated_predicates": list(result.evaluated_predicates),
                "source_fact_ids": list(rule.source_fact_ids) if rule is not None else [],
                "permitted_resolution": result.permitted_resolution,
                "overridable": rule.overridable if rule is not None else False,
            }
            rows.append(
                DecisionGateResult(
                    id=_stable_id("dgr", metadata.organization_id, plan_record_id, result.gate_id),
                    organization_id=metadata.organization_id,
                    evaluation_run_id=evaluation_run_id,
                    solution_plan_record_id=plan_record_id,
                    gate_id=result.gate_id,
                    truth=result.truth.value,
                    derived_status=derived_status,
                    is_primary=cast(bool, payload["is_primary"]),
                    reason_codes=reason_codes,
                    evaluated_predicates=list(result.evaluated_predicates),
                    source_fact_ids=list(rule.source_fact_ids) if rule is not None else [],
                    permitted_resolution=result.permitted_resolution,
                    overridable=rule.overridable if rule is not None else False,
                    result_hash=content_hash(payload),
                )
            )
    return tuple(rows)


def _evidence_assessments(
    *,
    evaluation: DecisionGraphEvaluation,
    decision_input: DecisionGraphInput,
    metadata: EvaluationPersistenceMetadata,
    evaluation_run_id: str,
) -> tuple[EvidenceAssessmentRecord, ...]:
    preference_fields = {
        criterion.criterion_id: criterion.field for criterion in decision_input.preferences
    }
    supported_by_evidence: dict[str, set[str]] = {}
    for plan in evaluation.plans:
        for score in plan.score_components:
            for evidence_id in score.evidence_ids:
                supported_by_evidence.setdefault(evidence_id, set()).add(score.criterion_id)
    rows: list[EvidenceAssessmentRecord] = []
    for assessment in evaluation.evidence_assessments:
        supported = sorted(
            criterion_id
            for criterion_id in supported_by_evidence.get(assessment.evidence_id, set())
            if preference_fields.get(criterion_id) == assessment.field
        )
        age = assessment.age_bounds
        payload = {
            "evidence_id": assessment.evidence_id,
            "source_record_id": assessment.record_id,
            "field": assessment.field,
            "supported_criterion_ids": supported,
            "source_allowed": assessment.source_allowed,
            "method_allowed": assessment.method_allowed,
            "scope_match": assessment.scope_match,
            "reconstructable": assessment.reconstructable,
            "freshness_current": assessment.freshness_current,
            "disputed": assessment.disputed,
            "revoked": assessment.revoked,
            "state": assessment.state.value,
            "age_lower": None if age is None else age.lower.to_dict(),
            "age_upper": None if age is None else age.upper.to_dict(),
            "reason_codes": list(assessment.reasons),
        }
        rows.append(
            EvidenceAssessmentRecord(
                id=_stable_id(
                    "ear",
                    metadata.organization_id,
                    evaluation_run_id,
                    assessment.evidence_id,
                    assessment.field,
                ),
                organization_id=metadata.organization_id,
                evaluation_run_id=evaluation_run_id,
                evidence_id=assessment.evidence_id,
                source_record_id=assessment.record_id,
                field=assessment.field,
                supported_criterion_ids=supported,
                source_allowed=assessment.source_allowed,
                method_allowed=assessment.method_allowed,
                scope_match=assessment.scope_match,
                reconstructable=assessment.reconstructable,
                freshness_current=assessment.freshness_current,
                disputed=assessment.disputed,
                revoked=assessment.revoked,
                state=assessment.state.value,
                age_lower_numerator=None if age is None else age.lower.numerator,
                age_lower_denominator=None if age is None else age.lower.denominator,
                age_upper_numerator=None if age is None else age.upper.numerator,
                age_upper_denominator=None if age is None else age.upper.denominator,
                reason_codes=list(assessment.reasons),
                assessment_hash=content_hash(payload),
            )
        )
    return tuple(rows)


def _score_components(
    *,
    evaluation: DecisionGraphEvaluation,
    decision_input: DecisionGraphInput,
    metadata: EvaluationPersistenceMetadata,
    evaluation_run_id: str,
    plan_record_ids: Mapping[str, str],
) -> tuple[ScoreComponentRecord, ...]:
    preferences = {item.criterion_id: item for item in decision_input.preferences}
    frozen_input_hashes = dict(evaluation.frozen_input_hashes)
    rows: list[ScoreComponentRecord] = []
    for plan in evaluation.plans:
        plan_record_id = plan_record_ids[plan.plan_id]
        for component in plan.score_components:
            preference = preferences.get(component.criterion_id)
            if preference is None:
                raise ValueError(f"Score criterion {component.criterion_id} is not frozen")
            input_hash = content_hash(
                {
                    "criterion_id": component.criterion_id,
                    "stable_action_ids": plan.stable_action_ids,
                    "evidence_ids": component.evidence_ids,
                    "frozen_input_hashes": frozen_input_hashes,
                }
            )
            payload = {
                "criterion_id": component.criterion_id,
                "weight": component.weight,
                "coverage_weight": preference.coverage_weight,
                "conservative_satisfaction": component.conservative_satisfaction.to_dict(),
                "optimistic_satisfaction": component.optimistic_satisfaction.to_dict(),
                "contribution_conservative": component.contribution_conservative.to_dict(),
                "contribution_optimistic": component.contribution_optimistic.to_dict(),
                "evidence_ids": list(component.evidence_ids),
                "evidence_state": component.evidence_state.value,
                "prior_label": component.prior_label,
                "input_hash": input_hash,
            }
            rows.append(
                ScoreComponentRecord(
                    id=_stable_id(
                        "scr", metadata.organization_id, plan_record_id, component.criterion_id
                    ),
                    organization_id=metadata.organization_id,
                    evaluation_run_id=evaluation_run_id,
                    solution_plan_record_id=plan_record_id,
                    criterion_id=component.criterion_id,
                    weight=component.weight,
                    coverage_weight=preference.coverage_weight,
                    conservative_satisfaction_numerator=(
                        component.conservative_satisfaction.numerator
                    ),
                    conservative_satisfaction_denominator=(
                        component.conservative_satisfaction.denominator
                    ),
                    optimistic_satisfaction_numerator=(component.optimistic_satisfaction.numerator),
                    optimistic_satisfaction_denominator=(
                        component.optimistic_satisfaction.denominator
                    ),
                    contribution_conservative_numerator=(
                        component.contribution_conservative.numerator
                    ),
                    contribution_conservative_denominator=(
                        component.contribution_conservative.denominator
                    ),
                    contribution_optimistic_numerator=(component.contribution_optimistic.numerator),
                    contribution_optimistic_denominator=(
                        component.contribution_optimistic.denominator
                    ),
                    evidence_ids=list(component.evidence_ids),
                    evidence_state=component.evidence_state.value,
                    prior_label=component.prior_label,
                    input_hash=input_hash,
                    component_hash=content_hash(payload),
                )
            )
    return tuple(rows)


def _ratio_pair(value: ExactRatio) -> tuple[int, int]:
    return value.numerator, value.denominator


def _ratio_midpoint(lower: ExactRatio, upper: ExactRatio) -> tuple[int, int]:
    midpoint = (lower.fraction + upper.fraction) / 2
    return midpoint.numerator, midpoint.denominator


def _money_pair(value: Decimal) -> tuple[int, int]:
    numerator, denominator = value.as_integer_ratio()
    return numerator, denominator


def _bound_reason(plan: EvaluatedPlan, dimension: str) -> str:
    tokens = {
        "PREFERENCE": ("PREFERENCE",),
        "STACK_RISK": ("RISK",),
        "TCO": ("TCO", "COST"),
        "DECISION_MATERIAL_COVERAGE": ("COVERAGE",),
        "EVIDENCE_AGE": ("EVIDENCE_TIME", "AGE"),
    }[dimension]
    for reason in plan.dimensions.bound_unavailable_reasons:
        if any(token in reason.upper() for token in tokens):
            return reason
    if plan.dimensions.bound_unavailable_reasons:
        return plan.dimensions.bound_unavailable_reasons[0]
    return f"BOUND_UNAVAILABLE:{dimension}"


def _score_bound(
    *,
    metadata: EvaluationPersistenceMetadata,
    evaluation_run_id: str,
    solution_plan_record_id: str,
    dimension: str,
    value_kind: str,
    values: tuple[tuple[int, int], tuple[int, int], tuple[int, int]] | None,
    currency: str | None,
    unavailable_reason: str | None,
    calculation_payload: dict[str, Any],
) -> ScoreBound:
    if values is None:
        lower_numerator = lower_denominator = None
        base_numerator = base_denominator = None
        upper_numerator = upper_denominator = None
        bound_status = "BOUND_UNAVAILABLE"
    else:
        (
            (lower_numerator, lower_denominator),
            (base_numerator, base_denominator),
            (
                upper_numerator,
                upper_denominator,
            ),
        ) = values
        bound_status = "AVAILABLE"
    hash_payload = {
        "solution_plan_record_id": solution_plan_record_id,
        "dimension": dimension,
        "bound_status": bound_status,
        "value_kind": value_kind,
        "lower": None
        if values is None
        else {"numerator": lower_numerator, "denominator": lower_denominator},
        "base": None
        if values is None
        else {"numerator": base_numerator, "denominator": base_denominator},
        "upper": None
        if values is None
        else {"numerator": upper_numerator, "denominator": upper_denominator},
        "currency": currency,
        "unavailable_reason": unavailable_reason,
        "calculation": calculation_payload,
    }
    return ScoreBound(
        id=_stable_id("sbd", metadata.organization_id, solution_plan_record_id, dimension),
        organization_id=metadata.organization_id,
        evaluation_run_id=evaluation_run_id,
        solution_plan_record_id=solution_plan_record_id,
        dimension=dimension,
        bound_status=bound_status,
        value_kind=value_kind,
        lower_numerator=lower_numerator,
        lower_denominator=lower_denominator,
        base_numerator=base_numerator,
        base_denominator=base_denominator,
        upper_numerator=upper_numerator,
        upper_denominator=upper_denominator,
        currency=currency,
        unavailable_reason=unavailable_reason,
        calculation_payload=calculation_payload,
        bound_hash=content_hash(hash_payload),
    )


def _score_bounds(
    *,
    evaluation: DecisionGraphEvaluation,
    metadata: EvaluationPersistenceMetadata,
    evaluation_run_id: str,
    plan_record_ids: Mapping[str, str],
) -> tuple[ScoreBound, ...]:
    rows: list[ScoreBound] = []
    for plan in evaluation.plans:
        record_id = plan_record_ids[plan.plan_id]
        dimensions = plan.dimensions

        preference = dimensions.preference
        if preference is None:
            preference_values = None
            preference_reason: str | None = _bound_reason(plan, "PREFERENCE")
        else:
            preference_values = (
                _ratio_pair(preference.conservative),
                _ratio_midpoint(preference.conservative, preference.optimistic),
                _ratio_pair(preference.optimistic),
            )
            preference_reason = None
        rows.append(
            _score_bound(
                metadata=metadata,
                evaluation_run_id=evaluation_run_id,
                solution_plan_record_id=record_id,
                dimension="PREFERENCE",
                value_kind="RATIO",
                values=preference_values,
                currency=None,
                unavailable_reason=preference_reason,
                calculation_payload={"base_derivation": "EXACT_MIDPOINT"},
            )
        )

        risk = dimensions.stack_risk
        if risk is None:
            risk_values = None
            risk_reason: str | None = _bound_reason(plan, "STACK_RISK")
        else:
            risk_values = ((risk.lower.rank, 1), (risk.base.rank, 1), (risk.upper.rank, 1))
            risk_reason = None
        rows.append(
            _score_bound(
                metadata=metadata,
                evaluation_run_id=evaluation_run_id,
                solution_plan_record_id=record_id,
                dimension="STACK_RISK",
                value_kind="RISK_ORDINAL",
                values=risk_values,
                currency=None,
                unavailable_reason=risk_reason,
                calculation_payload={
                    "risk_input_hash": dimensions.risk_input_hash,
                    "triggered_rule_ids": list(dimensions.triggered_risk_rule_ids),
                },
            )
        )

        cost = dimensions.total_cost
        if cost.low is None or cost.base is None or cost.high is None:
            cost_values = None
            cost_currency = metadata.valuation_currency
            cost_reason: str | None = _bound_reason(plan, "TCO")
        else:
            currencies = {cost.low.currency, cost.base.currency, cost.high.currency}
            if len(currencies) != 1:
                raise ValueError(f"Plan {plan.plan_id} TCO bounds use different currencies")
            cost_values = (
                _money_pair(cost.low.amount),
                _money_pair(cost.base.amount),
                _money_pair(cost.high.amount),
            )
            cost_currency = cost.low.currency
            cost_reason = None
        rows.append(
            _score_bound(
                metadata=metadata,
                evaluation_run_id=evaluation_run_id,
                solution_plan_record_id=record_id,
                dimension="TCO",
                value_kind="MONEY",
                values=cost_values,
                currency=cost_currency,
                unavailable_reason=cost_reason,
                calculation_payload=_json_document(
                    {
                        "offer_id": cost.offer_id,
                        "horizon_days": cost.horizon_days,
                        "payment_required": cost.payment_required,
                        "line_items": cost.line_items,
                    }
                ),
            )
        )

        coverage = dimensions.decision_material_coverage
        if coverage is None:
            coverage_values = None
            coverage_reason: str | None = _bound_reason(plan, "DECISION_MATERIAL_COVERAGE")
        else:
            coverage_values = (
                _ratio_pair(coverage.conservative),
                _ratio_midpoint(coverage.conservative, coverage.optimistic),
                _ratio_pair(coverage.optimistic),
            )
            coverage_reason = None
        rows.append(
            _score_bound(
                metadata=metadata,
                evaluation_run_id=evaluation_run_id,
                solution_plan_record_id=record_id,
                dimension="DECISION_MATERIAL_COVERAGE",
                value_kind="RATIO",
                values=coverage_values,
                currency=None,
                unavailable_reason=coverage_reason,
                calculation_payload={"base_derivation": "EXACT_MIDPOINT"},
            )
        )

        age = dimensions.maximum_evidence_age_ratio
        if age is None:
            age_values = None
            age_reason: str | None = _bound_reason(plan, "EVIDENCE_AGE")
        else:
            age_values = (
                _ratio_pair(age.lower),
                _ratio_midpoint(age.lower, age.upper),
                _ratio_pair(age.upper),
            )
            age_reason = None
        rows.append(
            _score_bound(
                metadata=metadata,
                evaluation_run_id=evaluation_run_id,
                solution_plan_record_id=record_id,
                dimension="EVIDENCE_AGE",
                value_kind="RATIO",
                values=age_values,
                currency=None,
                unavailable_reason=age_reason,
                calculation_payload={"base_derivation": "EXACT_MIDPOINT"},
            )
        )

        hard = (dimensions.hard_coverage.numerator, dimensions.hard_coverage.denominator)
        rows.append(
            _score_bound(
                metadata=metadata,
                evaluation_run_id=evaluation_run_id,
                solution_plan_record_id=record_id,
                dimension="HARD_COVERAGE",
                value_kind="RATIO",
                values=(hard, hard, hard),
                currency=None,
                unavailable_reason=None,
                calculation_payload={"operator": "SATISFIED_HARD_GATES_OVER_APPLICABLE"},
            )
        )
        universe = _ratio_pair(dimensions.universe_coverage)
        rows.append(
            _score_bound(
                metadata=metadata,
                evaluation_run_id=evaluation_run_id,
                solution_plan_record_id=record_id,
                dimension="UNIVERSE_COVERAGE",
                value_kind="RATIO",
                values=(universe, universe, universe),
                currency=None,
                unavailable_reason=None,
                calculation_payload={"operator": "EVALUATED_UNIVERSE_COVERAGE"},
            )
        )
    if any(dimension not in _BOUND_DIMENSIONS for dimension in (row.dimension for row in rows)):
        raise AssertionError("adapter emitted an unsupported score-bound dimension")
    return tuple(rows)


def _robustness_frontiers(
    *,
    evaluation: DecisionGraphEvaluation,
    metadata: EvaluationPersistenceMetadata,
    evaluation_run_id: str,
    plan_record_ids: Mapping[str, str],
) -> tuple[RobustnessFrontier, ...]:
    rows: list[RobustnessFrontier] = []
    bound_unavailable = set(evaluation.bound_unavailable_plan_ids)
    for plan in evaluation.plans:
        plan_record_id = plan_record_ids[plan.plan_id]
        frontier_values = (
            (
                "ORDERING",
                plan.ordering_frontier_member,
                False
                if plan.plan_id == evaluation.selected_plan_id
                else (
                    None
                    if evaluation.rank_stability == "UNDETERMINED"
                    else plan.ordering_frontier_member
                ),
                None,
            ),
            ("RESOLUTION", plan.resolution_frontier_member, None, plan.permitted_resolution),
            (
                "BOUND_UNAVAILABLE",
                plan.plan_id in bound_unavailable,
                None,
                plan.permitted_resolution,
            ),
        )
        for frontier_kind, member, can_beat_selected, permitted_resolution in frontier_values:
            payload = {
                "frontier_kind": frontier_kind,
                "solution_plan_id": plan.plan_id,
                "stable_action_ids": list(plan.stable_action_ids),
                "decision_rank_stability": evaluation.rank_stability,
                "member": member,
                "can_beat_selected": can_beat_selected,
                "permitted_resolution": permitted_resolution,
            }
            rows.append(
                RobustnessFrontier(
                    id=_stable_id("rbf", metadata.organization_id, plan_record_id, frontier_kind),
                    organization_id=metadata.organization_id,
                    evaluation_run_id=evaluation_run_id,
                    solution_plan_record_id=plan_record_id,
                    frontier_kind=frontier_kind,
                    decision_rank_stability=evaluation.rank_stability,
                    member=member,
                    can_beat_selected=can_beat_selected,
                    permitted_resolution=permitted_resolution,
                    frontier_payload=payload,
                    frontier_hash=content_hash(payload),
                )
            )
    return tuple(rows)


def build_evaluation_graph_write(
    decision: DecisionGraphDecision,
    decision_input: DecisionGraphInput,
    ledger: Mapping[str, Any],
    metadata: EvaluationPersistenceMetadata,
    *,
    commercial_terms_by_plan_id: Mapping[str, Mapping[str, Any]] | None = None,
) -> EvaluationGraphWrite:
    """Build the complete normalized BASE evaluation aggregate for one Decision."""

    evaluation = decision.base
    if evaluation.versions != decision_input.versions:
        raise ValueError("Decision Graph evaluation versions do not match its frozen input")
    ledger_document = _ledger_document(ledger, evaluation=evaluation, metadata=metadata)
    frozen_commercial_terms = commercial_terms_by_plan_id or {}
    unknown_commercial_plan_ids = set(frozen_commercial_terms) - {
        plan.plan_id for plan in evaluation.plans
    }
    if unknown_commercial_plan_ids:
        raise ValueError("Commercial terms reference an unknown Solution Plan")
    pipeline = build_evaluation_pipeline_version(decision_input, metadata)
    input_payload = _input_payload(evaluation, metadata)
    evaluation_payload = _json_document(evaluation_canonical_payload(evaluation))
    if content_hash(evaluation_payload) != evaluation.evaluation_payload_hash:
        raise ValueError("Decision Graph evaluation payload hash is inconsistent")
    evaluation_run_id = _stable_id(
        "evr",
        metadata.organization_id,
        metadata.purchase_request_id,
        "BASE",
        evaluation.evaluation_payload_hash,
    )
    evaluation_run = EvaluationRun(
        id=evaluation_run_id,
        organization_id=metadata.organization_id,
        purchase_request_id=metadata.purchase_request_id,
        purchase_brief_id=metadata.purchase_brief_id,
        decision_id=metadata.decision_id,
        evaluation_pipeline_version_id=pipeline.id,
        run_kind="BASE",
        evaluated_at=evaluation.evaluated_at,
        request_version=evaluation.versions.request_version,
        company_profile_version=evaluation.versions.company_profile_version,
        stackfile_version=evaluation.versions.stackfile_version,
        registry_version=evaluation.versions.registry_version,
        candidate_set_version=metadata.candidate_set_version,
        pack_set_version=evaluation.versions.pack_set_version,
        offer_set_version=evaluation.versions.offer_set_version,
        quote_set_version=metadata.quote_set_version,
        taxonomy_version=evaluation.versions.taxonomy_version,
        normalization_version=evaluation.versions.normalization_version,
        policy_version=evaluation.versions.policy_version,
        fx_version=evaluation.versions.fx_version,
        pipeline_version=evaluation.versions.pipeline_version,
        engine_version=evaluation.versions.engine_version,
        input_payload_hash=content_hash(input_payload),
        input_payload=input_payload,
        evaluation_payload_hash=evaluation.evaluation_payload_hash,
        evaluation_payload=evaluation_payload,
        selected_solution_plan_id=evaluation.selected_plan_id,
        rank_stability=evaluation.rank_stability,
    )

    discovery_run_id = _stable_id("dsr", metadata.organization_id, evaluation_run_id)
    candidate_members = _candidate_members(
        evaluation=evaluation,
        decision_input=decision_input,
        metadata=metadata,
        discovery_run_id=discovery_run_id,
    )
    universe = ledger_document.get("evaluated_universe")
    if not isinstance(universe, dict):
        raise ValueError("Decision Ledger evaluated_universe must be an object")
    frozen_input_hashes = dict(evaluation.frozen_input_hashes)
    candidate_set_hash_payload = {
        "candidate_set_version": metadata.candidate_set_version,
        "candidate_records_hash": frozen_input_hashes["candidate_records"],
        "current_actions_hash": frozen_input_hashes["current_actions"],
        "member_hashes": [item.member_hash for item in candidate_members],
    }
    discovery_payload = _json_document(
        {
            **candidate_set_hash_payload,
            "evaluated_universe": universe,
        }
    )
    discovery_run = DiscoveryRun(
        id=discovery_run_id,
        organization_id=metadata.organization_id,
        evaluation_run_id=evaluation_run_id,
        candidate_set_hash=content_hash(candidate_set_hash_payload),
        output_hash=content_hash(discovery_payload),
        raw_record_count=evaluation.coverage.raw_record_count,
        canonical_product_count=evaluation.coverage.canonical_product_count,
        duplicate_count=evaluation.coverage.duplicate_count,
        generated_solution_plan_count=evaluation.coverage.generated_solution_plan_count,
        excluded_count=evaluation.coverage.excluded_count,
        payload=discovery_payload,
    )
    plan_records = _solution_plan_records(
        evaluation=evaluation,
        ledger=ledger_document,
        metadata=metadata,
        evaluation_run_id=evaluation_run_id,
        commercial_terms_by_plan_id=frozen_commercial_terms,
    )
    plan_record_ids = {item.solution_plan_id: item.id for item in plan_records}
    return EvaluationGraphWrite(
        evaluation_run=evaluation_run,
        discovery_run=discovery_run,
        solution_plans=plan_records,
        candidate_set_members=candidate_members,
        identity_merges=_identity_merges(
            evaluation=evaluation,
            metadata=metadata,
            discovery_run_id=discovery_run_id,
        ),
        decision_gate_results=_gate_results(
            evaluation=evaluation,
            decision_input=decision_input,
            metadata=metadata,
            evaluation_run_id=evaluation_run_id,
            plan_record_ids=plan_record_ids,
        ),
        evidence_assessments=_evidence_assessments(
            evaluation=evaluation,
            decision_input=decision_input,
            metadata=metadata,
            evaluation_run_id=evaluation_run_id,
        ),
        solution_plan_components=_plan_components(
            evaluation=evaluation,
            decision_input=decision_input,
            metadata=metadata,
            evaluation_run_id=evaluation_run_id,
            plan_record_ids=plan_record_ids,
        ),
        score_components=_score_components(
            evaluation=evaluation,
            decision_input=decision_input,
            metadata=metadata,
            evaluation_run_id=evaluation_run_id,
            plan_record_ids=plan_record_ids,
        ),
        score_bounds=_score_bounds(
            evaluation=evaluation,
            metadata=metadata,
            evaluation_run_id=evaluation_run_id,
            plan_record_ids=plan_record_ids,
        ),
        robustness_frontiers=_robustness_frontiers(
            evaluation=evaluation,
            metadata=metadata,
            evaluation_run_id=evaluation_run_id,
            plan_record_ids=plan_record_ids,
        ),
    )


def build_counterfactual_record(
    decision: DecisionGraphDecision,
    metadata: EvaluationPersistenceMetadata,
) -> CounterfactualRecordModel:
    """Build the hash-linked counterfactual row without any private fact values."""

    counterfactual = decision.counterfactual
    payload = _json_document(
        {
            "outcome": counterfactual.outcome.value,
            "removed_fact_ids": counterfactual.removed_fact_ids,
            "alternative_fact_id_sets": counterfactual.alternative_fact_id_sets,
            "tested_limit": counterfactual.tested_limit,
            "before_evaluation_payload_hash": counterfactual.before_evaluation_payload_hash,
            "after_evaluation_payload_hash": counterfactual.after_evaluation_payload_hash,
            "generic_evaluation_payload_hash": counterfactual.generic_evaluation_payload_hash,
            "before_selected_plan_id": counterfactual.before_selected_plan_id,
            "after_selected_plan_id": counterfactual.after_selected_plan_id,
            "generic_selected_plan_id": counterfactual.generic_selected_plan_id,
            "changed_gate_ids": counterfactual.changed_gate_ids,
        }
    )
    if content_hash(payload) != counterfactual.record_hash:
        raise ValueError("Decision Graph counterfactual record hash is inconsistent")
    return CounterfactualRecordModel(
        id=_stable_id("cfr", metadata.organization_id, counterfactual.record_hash),
        organization_id=metadata.organization_id,
        decision_id=metadata.decision_id,
        outcome=counterfactual.outcome.value,
        removed_fact_ids=list(counterfactual.removed_fact_ids),
        alternative_fact_id_sets=[
            list(fact_ids) for fact_ids in counterfactual.alternative_fact_id_sets
        ],
        tested_limit=counterfactual.tested_limit,
        base_evaluation_payload_hash=counterfactual.before_evaluation_payload_hash,
        alternate_evaluation_payload_hash=counterfactual.after_evaluation_payload_hash,
        generic_evaluation_payload_hash=counterfactual.generic_evaluation_payload_hash,
        base_selected_solution_plan_id=counterfactual.before_selected_plan_id,
        alternate_selected_solution_plan_id=counterfactual.after_selected_plan_id,
        generic_selected_solution_plan_id=counterfactual.generic_selected_plan_id,
        changed_gate_ids=list(counterfactual.changed_gate_ids),
        record_hash=counterfactual.record_hash,
        payload=payload,
    )


__all__ = [
    "EvaluationPersistenceMetadata",
    "build_counterfactual_record",
    "build_evaluation_graph_write",
    "build_evaluation_pipeline_version",
    "ensure_evaluation_pipeline_version",
]
