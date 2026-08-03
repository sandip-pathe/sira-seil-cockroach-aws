"""SQLAlchemy models for the first complete procurement vertical.

PostgreSQL is the canonical store. JSON columns hold immutable, schema-versioned
snapshots while decision-critical identifiers and lifecycle states stay typed and
queryable. Provider credentials intentionally have no column in this model.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

JSON_DOCUMENT = JSON().with_variant(JSONB(none_as_null=True), "postgresql")


class Base(DeclarativeBase):
    """Declarative metadata root."""


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TenantOwned:
    @declared_attr.directive
    def organization_id(cls) -> Mapped[str]:
        return mapped_column(
            String(64),
            ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        )


class Organization(Base, Timestamped):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class PurchaseRequest(Base, TenantOwned, Timestamped):
    __tablename__ = "purchase_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    intent: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    visibility: Mapped[str] = mapped_column(String(24), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    request_hash: Mapped[str] = mapped_column(String(80), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "visibility IN ('PRIVATE','SELECTIVE','OPEN_RFP')",
            name="ck_purchase_request_visibility",
        ),
        UniqueConstraint("organization_id", "request_hash", name="uq_purchase_request_hash"),
    )


class PurchaseBriefVersion(Base, TenantOwned, Timestamped):
    __tablename__ = "purchase_brief_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    purchase_request_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_requests.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    supersedes_id: Mapped[str | None] = mapped_column(
        ForeignKey("purchase_brief_versions.id", ondelete="RESTRICT"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "purchase_request_id", "version", name="uq_purchase_brief_version"
        ),
    )


class RequirementBriefVersion(Base, TenantOwned, Timestamped):
    __tablename__ = "requirement_brief_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    purchase_request_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_requests.id", ondelete="RESTRICT"), nullable=False
    )
    purchase_brief_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_brief_versions.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "purchase_request_id",
            "version",
            name="uq_requirement_brief_version",
        ),
        UniqueConstraint(
            "organization_id",
            "id",
            "version",
            "content_hash",
            name="uq_requirement_brief_exact_binding",
        ),
    )


class DecisionSourceSnapshot(Base, TenantOwned, Timestamped):
    """Immutable, private source bundle accepted for deterministic compilation."""

    __tablename__ = "decision_source_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    purchase_request_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_requests.id", ondelete="RESTRICT"), nullable=False
    )
    purchase_brief_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_brief_versions.id", ondelete="RESTRICT"), nullable=False
    )
    stack_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("stack_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    accepted_by_actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_decision_source_snapshot_version"),
        CheckConstraint(
            "source_kind IN ('DEVELOPMENT_FIXTURE','PROVIDER_COMPILED','MANUAL_VERIFIED')",
            name="ck_decision_source_snapshot_kind",
        ),
        UniqueConstraint(
            "organization_id",
            "purchase_request_id",
            "version",
            name="uq_decision_source_snapshot_version",
        ),
        UniqueConstraint(
            "organization_id",
            "purchase_request_id",
            "content_hash",
            name="uq_decision_source_snapshot_hash",
        ),
    )


class DecisionRecord(Base, TenantOwned, Timestamped):
    __tablename__ = "decision_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    purchase_request_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_requests.id", ondelete="RESTRICT"), nullable=False
    )
    purchase_brief_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_brief_versions.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_id: Mapped[str | None] = mapped_column(
        ForeignKey("decision_records.id", ondelete="RESTRICT"), nullable=True
    )
    decision_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    selected_solution_plan_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "decision_hash", name="uq_decision_hash"),
        UniqueConstraint(
            "organization_id",
            "purchase_request_id",
            "version",
            name="uq_decision_record_version",
        ),
        CheckConstraint("version >= 1", name="ck_decision_record_version_positive"),
    )


class DecisionSimulation(Base, TenantOwned, Timestamped):
    __tablename__ = "decision_simulations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    decision_id: Mapped[str] = mapped_column(
        ForeignKey("decision_records.id", ondelete="RESTRICT"), nullable=False
    )
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    result_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    result_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    authoritative: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "decision_id", "actor_id", "input_hash", name="uq_simulation_input"
        ),
    )


class EvaluationPipelineVersion(Base, TenantOwned, Timestamped):
    """Immutable executable policy/pipeline bundle used by Decision Graph runs."""

    __tablename__ = "evaluation_pipeline_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    pipeline_version: Mapped[str] = mapped_column(String(80), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(80), nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    normalization_version: Mapped[str] = mapped_column(String(80), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    risk_rule_set_version: Mapped[str] = mapped_column(String(80), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "content_hash", name="uq_evaluation_pipeline_content_hash"
        ),
        Index(
            "ix_evaluation_pipeline_version_lookup",
            "organization_id",
            "pipeline_version",
        ),
    )


class EvaluationRun(Base, TenantOwned, Timestamped):
    """A frozen, replayable Decision Graph evaluation.

    ``evaluation_payload_hash`` covers the ordered evaluation payload only. It
    deliberately excludes this row's ID/timestamps and any counterfactual or
    final Decision hash, preventing a circular hash dependency.
    """

    __tablename__ = "evaluation_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    purchase_request_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_requests.id", ondelete="RESTRICT"), nullable=False
    )
    purchase_brief_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_brief_versions.id", ondelete="RESTRICT"), nullable=False
    )
    decision_id: Mapped[str | None] = mapped_column(
        ForeignKey("decision_records.id", ondelete="RESTRICT"), nullable=True
    )
    evaluation_pipeline_version_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_pipeline_versions.id", ondelete="RESTRICT"), nullable=False
    )
    run_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_version: Mapped[str] = mapped_column(String(80), nullable=False)
    company_profile_version: Mapped[str] = mapped_column(String(80), nullable=False)
    stackfile_version: Mapped[str] = mapped_column(String(80), nullable=False)
    registry_version: Mapped[str] = mapped_column(String(80), nullable=False)
    candidate_set_version: Mapped[str] = mapped_column(String(80), nullable=False)
    pack_set_version: Mapped[str] = mapped_column(String(80), nullable=False)
    offer_set_version: Mapped[str] = mapped_column(String(80), nullable=False)
    quote_set_version: Mapped[str] = mapped_column(String(80), nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    normalization_version: Mapped[str] = mapped_column(String(80), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    fx_version: Mapped[str] = mapped_column(String(80), nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(80), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(80), nullable=False)
    input_payload_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    evaluation_payload_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    evaluation_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    selected_solution_plan_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rank_stability: Mapped[str] = mapped_column(String(24), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "evaluation_payload_hash", name="uq_evaluation_payload_hash"
        ),
        UniqueConstraint(
            "organization_id",
            "purchase_request_id",
            "input_payload_hash",
            name="uq_evaluation_run_input",
        ),
        CheckConstraint(
            "run_kind IN ('BASE','GENERIC','COUNTERFACTUAL','REPLAY')",
            name="ck_evaluation_run_kind",
        ),
        CheckConstraint(
            "rank_stability IN ('STABLE','UNSTABLE','UNDETERMINED')",
            name="ck_evaluation_rank_stability",
        ),
        Index("ix_evaluation_runs_decision_id", "decision_id"),
        Index("ix_evaluation_runs_request_evaluated", "purchase_request_id", "evaluated_at"),
    )


class DiscoveryRun(Base, TenantOwned, Timestamped):
    __tablename__ = "discovery_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    evaluation_run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    candidate_set_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    output_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    raw_record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_product_count: Mapped[int] = mapped_column(Integer, nullable=False)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_solution_plan_count: Mapped[int] = mapped_column(Integer, nullable=False)
    excluded_count: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "evaluation_run_id", name="uq_discovery_evaluation"),
        CheckConstraint(
            "raw_record_count >= 0 AND canonical_product_count >= 0 "
            "AND duplicate_count >= 0 AND generated_solution_plan_count >= 0 "
            "AND excluded_count >= 0",
            name="ck_discovery_counts_nonnegative",
        ),
    )


class CandidateSetMember(Base, TenantOwned, Timestamped):
    __tablename__ = "candidate_set_members"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    discovery_run_id: Mapped[str] = mapped_column(
        ForeignKey("discovery_runs.id", ondelete="RESTRICT"), nullable=False
    )
    canonical_identity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(128), nullable=False)
    member_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    disposition: Mapped[str] = mapped_column(String(24), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    pack_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pack_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    offer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    offer_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_action_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    member_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "discovery_run_id",
            "source_record_id",
            name="uq_candidate_set_source",
        ),
        UniqueConstraint(
            "organization_id",
            "discovery_run_id",
            "ordinal",
            name="uq_candidate_set_ordinal",
        ),
        CheckConstraint(
            "member_kind IN ('PACK','CURRENT_STACK','CONTRACT_ACTION','NO_ACTION')",
            name="ck_candidate_set_member_kind",
        ),
        CheckConstraint(
            "disposition IN ('INCLUDED','EXCLUDED','DEDUPLICATED')",
            name="ck_candidate_set_disposition",
        ),
        CheckConstraint("ordinal >= 0", name="ck_candidate_set_ordinal_nonnegative"),
        CheckConstraint(
            "pack_version IS NULL OR pack_version >= 1",
            name="ck_candidate_set_pack_version_positive",
        ),
        CheckConstraint(
            "offer_version IS NULL OR offer_version >= 1",
            name="ck_candidate_set_offer_version_positive",
        ),
        Index("ix_candidate_set_members_identity", "discovery_run_id", "canonical_identity_id"),
    )


class IdentityMerge(Base, TenantOwned, Timestamped):
    __tablename__ = "identity_merges"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    discovery_run_id: Mapped[str] = mapped_column(
        ForeignKey("discovery_runs.id", ondelete="RESTRICT"), nullable=False
    )
    canonical_identity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    merged_record_id: Mapped[str] = mapped_column(String(128), nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False)
    merge_hash: Mapped[str] = mapped_column(String(80), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "discovery_run_id",
            "merged_record_id",
            name="uq_identity_merge_record",
        ),
        UniqueConstraint(
            "organization_id", "discovery_run_id", "merge_hash", name="uq_identity_merge_hash"
        ),
        Index("ix_identity_merges_canonical", "discovery_run_id", "canonical_identity_id"),
    )


class EvaluationSolutionPlan(Base, TenantOwned, Timestamped):
    """Run-scoped Solution Plan root for normalized graph child records."""

    __tablename__ = "evaluation_solution_plans"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    evaluation_run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    solution_plan_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    component_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    plan_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    construction_lifecycle: Mapped[str] = mapped_column(String(32), nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False)
    candidate_status: Mapped[str] = mapped_column(String(32), nullable=False)
    primary_reason_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rank_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ordering_frontier_member: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolution_frontier_member: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quote_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quote_policy_reason: Mapped[str] = mapped_column(String(100), nullable=False)
    permitted_resolution: Mapped[str | None] = mapped_column(String(200), nullable=True)
    autonomous_execution_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    stable_action_ids: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "evaluation_run_id",
            "solution_plan_id",
            name="uq_evaluation_solution_plan",
        ),
        UniqueConstraint(
            "organization_id", "evaluation_run_id", "plan_hash", name="uq_evaluation_plan_hash"
        ),
        CheckConstraint(
            "action IN ('REUSE_EXISTING','CONFIGURE_EXISTING','NO_ACTION','BUY','RENEW',"
            "'RESIZE','REPLACE','CONSOLIDATE','CANCEL')",
            name="ck_evaluation_plan_action",
        ),
        CheckConstraint(
            "construction_lifecycle IN ('CANDIDATE','RESOLUTION_PENDING','EXECUTABLE','BLOCKED')",
            name="ck_evaluation_plan_construction_lifecycle",
        ),
        CheckConstraint(
            "lifecycle IN ('CANDIDATE','RESOLUTION_PENDING','EXECUTABLE','BLOCKED')",
            name="ck_evaluation_plan_lifecycle",
        ),
        CheckConstraint(
            "candidate_status IN ('ELIGIBLE','ELIGIBLE_WITH_EXCEPTION','CONDITIONAL',"
            "'SIRA_INELIGIBLE','SEIL_PASS','UNAVAILABLE','STALE_EVIDENCE',"
            "'INSUFFICIENT_EVIDENCE','CONFLICTING_EVIDENCE','AUTHORITY_REQUIRED',"
            "'ADVISORY_ONLY')",
            name="ck_evaluation_plan_candidate_status",
        ),
        CheckConstraint(
            "rank_position IS NULL OR rank_position >= 1",
            name="ck_evaluation_plan_rank_positive",
        ),
        Index("ix_evaluation_solution_plans_rank", "evaluation_run_id", "rank_position"),
    )


class SolutionPlanComponent(Base, TenantOwned, Timestamped):
    __tablename__ = "solution_plan_components"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    evaluation_run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    solution_plan_record_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_solution_plans.id", ondelete="RESTRICT"), nullable=False
    )
    component_id: Mapped[str] = mapped_column(String(100), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    source_record_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    component_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "solution_plan_record_id",
            "component_id",
            name="uq_solution_plan_component",
        ),
        UniqueConstraint(
            "organization_id",
            "solution_plan_record_id",
            "ordinal",
            name="uq_solution_plan_component_ordinal",
        ),
        CheckConstraint("ordinal >= 0", name="ck_solution_plan_component_ordinal_nonnegative"),
        CheckConstraint(
            "action IN ('REUSE_EXISTING','CONFIGURE_EXISTING','NO_ACTION','BUY','RENEW',"
            "'RESIZE','REPLACE','CONSOLIDATE','CANCEL')",
            name="ck_solution_plan_component_action",
        ),
        CheckConstraint(
            "source_type IN ('PACK','CURRENT_STACK','CONTRACT_ACTION','NO_ACTION')",
            name="ck_solution_plan_component_source_type",
        ),
        Index("ix_solution_plan_components_evaluation", "evaluation_run_id"),
    )


class DecisionGateResult(Base, TenantOwned, Timestamped):
    __tablename__ = "decision_gate_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    evaluation_run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    solution_plan_record_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_solution_plans.id", ondelete="RESTRICT"), nullable=False
    )
    gate_id: Mapped[str] = mapped_column(String(100), nullable=False)
    truth: Mapped[str] = mapped_column(String(16), nullable=False)
    derived_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False)
    evaluated_predicates: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False)
    source_fact_ids: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False)
    permitted_resolution: Mapped[str | None] = mapped_column(String(200), nullable=True)
    overridable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    result_hash: Mapped[str] = mapped_column(String(80), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "solution_plan_record_id",
            "gate_id",
            name="uq_decision_gate_result",
        ),
        CheckConstraint(
            "truth IN ('TRUE','FALSE','UNKNOWN','CONFLICT')", name="ck_decision_gate_truth"
        ),
        CheckConstraint(
            "derived_status IS NULL OR derived_status IN ('ELIGIBLE','ELIGIBLE_WITH_EXCEPTION',"
            "'CONDITIONAL','SIRA_INELIGIBLE','SEIL_PASS','UNAVAILABLE','STALE_EVIDENCE',"
            "'INSUFFICIENT_EVIDENCE','CONFLICTING_EVIDENCE','AUTHORITY_REQUIRED',"
            "'ADVISORY_ONLY')",
            name="ck_decision_gate_derived_status",
        ),
        Index("ix_decision_gate_results_evaluation", "evaluation_run_id", "gate_id"),
    )


class EvidenceAssessmentRecord(Base, TenantOwned, Timestamped):
    __tablename__ = "evidence_assessments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    evaluation_run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    evidence_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(128), nullable=False)
    field: Mapped[str] = mapped_column(String(160), nullable=False)
    supported_criterion_ids: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False)
    source_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    method_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    scope_match: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reconstructable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    freshness_current: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    disputed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    age_lower_numerator: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    age_lower_denominator: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    age_upper_numerator: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    age_upper_denominator: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reason_codes: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False)
    assessment_hash: Mapped[str] = mapped_column(String(80), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "evaluation_run_id",
            "evidence_id",
            "field",
            name="uq_evidence_assessment",
        ),
        CheckConstraint(
            "state IN ('ACCEPTABLE','UNKNOWN','STALE','CONFLICT')",
            name="ck_evidence_assessment_state",
        ),
        CheckConstraint(
            "age_lower_denominator IS NULL OR age_lower_denominator > 0",
            name="ck_evidence_age_lower_denominator_positive",
        ),
        CheckConstraint(
            "age_upper_denominator IS NULL OR age_upper_denominator > 0",
            name="ck_evidence_age_upper_denominator_positive",
        ),
        CheckConstraint(
            "(age_lower_numerator IS NULL AND age_lower_denominator IS NULL "
            "AND age_upper_numerator IS NULL AND age_upper_denominator IS NULL) OR "
            "(age_lower_numerator IS NOT NULL AND age_lower_denominator IS NOT NULL "
            "AND age_upper_numerator IS NOT NULL AND age_upper_denominator IS NOT NULL)",
            name="ck_evidence_age_bounds_complete",
        ),
        Index("ix_evidence_assessments_evaluation_field", "evaluation_run_id", "field"),
    )


class ScoreComponentRecord(Base, TenantOwned, Timestamped):
    __tablename__ = "score_components"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    evaluation_run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    solution_plan_record_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_solution_plans.id", ondelete="RESTRICT"), nullable=False
    )
    criterion_id: Mapped[str] = mapped_column(String(100), nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False)
    coverage_weight: Mapped[int] = mapped_column(Integer, nullable=False)
    conservative_satisfaction_numerator: Mapped[int] = mapped_column(BigInteger, nullable=False)
    conservative_satisfaction_denominator: Mapped[int] = mapped_column(BigInteger, nullable=False)
    optimistic_satisfaction_numerator: Mapped[int] = mapped_column(BigInteger, nullable=False)
    optimistic_satisfaction_denominator: Mapped[int] = mapped_column(BigInteger, nullable=False)
    contribution_conservative_numerator: Mapped[int] = mapped_column(BigInteger, nullable=False)
    contribution_conservative_denominator: Mapped[int] = mapped_column(BigInteger, nullable=False)
    contribution_optimistic_numerator: Mapped[int] = mapped_column(BigInteger, nullable=False)
    contribution_optimistic_denominator: Mapped[int] = mapped_column(BigInteger, nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False)
    evidence_state: Mapped[str] = mapped_column(String(24), nullable=False)
    prior_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    input_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    component_hash: Mapped[str] = mapped_column(String(80), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "solution_plan_record_id",
            "criterion_id",
            name="uq_score_component_criterion",
        ),
        CheckConstraint("weight BETWEEN 1 AND 5", name="ck_score_component_weight"),
        CheckConstraint(
            "coverage_weight BETWEEN 1 AND 5", name="ck_score_component_coverage_weight"
        ),
        CheckConstraint(
            "conservative_satisfaction_denominator > 0 "
            "AND optimistic_satisfaction_denominator > 0 "
            "AND contribution_conservative_denominator > 0 "
            "AND contribution_optimistic_denominator > 0",
            name="ck_score_component_denominators_positive",
        ),
        CheckConstraint(
            "conservative_satisfaction_numerator BETWEEN 0 "
            "AND conservative_satisfaction_denominator "
            "AND optimistic_satisfaction_numerator BETWEEN 0 "
            "AND optimistic_satisfaction_denominator",
            name="ck_score_component_satisfaction_unit_interval",
        ),
        CheckConstraint(
            "evidence_state IN ('ACCEPTABLE','UNKNOWN','STALE','CONFLICT')",
            name="ck_score_component_evidence_state",
        ),
        Index("ix_score_components_evaluation", "evaluation_run_id", "criterion_id"),
    )


class ScoreBound(Base, TenantOwned, Timestamped):
    __tablename__ = "score_bounds"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    evaluation_run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    solution_plan_record_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_solution_plans.id", ondelete="RESTRICT"), nullable=False
    )
    dimension: Mapped[str] = mapped_column(String(48), nullable=False)
    bound_status: Mapped[str] = mapped_column(String(24), nullable=False)
    value_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    lower_numerator: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    lower_denominator: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    base_numerator: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    base_denominator: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    upper_numerator: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    upper_denominator: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    unavailable_reason: Mapped[str | None] = mapped_column(String(160), nullable=True)
    calculation_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    bound_hash: Mapped[str] = mapped_column(String(80), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "solution_plan_record_id",
            "dimension",
            name="uq_score_bound_dimension",
        ),
        CheckConstraint(
            "dimension IN ('PREFERENCE','STACK_RISK','TCO','DECISION_MATERIAL_COVERAGE',"
            "'EVIDENCE_AGE','HARD_COVERAGE','UNIVERSE_COVERAGE')",
            name="ck_score_bound_dimension",
        ),
        CheckConstraint(
            "bound_status IN ('AVAILABLE','BOUND_UNAVAILABLE')",
            name="ck_score_bound_status",
        ),
        CheckConstraint(
            "value_kind IN ('RATIO','RISK_ORDINAL','MONEY','COUNT')",
            name="ck_score_bound_value_kind",
        ),
        CheckConstraint(
            "(bound_status = 'AVAILABLE' AND lower_numerator IS NOT NULL "
            "AND lower_denominator IS NOT NULL AND base_numerator IS NOT NULL "
            "AND base_denominator IS NOT NULL AND upper_numerator IS NOT NULL "
            "AND upper_denominator IS NOT NULL AND unavailable_reason IS NULL) OR "
            "(bound_status = 'BOUND_UNAVAILABLE' AND unavailable_reason IS NOT NULL)",
            name="ck_score_bound_availability",
        ),
        CheckConstraint(
            "(lower_denominator IS NULL OR lower_denominator > 0) "
            "AND (base_denominator IS NULL OR base_denominator > 0) "
            "AND (upper_denominator IS NULL OR upper_denominator > 0)",
            name="ck_score_bound_denominators_positive",
        ),
        CheckConstraint(
            "currency IS NULL OR currency = upper(currency)", name="ck_score_bound_currency_upper"
        ),
        CheckConstraint(
            "(value_kind = 'MONEY' AND currency IS NOT NULL) "
            "OR (value_kind <> 'MONEY' AND currency IS NULL)",
            name="ck_score_bound_currency_kind",
        ),
        CheckConstraint(
            "value_kind <> 'RISK_ORDINAL' OR bound_status = 'BOUND_UNAVAILABLE' OR "
            "(lower_denominator = 1 AND base_denominator = 1 AND upper_denominator = 1 "
            "AND lower_numerator BETWEEN 0 AND 3 AND base_numerator BETWEEN 0 AND 3 "
            "AND upper_numerator BETWEEN 0 AND 3)",
            name="ck_score_bound_risk_ordinal",
        ),
        Index("ix_score_bounds_evaluation_dimension", "evaluation_run_id", "dimension"),
    )


class RobustnessFrontier(Base, TenantOwned, Timestamped):
    __tablename__ = "robustness_frontiers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    evaluation_run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    solution_plan_record_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_solution_plans.id", ondelete="RESTRICT"), nullable=False
    )
    frontier_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    decision_rank_stability: Mapped[str] = mapped_column(String(24), nullable=False)
    member: Mapped[bool] = mapped_column(Boolean, nullable=False)
    can_beat_selected: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    permitted_resolution: Mapped[str | None] = mapped_column(String(200), nullable=True)
    frontier_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    frontier_hash: Mapped[str] = mapped_column(String(80), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "solution_plan_record_id",
            "frontier_kind",
            name="uq_robustness_frontier_kind",
        ),
        CheckConstraint(
            "frontier_kind IN ('ORDERING','RESOLUTION','BOUND_UNAVAILABLE')",
            name="ck_robustness_frontier_kind",
        ),
        CheckConstraint(
            "decision_rank_stability IN ('STABLE','UNSTABLE','UNDETERMINED')",
            name="ck_robustness_rank_stability",
        ),
        Index("ix_robustness_frontiers_evaluation", "evaluation_run_id", "frontier_kind"),
    )


class CounterfactualRecordModel(Base, TenantOwned, Timestamped):
    """Canonical counterfactual edge keyed exclusively by evaluation hashes."""

    __tablename__ = "counterfactual_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    decision_id: Mapped[str | None] = mapped_column(
        ForeignKey("decision_records.id", ondelete="RESTRICT"), nullable=True
    )
    outcome: Mapped[str] = mapped_column(String(48), nullable=False)
    removed_fact_ids: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False)
    alternative_fact_id_sets: Mapped[list[list[str]]] = mapped_column(JSON_DOCUMENT, nullable=False)
    tested_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    base_evaluation_payload_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    alternate_evaluation_payload_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    generic_evaluation_payload_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    base_selected_solution_plan_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    alternate_selected_solution_plan_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    generic_selected_solution_plan_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    changed_gate_ids: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False)
    record_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "base_evaluation_payload_hash"],
            ["evaluation_runs.organization_id", "evaluation_runs.evaluation_payload_hash"],
            name="fk_counterfactual_base_evaluation_hash",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "alternate_evaluation_payload_hash"],
            ["evaluation_runs.organization_id", "evaluation_runs.evaluation_payload_hash"],
            name="fk_counterfactual_alternate_evaluation_hash",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "generic_evaluation_payload_hash"],
            ["evaluation_runs.organization_id", "evaluation_runs.evaluation_payload_hash"],
            name="fk_counterfactual_generic_evaluation_hash",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "record_hash", name="uq_counterfactual_record_hash"),
        CheckConstraint(
            "outcome IN ('WINNER_CHANGED','NO_SMALL_COUNTERFACTUAL_FOUND')",
            name="ck_counterfactual_outcome",
        ),
        CheckConstraint("tested_limit BETWEEN 1 AND 3", name="ck_counterfactual_tested_limit"),
        CheckConstraint(
            "(outcome = 'WINNER_CHANGED' AND alternate_evaluation_payload_hash IS NOT NULL) "
            "OR (outcome = 'NO_SMALL_COUNTERFACTUAL_FOUND' "
            "AND alternate_evaluation_payload_hash IS NULL)",
            name="ck_counterfactual_alternate_hash",
        ),
        CheckConstraint(
            "alternate_evaluation_payload_hash IS NULL "
            "OR alternate_evaluation_payload_hash <> base_evaluation_payload_hash",
            name="ck_counterfactual_distinct_alternate_hash",
        ),
        Index("ix_counterfactual_records_decision", "decision_id"),
        Index("ix_counterfactual_records_base_hash", "base_evaluation_payload_hash"),
    )


class CalibrationRun(Base, TenantOwned, Timestamped):
    __tablename__ = "calibration_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    purchase_request_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_requests.id", ondelete="RESTRICT"), nullable=False
    )
    purchase_brief_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_brief_versions.id", ondelete="RESTRICT"), nullable=False
    )
    result: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    proposed_purchase_brief_id: Mapped[str | None] = mapped_column(
        ForeignKey("purchase_brief_versions.id", ondelete="RESTRICT"), nullable=True
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CandidateFeedback(Base, TenantOwned, Timestamped):
    __tablename__ = "candidate_feedback"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    purchase_request_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_requests.id", ondelete="RESTRICT"), nullable=False
    )
    candidate_id: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    proposed_change: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "action IN ('SHORTLIST','PASS','REQUEST_OFFER','SAVE_FOR_LATER','NOT_ENOUGH_EVIDENCE')",
            name="ck_candidate_feedback_action",
        ),
    )


class Engagement(Base, TenantOwned, Timestamped):
    __tablename__ = "engagements"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    purchase_request_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_requests.id", ondelete="RESTRICT"), nullable=False
    )
    requirement_brief_id: Mapped[str] = mapped_column(String(64), nullable=False)
    requirement_brief_version: Mapped[int] = mapped_column(Integer, nullable=False)
    requirement_brief_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    candidate_id: Mapped[str] = mapped_column(String(100), nullable=False)
    seller_organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    expected_buyer_actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    expected_seller_actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    grant_scope: Mapped[str] = mapped_column(String(80), nullable=False)
    grant_status: Mapped[str] = mapped_column(String(24), nullable=False)
    grant_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    seller_visible_requirement_brief: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    buyer_consented: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    seller_consented: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    buyer_consent_actor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    seller_consent_actor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_exchange: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('NOT_STARTED','SELLER_REVIEWING','SELLER_PASSED','OFFER_AVAILABLE',"
            "'BUYER_CONSENT_PENDING','SELLER_CONSENT_PENDING','INTRODUCTION_READY','DECLINED','EXPIRED')",
            name="ck_engagement_status",
        ),
        CheckConstraint(
            "expected_buyer_actor_id <> expected_seller_actor_id",
            name="ck_engagement_distinct_participants",
        ),
        CheckConstraint(
            "organization_id <> seller_organization_id",
            name="ck_engagement_distinct_organizations",
        ),
        CheckConstraint(
            "grant_scope = 'SANITIZED_BRIEF_AND_CONTACT_CONSENT'",
            name="ck_engagement_grant_scope",
        ),
        CheckConstraint(
            "grant_status IN ('ACTIVE','REVOKED','EXPIRED')",
            name="ck_engagement_grant_status",
        ),
        CheckConstraint(
            "requirement_brief_version >= 1",
            name="ck_engagement_requirement_brief_version_positive",
        ),
        ForeignKeyConstraint(
            [
                "organization_id",
                "requirement_brief_id",
                "requirement_brief_version",
                "requirement_brief_hash",
            ],
            [
                "requirement_brief_versions.organization_id",
                "requirement_brief_versions.id",
                "requirement_brief_versions.version",
                "requirement_brief_versions.content_hash",
            ],
            name="fk_engagement_exact_requirement_brief",
            ondelete="RESTRICT",
        ),
        Index("ix_engagements_requirement_brief", "requirement_brief_id"),
        UniqueConstraint("organization_id", "grant_hash", name="uq_engagement_grant_hash"),
    )


class PurchaseIntent(Base, TenantOwned, Timestamped):
    __tablename__ = "purchase_intents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    decision_id: Mapped[str] = mapped_column(
        ForeignKey("decision_records.id", ondelete="RESTRICT"), nullable=False
    )
    decision_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    solution_plan_id: Mapped[str] = mapped_column(String(64), nullable=False)
    stack_patch_id: Mapped[str] = mapped_column(
        ForeignKey("stack_patches.id", ondelete="RESTRICT"), nullable=False
    )
    intent_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    merchant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    merchant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    merchant_url: Mapped[str] = mapped_column(Text, nullable=False)
    approved_merchant_chain_id: Mapped[str] = mapped_column(String(64), nullable=False)
    pack_id: Mapped[str] = mapped_column(String(100), nullable=False)
    pack_version: Mapped[int] = mapped_column(Integer, nullable=False)
    offer_id: Mapped[str] = mapped_column(String(100), nullable=False)
    offer_version: Mapped[int] = mapped_column(Integer, nullable=False)
    quote_id: Mapped[str] = mapped_column(String(100), nullable=False)
    quote_version: Mapped[int] = mapped_column(Integer, nullable=False)
    quote_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    expected_fulfillments: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    approval_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="NOT_REQUESTED"
    )
    payment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NOT_STARTED")
    fulfillment_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="NOT_STARTED"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        UniqueConstraint("organization_id", "intent_hash", name="uq_purchase_intent_hash"),
        UniqueConstraint(
            "organization_id",
            "decision_id",
            "solution_plan_id",
            "quote_id",
            "quote_version",
            name="uq_purchase_intent_business_lock",
        ),
        CheckConstraint("quote_version >= 1", name="ck_purchase_intent_quote_version_positive"),
        CheckConstraint("amount >= 0", name="ck_purchase_intent_amount_nonnegative"),
        CheckConstraint("currency = upper(currency)", name="ck_purchase_intent_currency_upper"),
        CheckConstraint(
            "approval_status IN ("
            "'NOT_REQUESTED','PENDING','APPROVED','REJECTED','REVOKED','EXPIRED','SUPERSEDED')",
            name="ck_purchase_intent_approval_status",
        ),
        CheckConstraint(
            "payment_status IN ("
            "'NOT_STARTED','SESSION_CREATED','CARDHOLDER_PENDING','CHECKOUT_PENDING',"
            "'MERCHANT_APPROVED','REPORTING','PRAVA_COMPLETED','DECLINED','EXPIRED','UNCERTAIN','FAILED')",
            name="ck_purchase_intent_payment_status",
        ),
        CheckConstraint(
            "fulfillment_status IN ('NOT_STARTED','PENDING','PARTIAL','VERIFIED',"
            "'FAILED_RETRYABLE','FAILED_FINAL','REVOKED')",
            name="ck_purchase_intent_fulfillment_status",
        ),
    )


class PurchaseReversal(Base, TenantOwned, Timestamped):
    """Refund/cancellation state bound to one exact paid Purchase Intent."""

    __tablename__ = "purchase_reversals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    purchase_intent_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_intents.id", ondelete="RESTRICT"), nullable=False
    )
    intent_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    refunded_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False, default=Decimal("0.00")
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    merchant_order_id: Mapped[str] = mapped_column(String(160), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    provider_adapter_id: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    reason_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    requested_by_actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    safe_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("kind IN ('CANCELLATION','REFUND')", name="ck_reversal_kind"),
        CheckConstraint(
            "status IN ('REQUESTED','PROVIDER_PENDING','PARTIALLY_REFUNDED','REFUNDED',"
            "'REJECTED','FAILED_RETRYABLE','COMPENSATION_REQUIRED','COMPENSATED','CANCELLED')",
            name="ck_reversal_status",
        ),
        CheckConstraint("requested_amount > 0", name="ck_reversal_requested_positive"),
        CheckConstraint("refunded_amount >= 0", name="ck_reversal_refunded_nonnegative"),
        CheckConstraint("refunded_amount <= requested_amount", name="ck_reversal_refunded_bounded"),
        CheckConstraint("currency = upper(currency)", name="ck_reversal_currency_upper"),
        UniqueConstraint(
            "organization_id",
            "purchase_intent_id",
            "reason_hash",
            name="uq_reversal_request",
        ),
        Index(
            "ix_reversal_intent_status",
            "organization_id",
            "purchase_intent_id",
            "status",
        ),
    )


class OutcomeCheckpoint(Base, TenantOwned, Timestamped):
    """Immutable measured outcome tied to the frozen decision and selected plan."""

    __tablename__ = "outcome_checkpoints"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    purchase_intent_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_intents.id", ondelete="RESTRICT"), nullable=False
    )
    decision_id: Mapped[str] = mapped_column(
        ForeignKey("decision_records.id", ondelete="RESTRICT"), nullable=False
    )
    decision_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    solution_plan_id: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_id: Mapped[str] = mapped_column(String(128), nullable=False)
    target_value: Mapped[Decimal] = mapped_column(Numeric(30, 6), nullable=False)
    target_operator: Mapped[str] = mapped_column(String(8), nullable=False)
    observed_value: Mapped[Decimal] = mapped_column(Numeric(30, 6), nullable=False)
    checkpoint_days: Mapped[int] = mapped_column(Integer, nullable=False)
    measurement_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    checkpoint_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    source_class: Mapped[str] = mapped_column(String(40), nullable=False)
    source_reference_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    recorded_by_actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    checkpoint_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    preference_proposal: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT, nullable=True)

    __table_args__ = (
        CheckConstraint("checkpoint_days BETWEEN 1 AND 365", name="ck_outcome_checkpoint_days"),
        CheckConstraint("target_operator IN ('gte','lte')", name="ck_outcome_target_operator"),
        CheckConstraint(
            "state IN ('MEASURING','ACHIEVED','NOT_ACHIEVED','INCONCLUSIVE')",
            name="ck_outcome_state",
        ),
        CheckConstraint(
            "source_class IN ('SYSTEM_OBSERVATION','HUMAN_ATTESTATION','PROVIDER_REPORT')",
            name="ck_outcome_source_class",
        ),
        UniqueConstraint("organization_id", "checkpoint_hash", name="uq_outcome_checkpoint_hash"),
        Index(
            "ix_outcome_intent_metric",
            "organization_id",
            "purchase_intent_id",
            "metric_id",
            "observed_at",
        ),
    )


class ActionRun(Base, TenantOwned, Timestamped):
    """Action-neutral execution run bound to an immutable Decision and plan."""

    __tablename__ = "action_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    decision_id: Mapped[str] = mapped_column(
        ForeignKey("decision_records.id", ondelete="RESTRICT"), nullable=False
    )
    solution_plan_record_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_solution_plans.id", ondelete="RESTRICT"), nullable=False
    )
    solution_plan_id: Mapped[str] = mapped_column(String(64), nullable=False)
    purchase_intent_id: Mapped[str | None] = mapped_column(
        ForeignKey("purchase_intents.id", ondelete="RESTRICT"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    current_checkpoint: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_successful_checkpoint: Mapped[str | None] = mapped_column(String(100), nullable=True)
    owner_role: Mapped[str] = mapped_column(String(80), nullable=False)
    blocking_task: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    recovery_action: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    retryable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    safe_to_leave: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    run_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    supersedes_id: Mapped[str | None] = mapped_column(
        ForeignKey("action_runs.id", ondelete="RESTRICT"), nullable=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "run_hash", name="uq_action_run_hash"),
        UniqueConstraint(
            "organization_id",
            "decision_id",
            "solution_plan_record_id",
            name="uq_action_run_decision_plan",
        ),
        CheckConstraint(
            "action IN ('REUSE_EXISTING','CONFIGURE_EXISTING','NO_ACTION','BUY','RENEW',"
            "'RESIZE','REPLACE','CONSOLIDATE','CANCEL')",
            name="ck_action_run_action",
        ),
        CheckConstraint(
            "status IN ('QUEUED','RUNNING','WAITING_FOR_HUMAN','RETRYABLE_ERROR',"
            "'UNCERTAIN','COMPLETED','FAILED_FINAL')",
            name="ck_action_run_status",
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at",
            name="ck_action_run_completion_order",
        ),
        CheckConstraint(
            "status NOT IN ('COMPLETED','FAILED_FINAL') OR completed_at IS NOT NULL",
            name="ck_action_run_terminal_completion",
        ),
        Index("ix_action_runs_decision_status", "decision_id", "status"),
    )


class ResultArtifact(Base, TenantOwned, Timestamped):
    __tablename__ = "result_artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    action_run_id: Mapped[str] = mapped_column(
        ForeignKey("action_runs.id", ondelete="RESTRICT"), nullable=False
    )
    artifact_type: Mapped[str] = mapped_column(String(40), nullable=False)
    verification_state: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    owner_role: Mapped[str] = mapped_column(String(80), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    safe_label: Mapped[str] = mapped_column(String(200), nullable=False)
    href: Mapped[str] = mapped_column(Text, nullable=False)
    stack_patch_id: Mapped[str | None] = mapped_column(
        ForeignKey("stack_patches.id", ondelete="RESTRICT"), nullable=True
    )
    receipt_id: Mapped[str | None] = mapped_column(
        ForeignKey("receipts.id", ondelete="RESTRICT"), nullable=True
    )
    artifact_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "action_run_id", "artifact_hash", name="uq_result_artifact_hash"
        ),
        CheckConstraint(
            "artifact_type IN ('DECISION_RECORD','CONFIGURATION_CHANGE','CONTRACT_CONFIRMATION',"
            "'CANCELLATION_CONFIRMATION','ORDER','ENTITLEMENT','MIGRATION_RECORD','STACK_PATCH',"
            "'OUTCOME_CHECKPOINT')",
            name="ck_result_artifact_type",
        ),
        CheckConstraint(
            "verification_state IN ('PENDING','VERIFIED','FAILED','REVOKED')",
            name="ck_result_artifact_verification_state",
        ),
        CheckConstraint(
            "verified_at IS NULL OR verified_at >= occurred_at",
            name="ck_result_artifact_verification_order",
        ),
        CheckConstraint(
            "verification_state <> 'VERIFIED' OR verified_at IS NOT NULL",
            name="ck_result_artifact_verified_timestamp",
        ),
        Index("ix_result_artifacts_action_type", "action_run_id", "artifact_type"),
    )


class ApprovalRequest(Base, TenantOwned, Timestamped):
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    purchase_intent_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_intents.id", ondelete="RESTRICT"), nullable=False
    )
    intent_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    required_roles: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False)
    approved_roles: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False, default=list)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "purchase_intent_id", "intent_hash", name="uq_approval_exact_intent"
        ),
        CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED','REVOKED','EXPIRED','SUPERSEDED')",
            name="ck_approval_request_status",
        ),
    )


class ApprovalEvent(Base, TenantOwned):
    __tablename__ = "approval_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    approval_request_id: Mapped[str] = mapped_column(
        ForeignKey("approval_requests.id", ondelete="RESTRICT"), nullable=False
    )
    intent_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    event_key: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "event_key", name="uq_approval_event_key"),
        CheckConstraint(
            "action IN ('APPROVE','REJECT','REVOKE','DELEGATE')",
            name="ck_approval_event_action",
        ),
    )


class PaymentSession(Base, TenantOwned, Timestamped):
    __tablename__ = "payment_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    purchase_intent_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_intents.id", ondelete="RESTRICT"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_order_id: Mapped[str] = mapped_column(String(128), nullable=False)
    hosted_url: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "provider_session_id", name="uq_provider_payment_session"),
    )


class PravaMcpConnection(Base, TenantOwned, Timestamped):
    """Encrypted, revocable Prava Pay OAuth connection owned by one organization."""

    __tablename__ = "prava_mcp_connections"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    client_id: Mapped[str] = mapped_column(String(160), nullable=False)
    encrypted_tokens: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    access_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_prava_mcp_connection_org"),
        CheckConstraint(
            "status IN ('CONNECTED','REFRESH_REQUIRED','REVOKED')",
            name="ck_prava_mcp_connection_status",
        ),
    )


class PravaMcpAuthorization(Base, TenantOwned, Timestamped):
    """One-time PKCE authorization state; verifier is encrypted at rest."""

    __tablename__ = "prava_mcp_authorizations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    state_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    client_id: Mapped[str] = mapped_column(String(160), nullable=False)
    encrypted_code_verifier: Mapped[str] = mapped_column(Text, nullable=False)
    redirect_uri: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "state_hash", name="uq_prava_mcp_oauth_state"),
    )


class PravaShoppingRun(Base, TenantOwned, Timestamped):
    """Canonical identifiers for one real Prava quote-to-order chain."""

    __tablename__ = "prava_shopping_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    purchase_intent_id: Mapped[str | None] = mapped_column(
        ForeignKey("purchase_intents.id", ondelete="RESTRICT"), nullable=True
    )
    product_id: Mapped[str] = mapped_column(String(200), nullable=False)
    variant_id: Mapped[str] = mapped_column(String(200), nullable=False)
    merchant: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    checkout_session_id: Mapped[str] = mapped_column(String(200), nullable=False)
    payment_session_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payment_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quote_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    order_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    safe_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "checkout_session_id", name="uq_prava_shopping_checkout"
        ),
        CheckConstraint("quantity >= 1", name="ck_prava_shopping_quantity"),
        CheckConstraint("amount > 0", name="ck_prava_shopping_amount"),
        CheckConstraint("currency = upper(currency)", name="ck_prava_shopping_currency"),
        CheckConstraint(
            "status IN ('QUOTED','AWAITING_APPROVAL','QUEUED','RUNNING','PAID','FAILED')",
            name="ck_prava_shopping_status",
        ),
    )


class BrowserReturnBinding(Base, TenantOwned, Timestamped):
    __tablename__ = "browser_return_bindings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    purchase_intent_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_intents.id", ondelete="RESTRICT"), nullable=False
    )
    payment_session_id: Mapped[str] = mapped_column(
        ForeignKey("payment_sessions.id", ondelete="RESTRICT"), nullable=False
    )
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    state_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_session_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    return_url_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "state_hash", name="uq_browser_return_state_hash"),
        UniqueConstraint(
            "organization_id",
            "payment_session_id",
            name="uq_browser_return_payment_session",
        ),
    )


class PaymentAttempt(Base, TenantOwned, Timestamped):
    __tablename__ = "payment_attempts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    purchase_intent_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_intents.id", ondelete="RESTRICT"), nullable=False
    )
    payment_session_id: Mapped[str] = mapped_column(
        ForeignKey("payment_sessions.id", ondelete="RESTRICT"), nullable=False
    )
    merchant_outcome: Mapped[str | None] = mapped_column(String(24), nullable=True)
    external_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "uq_open_payment_attempt",
            "purchase_intent_id",
            unique=True,
            postgresql_where=text("closed_at IS NULL"),
            sqlite_where=text("closed_at IS NULL"),
        ),
        Index(
            "uq_charged_or_uncertain_intent",
            "purchase_intent_id",
            unique=True,
            postgresql_where=text("merchant_outcome IN ('APPROVED','UNKNOWN')"),
            sqlite_where=text("merchant_outcome IN ('APPROVED','UNKNOWN')"),
        ),
    )


class MerchantOrder(Base, TenantOwned, Timestamped):
    __tablename__ = "merchant_orders"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    purchase_intent_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_intents.id", ondelete="RESTRICT"), nullable=False
    )
    merchant_adapter_id: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    external_order_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    safe_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "merchant_adapter_id", "idempotency_key", name="uq_merchant_order_provider_key"
        ),
        UniqueConstraint(
            "merchant_adapter_id", "external_order_id", name="uq_merchant_external_order"
        ),
    )


class Entitlement(Base, TenantOwned, Timestamped):
    __tablename__ = "entitlements"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    purchase_intent_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_intents.id", ondelete="RESTRICT"), nullable=False
    )
    merchant_order_id: Mapped[str] = mapped_column(
        ForeignKey("merchant_orders.id", ondelete="RESTRICT"), nullable=False
    )
    fulfillment_adapter_id: Mapped[str] = mapped_column(String(80), nullable=False)
    external_entitlement_id: Mapped[str] = mapped_column(String(128), nullable=False)
    fulfillment_item_id: Mapped[str] = mapped_column(String(100), nullable=False)
    entitlement_type: Mapped[str] = mapped_column(String(80), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(80), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False)
    safe_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "fulfillment_adapter_id",
            "external_entitlement_id",
            name="uq_external_entitlement",
        ),
        CheckConstraint("quantity >= 0", name="ck_entitlement_quantity_nonnegative"),
    )


class Receipt(Base, TenantOwned, Timestamped):
    __tablename__ = "receipts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    purchase_intent_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_intents.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    receipt_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)


class StackSnapshot(Base, TenantOwned, Timestamped):
    __tablename__ = "stack_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    lock: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    lock_hash: Mapped[str] = mapped_column(String(80), nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "version", name="uq_stack_snapshot_version"),
        UniqueConstraint("organization_id", "lock_hash", name="uq_stack_lock_hash"),
    )


class StackPatch(Base, TenantOwned, Timestamped):
    __tablename__ = "stack_patches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    base_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("stack_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    base_version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    patch_hash: Mapped[str] = mapped_column(String(80), nullable=False)


class SellerProduct(Base, TenantOwned, Timestamped):
    """Seller-safe product identity and current Product Evidence lifecycle pointer."""

    __tablename__ = "seller_products"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    public_summary: Mapped[str] = mapped_column(Text, nullable=False)
    publisher_authority: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_actor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    current_draft_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_pack_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    fixture_label: Mapped[str | None] = mapped_column(String(80), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "publisher_authority IN ('SELLER_SEALED','PLATFORM_COMPILED','EXTERNAL_UNSEALED')",
            name="ck_seller_product_authority",
        ),
        CheckConstraint(
            "state IN ('UNCLAIMED','CLAIM_PENDING','CLAIM_DENIED','SELLER_DRAFT',"
            "'VALIDATION_CONFLICT','IN_REVIEW','CHANGES_REQUESTED','PUBLISH_READY',"
            "'PUBLISHED','SUPERSEDED','PUBLICATION_FAILED')",
            name="ck_seller_product_state",
        ),
        CheckConstraint("current_version >= 1", name="ck_seller_product_version"),
        UniqueConstraint("organization_id", "name", "category", name="uq_seller_product_identity"),
    )


class SellerProductClaim(Base, TenantOwned, Timestamped):
    """A hash-bound vendor authority claim; raw proof never enters public projections."""

    __tablename__ = "seller_product_claims"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(
        ForeignKey("seller_products.id", ondelete="RESTRICT"), nullable=False
    )
    claimant_actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    requested_role: Mapped[str] = mapped_column(String(32), nullable=False)
    authority_proof_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    safe_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    decided_by_actor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "requested_role IN ('SELLER_EDITOR','SELLER_REVIEWER')",
            name="ck_seller_claim_role",
        ),
        CheckConstraint(
            "state IN ('CLAIM_PENDING','CLAIM_DENIED','SELLER_DRAFT')",
            name="ck_seller_claim_state",
        ),
        UniqueConstraint(
            "organization_id",
            "product_id",
            "claimant_actor_id",
            "authority_proof_hash",
            name="uq_seller_claim_proof",
        ),
        Index("ix_seller_claim_product_state", "organization_id", "product_id", "state"),
    )


class SellerPackDraft(Base, TenantOwned, Timestamped):
    """Mutable aggregate pointer whose revisions are preserved as immutable rows."""

    __tablename__ = "seller_pack_drafts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(
        ForeignKey("seller_products.id", ondelete="RESTRICT"), nullable=False
    )
    editor_actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    publisher_authority: Mapped[str] = mapped_column(String(32), nullable=False)
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    current_revision_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    validation: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    based_on_pack_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        CheckConstraint("current_revision >= 1", name="ck_seller_draft_revision"),
        CheckConstraint(
            "state IN ('SELLER_DRAFT','VALIDATION_CONFLICT','IN_REVIEW',"
            "'CHANGES_REQUESTED','PUBLISH_READY','PUBLISHED','SUPERSEDED',"
            "'PUBLICATION_FAILED')",
            name="ck_seller_draft_state",
        ),
        CheckConstraint(
            "publisher_authority IN ('SELLER_SEALED','PLATFORM_COMPILED','EXTERNAL_UNSEALED')",
            name="ck_seller_draft_authority",
        ),
        UniqueConstraint("organization_id", "product_id", name="uq_seller_current_draft"),
    )


class SellerPackDraftRevision(Base, TenantOwned):
    """Immutable, exact-hash snapshot of one draft revision."""

    __tablename__ = "seller_pack_draft_revisions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("seller_pack_drafts.id", ondelete="RESTRICT"), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    claims: Mapped[list[dict[str, Any]]] = mapped_column(JSON_DOCUMENT, nullable=False)
    fit_rules: Mapped[list[dict[str, Any]]] = mapped_column(JSON_DOCUMENT, nullable=False)
    anti_fit_rules: Mapped[list[dict[str, Any]]] = mapped_column(JSON_DOCUMENT, nullable=False)
    validation: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    created_by_actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("revision >= 1", name="ck_seller_draft_snapshot_revision"),
        UniqueConstraint(
            "organization_id", "draft_id", "revision", name="uq_seller_draft_revision"
        ),
        UniqueConstraint(
            "organization_id", "draft_id", "revision_hash", name="uq_seller_draft_hash"
        ),
    )


class SellerEvidenceAttachment(Base, TenantOwned, Timestamped):
    """Evidence provenance, unverified by default, scoped to one seller draft."""

    __tablename__ = "seller_evidence_attachments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("seller_pack_drafts.id", ondelete="RESTRICT"), nullable=False
    )
    attached_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    source_reference_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    public_source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_class: Mapped[str] = mapped_column(String(80), nullable=False)
    claim_fields: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_state: Mapped[str] = mapped_column(String(24), nullable=False)
    verification_actor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    verification_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    added_by_actor_id: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        CheckConstraint("attached_revision >= 1", name="ck_seller_evidence_revision"),
        CheckConstraint(
            "verification_state IN ('UNVERIFIED','PENDING','VERIFIED','REJECTED')",
            name="ck_seller_evidence_verification",
        ),
        UniqueConstraint(
            "organization_id",
            "draft_id",
            "source_reference_hash",
            name="uq_seller_evidence_source",
        ),
    )


class SellerReviewSubmission(Base, TenantOwned):
    """Frozen revision submitted for independent seller review."""

    __tablename__ = "seller_review_submissions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("seller_pack_drafts.id", ondelete="RESTRICT"), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    submitted_by_actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    reviewer_role: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("revision >= 1", name="ck_seller_review_revision"),
        CheckConstraint(
            "reviewer_role IN ('SELLER_REVIEWER','PLATFORM_OPERATOR')",
            name="ck_seller_review_role",
        ),
        CheckConstraint("status IN ('PENDING','COMPLETED')", name="ck_seller_review_status"),
        UniqueConstraint(
            "organization_id", "draft_id", "revision_hash", name="uq_seller_review_submission"
        ),
    )


class SellerReviewDecisionRecord(Base, TenantOwned):
    """Append-only reviewer decision bound to the frozen revision hash."""

    __tablename__ = "seller_review_decisions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    submission_id: Mapped[str] = mapped_column(
        ForeignKey("seller_review_submissions.id", ondelete="RESTRICT"), nullable=False
    )
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("seller_pack_drafts.id", ondelete="RESTRICT"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    revision_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    event_key: Mapped[str] = mapped_column(String(128), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "decision IN ('REQUEST_CHANGES','APPROVE','REJECT')",
            name="ck_seller_review_decision",
        ),
        CheckConstraint(
            "actor_role IN ('SELLER_REVIEWER','PLATFORM_OPERATOR')",
            name="ck_seller_review_actor_role",
        ),
        UniqueConstraint("organization_id", "event_key", name="uq_seller_review_event"),
        UniqueConstraint(
            "organization_id", "submission_id", name="uq_seller_review_final_decision"
        ),
    )


class SellerPackVersion(Base, TenantOwned):
    """Immutable published Product Evidence content."""

    __tablename__ = "seller_pack_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(
        ForeignKey("seller_products.id", ondelete="RESTRICT"), nullable=False
    )
    source_draft_id: Mapped[str] = mapped_column(
        ForeignKey("seller_pack_drafts.id", ondelete="RESTRICT"), nullable=False
    )
    source_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    source_revision_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    publisher_authority: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    published_by_actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    superseded_by_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        CheckConstraint("source_revision >= 1", name="ck_seller_pack_source_revision"),
        CheckConstraint("version >= 1", name="ck_seller_pack_version"),
        CheckConstraint(
            "publisher_authority IN ('SELLER_SEALED','PLATFORM_COMPILED')",
            name="ck_seller_pack_published_authority",
        ),
        UniqueConstraint("organization_id", "product_id", "version", name="uq_seller_pack_version"),
        UniqueConstraint("organization_id", "content_hash", name="uq_seller_pack_content_hash"),
    )


class SellerPackSuspension(Base, TenantOwned):
    """Append-only safety suspension; published Pack content is never mutated."""

    __tablename__ = "seller_pack_suspensions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    pack_version_id: Mapped[str] = mapped_column(
        ForeignKey("seller_pack_versions.id", ondelete="RESTRICT"), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    event_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "event_key", name="uq_seller_suspension_event"),
    )


class SellerPackExportArtifact(Base, TenantOwned):
    """Hash-bound export generated exclusively from immutable published fields."""

    __tablename__ = "seller_pack_export_artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    pack_version_id: Mapped[str] = mapped_column(
        ForeignKey("seller_pack_versions.id", ondelete="RESTRICT"), nullable=False
    )
    format: Mapped[str] = mapped_column(String(24), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "format IN ('JSON','HTML','REUSABLE_ANSWER')", name="ck_seller_export_format"
        ),
        UniqueConstraint(
            "organization_id", "pack_version_id", "format", name="uq_seller_pack_export"
        ),
    )


class SellerActivityEvent(Base, TenantOwned):
    """Observation event for non-causal seller value metrics."""

    __tablename__ = "seller_activity_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(
        ForeignKey("seller_products.id", ondelete="RESTRICT"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False)
    question_fingerprint: Mapped[str | None] = mapped_column(String(80), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fixture_label: Mapped[str | None] = mapped_column(String(80), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('ANSWER_RENDERED','SELLER_HANDOFF_REQUESTED')",
            name="ck_seller_activity_type",
        ),
        Index(
            "ix_seller_activity_window",
            "organization_id",
            "product_id",
            "occurred_at",
        ),
    )


class IdempotencyRecord(Base, TenantOwned, Timestamped):
    __tablename__ = "idempotency_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    operation: Mapped[str] = mapped_column(String(120), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    response_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "actor_id",
            "operation",
            "idempotency_key",
            name="uq_idempotency_scope",
        ),
    )


class OutboxEvent(Base, TenantOwned):
    __tablename__ = "outbox_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    aggregate_type: Mapped[str] = mapped_column(String(80), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    event_key: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("organization_id", "event_key", name="uq_outbox_event_key"),)


class WorkflowRun(Base, TenantOwned, Timestamped):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    aggregate_type: Mapped[str] = mapped_column(String(80), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    operation: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    result_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    safe_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    event_log: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=list
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "aggregate_type",
            "aggregate_id",
            "operation",
            name="uq_workflow_identity",
        ),
        CheckConstraint(
            "status IN ('PENDING','RUNNING','COMPLETED','FAILED')", name="ck_workflow_status"
        ),
    )


class TransactionTransition(Base, TenantOwned):
    __tablename__ = "transaction_transitions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    purchase_intent_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_intents.id", ondelete="RESTRICT"), nullable=False
    )
    from_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt_id: Mapped[str | None] = mapped_column(
        ForeignKey("payment_attempts.id", ondelete="RESTRICT"), nullable=True
    )
    actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    event_key: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_event_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "purchase_intent_id", "event_key", name="uq_transaction_event_key"
        ),
        Index(
            "uq_provider_event_ref",
            "organization_id",
            "provider_event_ref",
            unique=True,
            postgresql_where=text("provider_event_ref IS NOT NULL"),
        ),
    )
