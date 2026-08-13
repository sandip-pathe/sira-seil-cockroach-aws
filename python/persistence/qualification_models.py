"""CockroachDB models for qualified two-sided marketplace decisions."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from .models import JSON_DOCUMENT, Base, TenantOwned, Timestamped


class Vector1024(UserDefinedType[str]):
    """CockroachDB vector type used by Titan Text Embeddings V2."""

    cache_ok = True

    def get_col_spec(self, **_kwargs: object) -> str:
        return "VECTOR(1024)"


class CompanyContextItem(Base, TenantOwned, Timestamped):
    __tablename__ = "qualification_company_context_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    current_version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False)
    current_hash: Mapped[str] = mapped_column(String(80), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "kind IN ('REQUIREMENT','CONSTRAINT','STACK','POLICY','PREFERENCE','NOTE')",
            name="ck_qualification_context_kind",
        ),
        CheckConstraint("state IN ('ACTIVE','RETIRED')", name="ck_qualification_context_state"),
        CheckConstraint("current_version >= 1", name="ck_qualification_context_version"),
        UniqueConstraint("organization_id", "id", name="uq_qualification_context_item_tenant_id"),
        UniqueConstraint(
            "organization_id",
            "id",
            "current_version_id",
            "current_hash",
            name="uq_qualification_context_current_binding",
        ),
    )


class CompanyContextVersion(Base, TenantOwned, Timestamped):
    __tablename__ = "qualification_company_context_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    changed_by_actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    change_reason: Mapped[str] = mapped_column(String(500), nullable=False)

    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_qualification_context_revision"),
        UniqueConstraint(
            "organization_id", "item_id", "version", name="uq_qualification_context_revision"
        ),
        UniqueConstraint(
            "organization_id", "id", "content_hash", name="uq_qualification_context_binding"
        ),
        ForeignKeyConstraint(
            ["organization_id", "item_id"],
            [
                "qualification_company_context_items.organization_id",
                "qualification_company_context_items.id",
            ],
            ondelete="RESTRICT",
        ),
    )


class CompanyContextEmbedding(Base, TenantOwned, Timestamped):
    __tablename__ = "qualification_company_context_embeddings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    model_id: Mapped[str] = mapped_column(String(160), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[str] = mapped_column(Vector1024(), nullable=False)

    __table_args__ = (
        CheckConstraint("dimensions = 1024", name="ck_qualification_context_embedding_dimensions"),
        UniqueConstraint(
            "organization_id",
            "version_id",
            "content_hash",
            name="uq_qualification_context_embedding",
        ),
        ForeignKeyConstraint(
            ["organization_id", "version_id", "content_hash"],
            [
                "qualification_company_context_versions.organization_id",
                "qualification_company_context_versions.id",
                "qualification_company_context_versions.content_hash",
            ],
            ondelete="RESTRICT",
        ),
        Index(
            "ix_qualification_context_embedding_scope",
            "organization_id",
            "kind",
            "version_id",
        ),
    )


class ProductTwinVersion(Base, TenantOwned, Timestamped):
    __tablename__ = "qualification_product_twin_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    published_by_actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_qualification_twin_version"),
        UniqueConstraint(
            "organization_id", "product_id", "version", name="uq_qualification_twin_version"
        ),
        UniqueConstraint(
            "organization_id", "id", "content_hash", name="uq_qualification_twin_binding"
        ),
        UniqueConstraint("organization_id", "id", name="uq_qualification_twin_tenant_id"),
    )


class CatalogProjectionVersion(Base, TenantOwned, Timestamped):
    __tablename__ = "qualification_catalog_projection_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    buyer_safe_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)

    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_qualification_catalog_version"),
        UniqueConstraint(
            "organization_id",
            "product_id",
            "version",
            name="uq_qualification_catalog_version",
        ),
        UniqueConstraint(
            "organization_id", "id", "content_hash", name="uq_qualification_catalog_binding"
        ),
        UniqueConstraint("organization_id", "id", name="uq_qualification_catalog_tenant_id"),
    )


class EvidenceVersion(Base, TenantOwned, Timestamped):
    __tablename__ = "qualification_evidence_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    source_object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    source_checksum: Mapped[str] = mapped_column(String(80), nullable=False)
    facts: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reviewed_by_actor_id: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_qualification_evidence_version"),
        UniqueConstraint(
            "organization_id",
            "product_id",
            "version",
            name="uq_qualification_evidence_version",
        ),
        UniqueConstraint(
            "organization_id", "id", "content_hash", name="uq_qualification_evidence_binding"
        ),
    )


class ProductBundle(Base, TenantOwned, Timestamped):
    __tablename__ = "qualification_product_bundles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    product_twin_version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    catalog_projection_version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    disclosure_policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    embedding_profile: Mapped[str] = mapped_column(String(120), nullable=False)
    digest: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_qualification_bundle_version"),
        CheckConstraint(
            "state IN ('CANDIDATE','READY','ACTIVE','SUPERSEDED','RETRACTED')",
            name="ck_qualification_bundle_state",
        ),
        UniqueConstraint(
            "organization_id", "product_id", "version", name="uq_qualification_bundle_version"
        ),
        UniqueConstraint("organization_id", "id", "digest", name="uq_qualification_bundle_binding"),
        UniqueConstraint("organization_id", "id", name="uq_qualification_bundle_tenant_id"),
        ForeignKeyConstraint(
            ["organization_id", "product_twin_version_id"],
            [
                "qualification_product_twin_versions.organization_id",
                "qualification_product_twin_versions.id",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "catalog_projection_version_id"],
            [
                "qualification_catalog_projection_versions.organization_id",
                "qualification_catalog_projection_versions.id",
            ],
            ondelete="RESTRICT",
        ),
    )


class ProductBundleMember(Base, TenantOwned):
    __tablename__ = "qualification_product_bundle_members"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    bundle_id: Mapped[str] = mapped_column(String(64), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    member_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    member_id: Mapped[str] = mapped_column(String(64), nullable=False)
    member_hash: Mapped[str] = mapped_column(String(80), nullable=False)

    __table_args__ = (
        CheckConstraint("ordinal >= 0", name="ck_qualification_bundle_member_ordinal"),
        CheckConstraint(
            "member_kind IN ('PRODUCT_TWIN','CATALOG_PROJECTION','EVIDENCE')",
            name="ck_qualification_bundle_member_kind",
        ),
        UniqueConstraint(
            "organization_id", "bundle_id", "ordinal", name="uq_qualification_bundle_ordinal"
        ),
        UniqueConstraint(
            "organization_id",
            "bundle_id",
            "member_kind",
            "member_id",
            name="uq_qualification_bundle_member",
        ),
        ForeignKeyConstraint(
            ["organization_id", "bundle_id"],
            ["qualification_product_bundles.organization_id", "qualification_product_bundles.id"],
            ondelete="RESTRICT",
        ),
    )


class ActiveProductBundle(Base, TenantOwned, Timestamped):
    __tablename__ = "qualification_active_product_bundles"

    product_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    bundle_id: Mapped[str] = mapped_column(String(64), nullable=False)
    bundle_digest: Mapped[str] = mapped_column(String(80), nullable=False)
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        CheckConstraint("generation >= 1", name="ck_qualification_active_bundle_generation"),
        ForeignKeyConstraint(
            ["organization_id", "bundle_id", "bundle_digest"],
            [
                "qualification_product_bundles.organization_id",
                "qualification_product_bundles.id",
                "qualification_product_bundles.digest",
            ],
            ondelete="RESTRICT",
        ),
    )


class ProductEmbedding(Base, TenantOwned, Timestamped):
    __tablename__ = "qualification_product_embeddings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    bundle_id: Mapped[str] = mapped_column(String(64), nullable=False)
    product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    visibility: Mapped[str] = mapped_column(String(24), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    model_id: Mapped[str] = mapped_column(String(160), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[str] = mapped_column(Vector1024(), nullable=False)

    __table_args__ = (
        CheckConstraint("dimensions = 1024", name="ck_qualification_embedding_dimensions"),
        CheckConstraint(
            "visibility IN ('BUYER_SAFE','PUBLIC')", name="ck_qualification_embedding_visibility"
        ),
        UniqueConstraint(
            "organization_id", "bundle_id", "content_hash", name="uq_qualification_embedding"
        ),
        ForeignKeyConstraint(
            ["organization_id", "bundle_id"],
            ["qualification_product_bundles.organization_id", "qualification_product_bundles.id"],
            ondelete="RESTRICT",
        ),
        Index(
            "ix_qualification_embedding_scope",
            "organization_id",
            "category",
            "visibility",
            "bundle_id",
        ),
    )


class QualificationMission(Base, TenantOwned, Timestamped):
    __tablename__ = "qualification_missions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    buyer_context_version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    buyer_context_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    buyer_context_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    requirement_brief_version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    requirement_brief_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    requirement_brief_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    procurement_policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    procurement_policy_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    procurement_policy_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        CheckConstraint(
            "state IN ('DRAFT','READY','RUNNING','AWAITING_APPROVAL',"
            "'COMPLETED','FAILED','CANCELLED')",
            name="ck_qualification_mission_state",
        ),
        UniqueConstraint("organization_id", "id", name="uq_qualification_mission_tenant_id"),
    )


class QualificationMissionBundle(Base, TenantOwned):
    __tablename__ = "qualification_mission_bundles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mission_id: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt_id: Mapped[str] = mapped_column(String(64), nullable=False)
    product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    seller_organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    bundle_id: Mapped[str] = mapped_column(String(64), nullable=False)
    bundle_digest: Mapped[str] = mapped_column(String(80), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "attempt_id",
            "product_id",
            name="uq_qualification_attempt_product",
        ),
        ForeignKeyConstraint(
            ["organization_id", "mission_id"],
            ["qualification_missions.organization_id", "qualification_missions.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "attempt_id"],
            ["qualification_attempts.organization_id", "qualification_attempts.id"],
            ondelete="RESTRICT",
        ),
    )


class QualificationAttempt(Base, TenantOwned, Timestamped):
    __tablename__ = "qualification_attempts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mission_id: Mapped[str] = mapped_column(String(64), nullable=False)
    root_attempt_id: Mapped[str] = mapped_column(String(64), nullable=False)
    predecessor_attempt_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    replacement_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    input_digest: Mapped[str | None] = mapped_column(String(80), nullable=True)
    stale_reason: Mapped[str | None] = mapped_column(String(160), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "replacement_depth BETWEEN 0 AND 3", name="ck_qualification_replacement_depth"
        ),
        CheckConstraint("generation >= 0", name="ck_qualification_attempt_generation"),
        CheckConstraint(
            "state IN ('QUEUED','RUNNING','SNAPSHOT_COMPLETE','STALE',"
            "'COMPLETED','FAILED','CANCELLED')",
            name="ck_qualification_attempt_state",
        ),
        UniqueConstraint(
            "organization_id", "predecessor_attempt_id", name="uq_qualification_direct_successor"
        ),
        UniqueConstraint(
            "organization_id", "id", "generation", name="uq_qualification_attempt_fence"
        ),
        UniqueConstraint("organization_id", "id", name="uq_qualification_attempt_tenant_id"),
        ForeignKeyConstraint(
            ["organization_id", "mission_id"],
            ["qualification_missions.organization_id", "qualification_missions.id"],
            ondelete="RESTRICT",
        ),
        Index(
            "ix_qualification_attempt_claim",
            "organization_id",
            "state",
            "lease_expires_at",
        ),
    )


class AttemptDependency(Base, TenantOwned):
    __tablename__ = "qualification_attempt_dependencies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(String(64), nullable=False)
    dependency_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    dependency_organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    dependency_id: Mapped[str] = mapped_column(String(64), nullable=False)
    dependency_version: Mapped[str] = mapped_column(String(80), nullable=False)
    dependency_hash: Mapped[str] = mapped_column(String(80), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "attempt_id",
            "dependency_kind",
            "dependency_id",
            name="uq_qualification_attempt_dependency",
        ),
        ForeignKeyConstraint(
            ["organization_id", "attempt_id"],
            ["qualification_attempts.organization_id", "qualification_attempts.id"],
            ondelete="RESTRICT",
        ),
    )


class AttemptCheckpoint(Base, TenantOwned):
    __tablename__ = "qualification_attempt_checkpoints"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(String(64), nullable=False)
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(48), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("sequence >= 1", name="ck_qualification_checkpoint_sequence"),
        UniqueConstraint(
            "organization_id", "attempt_id", "sequence", name="uq_qualification_checkpoint_sequence"
        ),
        ForeignKeyConstraint(
            ["organization_id", "attempt_id", "generation"],
            [
                "qualification_attempts.organization_id",
                "qualification_attempts.id",
                "qualification_attempts.generation",
            ],
            ondelete="RESTRICT",
        ),
    )


class QualificationDecision(Base, TenantOwned, Timestamped):
    __tablename__ = "qualification_decisions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mission_id: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt_id: Mapped[str] = mapped_column(String(64), nullable=False)
    input_digest: Mapped[str] = mapped_column(String(80), nullable=False)
    decision_digest: Mapped[str] = mapped_column(String(80), nullable=False)
    recommended_product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    approval_state: Mapped[str] = mapped_column(String(24), nullable=False)
    current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint(
            "approval_state IN ('PENDING','APPROVED','REJECTED','INVALIDATED')",
            name="ck_qualification_decision_approval",
        ),
        UniqueConstraint("organization_id", "attempt_id", name="uq_qualification_decision_attempt"),
        UniqueConstraint(
            "organization_id",
            "mission_id",
            "input_digest",
            name="uq_qualification_decision_input",
        ),
        UniqueConstraint("organization_id", "id", name="uq_qualification_decision_tenant_id"),
        ForeignKeyConstraint(
            ["organization_id", "attempt_id"],
            ["qualification_attempts.organization_id", "qualification_attempts.id"],
            ondelete="RESTRICT",
        ),
        Index(
            "uq_qualification_current_decision",
            "organization_id",
            "mission_id",
            unique=True,
            cockroachdb_where=text("current"),
            postgresql_where=text("current"),
        ),
    )


class DecisionDependency(Base, TenantOwned):
    __tablename__ = "qualification_decision_dependencies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    decision_id: Mapped[str] = mapped_column(String(64), nullable=False)
    dependency_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    dependency_organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    dependency_id: Mapped[str] = mapped_column(String(64), nullable=False)
    dependency_version: Mapped[str] = mapped_column(String(80), nullable=False)
    dependency_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    cited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "decision_id",
            "dependency_kind",
            "dependency_id",
            name="uq_qualification_decision_dependency",
        ),
        ForeignKeyConstraint(
            ["organization_id", "decision_id"],
            ["qualification_decisions.organization_id", "qualification_decisions.id"],
            ondelete="RESTRICT",
        ),
    )


class MarketplaceEngagement(Base, Timestamped):
    __tablename__ = "marketplace_engagements"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mission_id: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_id: Mapped[str] = mapped_column(String(64), nullable=False)
    buyer_organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    seller_organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    input_digest: Mapped[str] = mapped_column(String(80), nullable=False)
    buyer_safe_requirement: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    buyer_safe_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "state IN ('OPEN','RESPONDED','CONSENT_PENDING','INTRODUCED','EXPIRED','INVALIDATED')",
            name="ck_marketplace_engagement_state",
        ),
        CheckConstraint(
            "buyer_organization_id <> seller_organization_id",
            name="ck_marketplace_distinct_parties",
        ),
        UniqueConstraint("decision_id", "seller_organization_id", name="uq_marketplace_engagement"),
    )


class BuyerEngagementProjection(Base, TenantOwned, Timestamped):
    __tablename__ = "marketplace_buyer_projections"

    engagement_id: Mapped[str] = mapped_column(
        ForeignKey("marketplace_engagements.id", ondelete="RESTRICT"), primary_key=True
    )
    projection_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)


class SellerEngagementProjection(Base, TenantOwned, Timestamped):
    __tablename__ = "marketplace_seller_projections"

    engagement_id: Mapped[str] = mapped_column(
        ForeignKey("marketplace_engagements.id", ondelete="RESTRICT"), primary_key=True
    )
    projection_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)


class SellerResponse(Base, TenantOwned, Timestamped):
    __tablename__ = "marketplace_seller_responses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    engagement_id: Mapped[str] = mapped_column(
        ForeignKey("marketplace_engagements.id", ondelete="RESTRICT"), nullable=False
    )
    buyer_organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    seller_organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    input_digest: Mapped[str] = mapped_column(String(80), nullable=False)
    response: Mapped[str] = mapped_column(String(24), nullable=False)
    cited_evidence_ids: Mapped[list[Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "buyer_organization_id <> seller_organization_id",
            name="ck_marketplace_response_distinct_parties",
        ),
        CheckConstraint(
            "organization_id = seller_organization_id",
            name="ck_marketplace_response_seller_owned",
        ),
        CheckConstraint(
            "response IN ('FIT','ANTI_FIT','NEEDS_INFO')", name="ck_marketplace_seller_response"
        ),
        UniqueConstraint(
            "organization_id", "engagement_id", "input_digest", name="uq_marketplace_response"
        ),
    )


class MarketplaceConsent(Base, Timestamped):
    __tablename__ = "marketplace_consents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    engagement_id: Mapped[str] = mapped_column(
        ForeignKey("marketplace_engagements.id", ondelete="RESTRICT"), nullable=False
    )
    party: Mapped[str] = mapped_column(String(12), nullable=False)
    buyer_organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    seller_organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    input_digest: Mapped[str] = mapped_column(String(80), nullable=False)
    approved_fields_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("party IN ('BUYER','SELLER')", name="ck_marketplace_consent_party"),
        CheckConstraint(
            "buyer_organization_id <> seller_organization_id",
            name="ck_marketplace_consent_distinct_parties",
        ),
        CheckConstraint(
            "state IN ('GRANTED','REVOKED','EXPIRED')", name="ck_marketplace_consent_state"
        ),
        UniqueConstraint(
            "engagement_id", "party", "input_digest", name="uq_marketplace_consent_digest"
        ),
    )


class QualifiedIntroduction(Base, Timestamped):
    __tablename__ = "qualified_introductions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    engagement_id: Mapped[str] = mapped_column(
        ForeignKey("marketplace_engagements.id", ondelete="RESTRICT"), nullable=False
    )
    decision_id: Mapped[str] = mapped_column(String(64), nullable=False)
    buyer_organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    seller_organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    input_digest: Mapped[str] = mapped_column(String(80), nullable=False)
    shared_fields_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    receipt_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)

    __table_args__ = (
        UniqueConstraint("engagement_id", name="uq_qualified_introduction_engagement"),
        UniqueConstraint(
            "decision_id", "seller_organization_id", name="uq_qualified_introduction_effect"
        ),
    )


class ConsumerReceipt(Base, TenantOwned):
    __tablename__ = "qualification_consumer_receipts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    consumer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    message_id: Mapped[str] = mapped_column(String(160), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    result_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "consumer_name",
            "message_id",
            name="uq_qualification_consumer_receipt",
        ),
    )


class QualificationEffect(Base, TenantOwned, Timestamped):
    __tablename__ = "qualification_effects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    effect_kind: Mapped[str] = mapped_column(String(48), nullable=False)
    semantic_key: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    result_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "state IN ('RESERVED','DELIVERED','FAILED','CANCELLED')",
            name="ck_qualification_effect_state",
        ),
        UniqueConstraint(
            "organization_id", "effect_kind", "semantic_key", name="uq_qualification_effect"
        ),
    )
