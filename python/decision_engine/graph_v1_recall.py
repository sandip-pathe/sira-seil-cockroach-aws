"""Seller-neutral recall, identity deduplication, and evidence assessment."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from domain import content_hash
from domain.enums import PackAuthority
from domain.errors import DomainValidationError

from .bounds import evidence_age_bounds
from .graph_v1_models import (
    DecisionGraphInput,
    EvidenceAssessment,
    EvidencePolicy,
    EvidenceRecord,
    EvidenceState,
    FactValue,
    IdentityMerge,
    IdentityRecord,
    ProductFact,
    RawCandidateRecord,
    RecallResult,
)


def _alias_map(decision_input: DecisionGraphInput) -> dict[str, str]:
    return dict(decision_input.identity_normalization.aliases)


def _canonical(value: str, aliases: dict[str, str]) -> str:
    current = value.casefold().strip()
    visited: set[str] = set()
    while current in aliases:
        if current in visited:
            raise ValueError("identity normalization aliases contain a cycle")
        visited.add(current)
        current = aliases[current]
    return current


def _identity_key(record: RawCandidateRecord, aliases: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        _canonical(record.seller_id, aliases),
        _canonical(record.product_id, aliases),
        _canonical(record.edition, aliases),
        _canonical(record.region, aliases),
    )


def _canonical_id(key: tuple[str, str, str, str]) -> str:
    return f"canonical_{content_hash(key).split(':', maxsplit=1)[1][:20]}"


def _authority_floor(records: Iterable[RawCandidateRecord]) -> PackAuthority:
    authority_rank = {
        PackAuthority.SELLER_SEALED: 0,
        PackAuthority.PLATFORM_COMPILED: 1,
        PackAuthority.EXTERNAL_UNSEALED: 2,
    }
    return max((record.authority for record in records), key=authority_rank.__getitem__)


def _merge_facts(records: tuple[RawCandidateRecord, ...]) -> tuple[ProductFact, ...]:
    unique: dict[tuple[str, str], set[str]] = {}
    values: dict[tuple[str, str], FactValue] = {}
    for record in records:
        for fact in record.facts:
            value_hash = content_hash(fact.value)
            key = (fact.field, value_hash)
            values[key] = fact.value
            unique.setdefault(key, set()).update(fact.evidence_ids)
    return tuple(
        ProductFact(field, values[(field, value_hash)], tuple(sorted(evidence_ids)))
        for (field, value_hash), evidence_ids in sorted(unique.items())
    )


def recall_and_deduplicate(decision_input: DecisionGraphInput) -> RecallResult:
    """Resolve aliases and collapse duplicate editions, sellers, regions, and offers.

    Conflicting duplicate values are retained as separate raw facts so the
    evidence/gate stage reports a conflict.  A duplicate can therefore never
    improve coverage or silently replace an inconvenient value.
    """

    aliases = _alias_map(decision_input)
    grouped: dict[tuple[str, str, str, str], list[RawCandidateRecord]] = defaultdict(list)
    for record in sorted(decision_input.candidates, key=lambda item: item.record_id):
        grouped[_identity_key(record, aliases)].append(record)

    identities: list[IdentityRecord] = []
    merges: list[IdentityMerge] = []
    representatives: list[RawCandidateRecord] = []
    for key, group_items in sorted(grouped.items()):
        group = tuple(sorted(group_items, key=lambda item: item.record_id))
        canonical_id = _canonical_id(key)
        offer_ids = tuple(sorted({_canonical(item.offer_id, aliases) for item in group}))
        pack_ids = tuple(sorted({item.pack_id for item in group}))
        record_ids = tuple(item.record_id for item in group)
        identities.append(
            IdentityRecord(
                canonical_id=canonical_id,
                seller_id=key[0],
                product_id=key[1],
                edition=key[2],
                region=key[3],
                record_ids=record_ids,
                pack_ids=pack_ids,
                offer_ids=offer_ids,
            )
        )
        first = group[0]
        anchor = min(group, key=lambda item: (-item.pack_version, item.record_id))
        representatives.append(
            RawCandidateRecord(
                record_id=canonical_id,
                pack_id=anchor.pack_id,
                pack_version=anchor.pack_version,
                seller_id=key[0],
                product_id=key[1],
                edition=key[2],
                region=key[3],
                offer_id=_canonical(anchor.offer_id, aliases),
                authority=_authority_floor(group),
                available=all(item.available for item in group),
                facts=_merge_facts(group),
                seller_gate_ids=tuple(
                    sorted({gate_id for item in group for gate_id in item.seller_gate_ids})
                ),
                aliases=tuple(sorted({alias for item in group for alias in item.aliases})),
            )
        )
        for duplicate in group[1:]:
            reasons: list[str] = ["CANONICAL_IDENTITY_MATCH"]
            if duplicate.offer_id != first.offer_id:
                reasons.append("OFFER_ALIAS")
            if duplicate.edition != first.edition:
                reasons.append("EDITION_ALIAS")
            merges.append(IdentityMerge(canonical_id, duplicate.record_id, tuple(sorted(reasons))))

    return RecallResult(
        identities=tuple(identities),
        merges=tuple(sorted(merges, key=lambda item: (item.canonical_id, item.merged_record_id))),
        representatives=tuple(sorted(representatives, key=lambda item: item.record_id)),
        raw_record_count=len(decision_input.candidates),
    )


def _scope_matches(required_scope: str, actual_scope: str) -> bool:
    required = required_scope.casefold().strip()
    actual = actual_scope.casefold().strip()
    return required == "*" or required == actual


def _assessment(
    *,
    record: EvidenceRecord,
    policy: EvidencePolicy,
    field: str,
    decision_input: DecisionGraphInput,
) -> EvidenceAssessment:
    source_allowed = record.source_class in policy.allowed_source_classes
    method_allowed = record.verification_method in policy.allowed_verification_methods
    scope_match = _scope_matches(policy.required_scope, record.verification_scope)
    reasons: list[str] = []
    if not source_allowed:
        reasons.append("SOURCE_CLASS_NOT_ALLOWED")
    if not method_allowed:
        reasons.append("VERIFICATION_METHOD_NOT_ALLOWED")
    if not scope_match:
        reasons.append("VERIFICATION_SCOPE_MISMATCH")
    if not record.reconstructable:
        reasons.append("NOT_RECONSTRUCTABLE")
    if record.disputed:
        reasons.append("DISPUTED")
    if record.revoked:
        reasons.append("REVOKED")

    age_bounds = None
    freshness_current: bool | None = None
    if record.observed_at_lower is None or record.observed_at_upper is None:
        reasons.append("BOUND_UNAVAILABLE:EVIDENCE_TIME")
    else:
        age_bounds = evidence_age_bounds(
            evaluated_at=decision_input.evaluated_at,
            observed_at_lower=record.observed_at_lower,
            observed_at_upper=record.observed_at_upper,
            sla_seconds=policy.freshness_sla_seconds,
        )
        freshness_current = age_bounds.upper.fraction <= 1
        if not freshness_current:
            reasons.append("STALE")

    if record.disputed or record.revoked:
        state = EvidenceState.CONFLICT
    elif freshness_current is False:
        state = EvidenceState.STALE
    elif (
        not source_allowed
        or not method_allowed
        or not scope_match
        or not record.reconstructable
        or freshness_current is None
    ):
        state = EvidenceState.UNKNOWN
    else:
        state = EvidenceState.ACCEPTABLE
    return EvidenceAssessment(
        evidence_id=record.evidence_id,
        record_id=record.record_id,
        field=field,
        source_allowed=source_allowed,
        method_allowed=method_allowed,
        scope_match=scope_match,
        reconstructable=record.reconstructable,
        freshness_current=freshness_current,
        disputed=record.disputed,
        revoked=record.revoked,
        state=state,
        reasons=tuple(sorted(reasons)),
        age_bounds=age_bounds,
    )


def assess_evidence(
    decision_input: DecisionGraphInput, recall: RecallResult
) -> tuple[EvidenceAssessment, ...]:
    """Assess every decision-material evidence/field pair exactly once."""

    evidence_by_id = {item.evidence_id: item for item in decision_input.evidence}
    policies = {item.field: item for item in decision_input.evidence_policies}
    pairs: set[tuple[str, str]] = set()
    for candidate in recall.representatives:
        for fact in candidate.facts:
            pairs.update((evidence_id, fact.field) for evidence_id in fact.evidence_ids)
    for action in decision_input.current_actions:
        for fact in action.facts:
            pairs.update((evidence_id, fact.field) for evidence_id in fact.evidence_ids)
    criterion_fields = {item.criterion_id: item.field for item in decision_input.preferences}
    for observation in decision_input.outcome_values:
        field = criterion_fields.get(observation.criterion_id)
        if field is None:
            continue
        pairs.update((evidence_id, field) for evidence_id in observation.evidence_ids)

    assessments: list[EvidenceAssessment] = []
    for evidence_id, field in sorted(pairs):
        record = evidence_by_id.get(evidence_id)
        policy = policies.get(field)
        if policy is None:
            raise DomainValidationError(
                f"missing evidence policy for decision-material field {field}"
            )
        if record is None:
            assessments.append(
                EvidenceAssessment(
                    evidence_id=evidence_id,
                    record_id=f"missing_record_{evidence_id}",
                    field=field,
                    source_allowed=False,
                    method_allowed=False,
                    scope_match=False,
                    reconstructable=False,
                    freshness_current=None,
                    disputed=False,
                    revoked=False,
                    state=EvidenceState.UNKNOWN,
                    reasons=("BOUND_UNAVAILABLE:EVIDENCE_TIME", "MISSING_EVIDENCE_RECORD"),
                    age_bounds=None,
                )
            )
            continue
        assessments.append(
            _assessment(record=record, policy=policy, field=field, decision_input=decision_input)
        )
    return tuple(assessments)
