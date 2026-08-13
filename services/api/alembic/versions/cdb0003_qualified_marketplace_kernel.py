"""qualified marketplace kernel

Revision ID: cdb0003
Revises: cdb0002
Create Date: 2026-08-13 05:46:41.748925
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from persistence.qualification_models import Vector1024

revision: str = "cdb0003"
down_revision: str | None = "cdb0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INSERT_ONLY_TENANT_TABLES = (
    "marketplace_buyer_projections",
    "marketplace_seller_projections",
    "marketplace_seller_responses",
    "qualification_attempt_checkpoints",
    "qualification_attempt_dependencies",
    "qualification_catalog_projection_versions",
    "qualification_consumer_receipts",
    "qualification_decision_dependencies",
    "qualification_evidence_versions",
    "qualification_mission_bundles",
    "qualification_product_bundle_members",
    "qualification_product_embeddings",
    "qualification_product_twin_versions",
)
_MUTABLE_TENANT_TABLES = (
    "qualification_active_product_bundles",
    "qualification_attempts",
    "qualification_decisions",
    "qualification_effects",
    "qualification_missions",
    "qualification_product_bundles",
)
_BILATERAL_TABLES = (
    "marketplace_consents",
    "marketplace_engagements",
    "qualified_introductions",
)
_WORKER_PUBLISHED_TABLES = (
    "qualification_active_product_bundles",
    "qualification_catalog_projection_versions",
    "qualification_evidence_versions",
    "qualification_product_bundle_members",
    "qualification_product_bundles",
    "qualification_product_embeddings",
)
_TENANT_EXPRESSION = (
    "organization_id = split_part(current_setting('application_name', true), '.', 2)"
)
_BILATERAL_EXPRESSION = (
    "split_part(current_setting('application_name', true), '.', 2) "
    "IN (buyer_organization_id, seller_organization_id)"
)


def _install_security_and_vector_index() -> None:
    op.execute("CREATE ROLE IF NOT EXISTS sira_qualification_worker")
    op.execute("GRANT USAGE ON SCHEMA public TO sira_qualification_worker")
    for table in _INSERT_ONLY_TENANT_TABLES:
        op.execute(f'GRANT SELECT, INSERT ON TABLE "{table}" TO sira_runtime')
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(
            f'CREATE POLICY tenant_isolation ON "{table}" FOR ALL TO sira_runtime '
            f"USING ({_TENANT_EXPRESSION}) WITH CHECK ({_TENANT_EXPRESSION})"
        )
    for table in _MUTABLE_TENANT_TABLES:
        op.execute(f'GRANT SELECT, INSERT, UPDATE ON TABLE "{table}" TO sira_runtime')
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(
            f'CREATE POLICY tenant_isolation ON "{table}" FOR ALL TO sira_runtime '
            f"USING ({_TENANT_EXPRESSION}) WITH CHECK ({_TENANT_EXPRESSION})"
        )
    for table in _BILATERAL_TABLES:
        op.execute(f'GRANT SELECT, INSERT, UPDATE ON TABLE "{table}" TO sira_runtime')
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(
            f'CREATE POLICY bilateral_access ON "{table}" FOR ALL TO sira_runtime '
            f"USING ({_BILATERAL_EXPRESSION}) WITH CHECK ({_BILATERAL_EXPRESSION})"
        )
    for table in _WORKER_PUBLISHED_TABLES:
        op.execute(f'GRANT SELECT ON TABLE "{table}" TO sira_qualification_worker')
        op.execute(
            f'CREATE POLICY worker_published_select ON "{table}" '
            "FOR SELECT TO sira_qualification_worker USING (true)"
        )
    op.execute(
        "CREATE VECTOR INDEX qualification_product_embedding_dvi "
        "ON qualification_product_embeddings "
        "(organization_id, category, visibility, embedding vector_cosine_ops)"
    )


def _remove_security_and_vector_index() -> None:
    op.execute("DROP INDEX IF EXISTS qualification_product_embedding_dvi")
    for table in reversed(_WORKER_PUBLISHED_TABLES):
        op.execute(f'DROP POLICY IF EXISTS worker_published_select ON "{table}"')
        op.execute(f'REVOKE SELECT ON TABLE "{table}" FROM sira_qualification_worker')
    for table in reversed(_BILATERAL_TABLES):
        op.execute(f'DROP POLICY IF EXISTS bilateral_access ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON TABLE "{table}" FROM sira_runtime')
    for table in reversed(_MUTABLE_TENANT_TABLES + _INSERT_ONLY_TENANT_TABLES):
        op.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON TABLE "{table}" FROM sira_runtime')
    op.execute("REVOKE USAGE ON SCHEMA public FROM sira_qualification_worker")
    op.execute("DROP ROLE IF EXISTS sira_qualification_worker")


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "marketplace_engagements",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("mission_id", sa.String(length=64), nullable=False),
        sa.Column("decision_id", sa.String(length=64), nullable=False),
        sa.Column("buyer_organization_id", sa.String(length=64), nullable=False),
        sa.Column("seller_organization_id", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("input_digest", sa.String(length=80), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ('OPEN','RESPONDED','CONSENT_PENDING','INTRODUCED','EXPIRED','INVALIDATED')",
            name="ck_marketplace_engagement_state",
        ),
        sa.CheckConstraint(
            "buyer_organization_id <> seller_organization_id",
            name="ck_marketplace_distinct_parties",
        ),
        sa.ForeignKeyConstraint(
            ["buyer_organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["seller_organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "decision_id", "seller_organization_id", name="uq_marketplace_engagement"
        ),
    )
    op.create_table(
        "qualification_catalog_projection_versions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        sa.Column(
            "buyer_safe_payload",
            sa.JSON()
            .with_variant(postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), "cockroachdb")
            .with_variant(postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("version >= 1", name="ck_qualification_catalog_version"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "id", "content_hash", name="uq_qualification_catalog_binding"
        ),
        sa.UniqueConstraint("organization_id", "id", name="uq_qualification_catalog_tenant_id"),
        sa.UniqueConstraint(
            "organization_id", "product_id", "version", name="uq_qualification_catalog_version"
        ),
    )
    op.create_index(
        op.f("ix_qualification_catalog_projection_versions_organization_id"),
        "qualification_catalog_projection_versions",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "qualification_consumer_receipts",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("consumer_name", sa.String(length=100), nullable=False),
        sa.Column("message_id", sa.String(length=160), nullable=False),
        sa.Column("payload_hash", sa.String(length=80), nullable=False),
        sa.Column("result_ref", sa.String(length=100), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "consumer_name",
            "message_id",
            name="uq_qualification_consumer_receipt",
        ),
    )
    op.create_index(
        op.f("ix_qualification_consumer_receipts_organization_id"),
        "qualification_consumer_receipts",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "qualification_effects",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("effect_kind", sa.String(length=48), nullable=False),
        sa.Column("semantic_key", sa.String(length=200), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column(
            "payload",
            sa.JSON()
            .with_variant(postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), "cockroachdb")
            .with_variant(postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("result_ref", sa.String(length=100), nullable=True),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ('RESERVED','DELIVERED','FAILED','CANCELLED')",
            name="ck_qualification_effect_state",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "effect_kind", "semantic_key", name="uq_qualification_effect"
        ),
    )
    op.create_index(
        op.f("ix_qualification_effects_organization_id"),
        "qualification_effects",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "qualification_evidence_versions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        sa.Column("source_object_key", sa.String(length=500), nullable=False),
        sa.Column("source_checksum", sa.String(length=80), nullable=False),
        sa.Column(
            "facts",
            sa.JSON()
            .with_variant(postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), "cockroachdb")
            .with_variant(postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        sa.Column("reviewed_by_actor_id", sa.String(length=100), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("version >= 1", name="ck_qualification_evidence_version"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "id", "content_hash", name="uq_qualification_evidence_binding"
        ),
        sa.UniqueConstraint(
            "organization_id", "product_id", "version", name="uq_qualification_evidence_version"
        ),
    )
    op.create_index(
        op.f("ix_qualification_evidence_versions_organization_id"),
        "qualification_evidence_versions",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "qualification_missions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("buyer_context_version_id", sa.String(length=64), nullable=False),
        sa.Column("buyer_context_hash", sa.String(length=80), nullable=False),
        sa.Column("requirement_brief_version_id", sa.String(length=64), nullable=False),
        sa.Column("requirement_brief_hash", sa.String(length=80), nullable=False),
        sa.Column("procurement_policy_version", sa.String(length=80), nullable=False),
        sa.Column("procurement_policy_hash", sa.String(length=80), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ('DRAFT','READY','RUNNING','AWAITING_APPROVAL','COMPLETED','FAILED','CANCELLED')",
            name="ck_qualification_mission_state",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_qualification_mission_tenant_id"),
    )
    op.create_index(
        op.f("ix_qualification_missions_organization_id"),
        "qualification_missions",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "qualification_product_twin_versions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        sa.Column(
            "payload",
            sa.JSON()
            .with_variant(postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), "cockroachdb")
            .with_variant(postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("published_by_actor_id", sa.String(length=100), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("version >= 1", name="ck_qualification_twin_version"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "id", "content_hash", name="uq_qualification_twin_binding"
        ),
        sa.UniqueConstraint("organization_id", "id", name="uq_qualification_twin_tenant_id"),
        sa.UniqueConstraint(
            "organization_id", "product_id", "version", name="uq_qualification_twin_version"
        ),
    )
    op.create_index(
        op.f("ix_qualification_product_twin_versions_organization_id"),
        "qualification_product_twin_versions",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "marketplace_buyer_projections",
        sa.Column("engagement_id", sa.String(length=64), nullable=False),
        sa.Column("projection_hash", sa.String(length=80), nullable=False),
        sa.Column(
            "payload",
            sa.JSON()
            .with_variant(postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), "cockroachdb")
            .with_variant(postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["engagement_id"], ["marketplace_engagements.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("engagement_id"),
    )
    op.create_index(
        op.f("ix_marketplace_buyer_projections_organization_id"),
        "marketplace_buyer_projections",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "marketplace_consents",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("engagement_id", sa.String(length=64), nullable=False),
        sa.Column("party", sa.String(length=12), nullable=False),
        sa.Column("buyer_organization_id", sa.String(length=64), nullable=False),
        sa.Column("seller_organization_id", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=100), nullable=False),
        sa.Column("input_digest", sa.String(length=80), nullable=False),
        sa.Column("approved_fields_hash", sa.String(length=80), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("party IN ('BUYER','SELLER')", name="ck_marketplace_consent_party"),
        sa.CheckConstraint(
            "buyer_organization_id <> seller_organization_id",
            name="ck_marketplace_consent_distinct_parties",
        ),
        sa.CheckConstraint(
            "state IN ('GRANTED','REVOKED','EXPIRED')", name="ck_marketplace_consent_state"
        ),
        sa.ForeignKeyConstraint(
            ["engagement_id"], ["marketplace_engagements.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["buyer_organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["seller_organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "engagement_id", "party", "input_digest", name="uq_marketplace_consent_digest"
        ),
    )
    op.create_table(
        "marketplace_seller_projections",
        sa.Column("engagement_id", sa.String(length=64), nullable=False),
        sa.Column("projection_hash", sa.String(length=80), nullable=False),
        sa.Column(
            "payload",
            sa.JSON()
            .with_variant(postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), "cockroachdb")
            .with_variant(postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["engagement_id"], ["marketplace_engagements.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("engagement_id"),
    )
    op.create_index(
        op.f("ix_marketplace_seller_projections_organization_id"),
        "marketplace_seller_projections",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "marketplace_seller_responses",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("engagement_id", sa.String(length=64), nullable=False),
        sa.Column("input_digest", sa.String(length=80), nullable=False),
        sa.Column("response", sa.String(length=24), nullable=False),
        sa.Column(
            "cited_evidence_ids",
            sa.JSON()
            .with_variant(postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), "cockroachdb")
            .with_variant(postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.String(length=100), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "response IN ('FIT','ANTI_FIT','NEEDS_INFO')", name="ck_marketplace_seller_response"
        ),
        sa.ForeignKeyConstraint(
            ["engagement_id"], ["marketplace_engagements.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "engagement_id", "input_digest", name="uq_marketplace_response"
        ),
    )
    op.create_index(
        op.f("ix_marketplace_seller_responses_organization_id"),
        "marketplace_seller_responses",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "qualification_attempts",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("mission_id", sa.String(length=64), nullable=False),
        sa.Column("root_attempt_id", sa.String(length=64), nullable=False),
        sa.Column("predecessor_attempt_id", sa.String(length=64), nullable=True),
        sa.Column("replacement_depth", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("lease_owner", sa.String(length=100), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_digest", sa.String(length=80), nullable=True),
        sa.Column("stale_reason", sa.String(length=160), nullable=True),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ('QUEUED','RUNNING','SNAPSHOT_COMPLETE','STALE','COMPLETED','FAILED','CANCELLED')",
            name="ck_qualification_attempt_state",
        ),
        sa.CheckConstraint("generation >= 0", name="ck_qualification_attempt_generation"),
        sa.CheckConstraint(
            "replacement_depth BETWEEN 0 AND 3", name="ck_qualification_replacement_depth"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "mission_id"],
            ["qualification_missions.organization_id", "qualification_missions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "id", "generation", name="uq_qualification_attempt_fence"
        ),
        sa.UniqueConstraint("organization_id", "id", name="uq_qualification_attempt_tenant_id"),
        sa.UniqueConstraint(
            "organization_id", "predecessor_attempt_id", name="uq_qualification_direct_successor"
        ),
    )
    op.create_index(
        "ix_qualification_attempt_claim",
        "qualification_attempts",
        ["organization_id", "state", "lease_expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_qualification_attempts_organization_id"),
        "qualification_attempts",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "qualification_mission_bundles",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("mission_id", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("seller_organization_id", sa.String(length=64), nullable=False),
        sa.Column("bundle_id", sa.String(length=64), nullable=False),
        sa.Column("bundle_digest", sa.String(length=80), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "mission_id"],
            ["qualification_missions.organization_id", "qualification_missions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "mission_id", "product_id", name="uq_qualification_mission_product"
        ),
    )
    op.create_index(
        op.f("ix_qualification_mission_bundles_organization_id"),
        "qualification_mission_bundles",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "qualification_product_bundles",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("product_twin_version_id", sa.String(length=64), nullable=False),
        sa.Column("catalog_projection_version_id", sa.String(length=64), nullable=False),
        sa.Column("disclosure_policy_version", sa.String(length=80), nullable=False),
        sa.Column("embedding_profile", sa.String(length=120), nullable=False),
        sa.Column("digest", sa.String(length=80), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ('CANDIDATE','READY','ACTIVE','SUPERSEDED','RETRACTED')",
            name="ck_qualification_bundle_state",
        ),
        sa.CheckConstraint("version >= 1", name="ck_qualification_bundle_version"),
        sa.ForeignKeyConstraint(
            ["organization_id", "catalog_projection_version_id"],
            [
                "qualification_catalog_projection_versions.organization_id",
                "qualification_catalog_projection_versions.id",
            ],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "product_twin_version_id"],
            [
                "qualification_product_twin_versions.organization_id",
                "qualification_product_twin_versions.id",
            ],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "id", "digest", name="uq_qualification_bundle_binding"
        ),
        sa.UniqueConstraint("organization_id", "id", name="uq_qualification_bundle_tenant_id"),
        sa.UniqueConstraint(
            "organization_id", "product_id", "version", name="uq_qualification_bundle_version"
        ),
    )
    op.create_index(
        op.f("ix_qualification_product_bundles_organization_id"),
        "qualification_product_bundles",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "qualified_introductions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("engagement_id", sa.String(length=64), nullable=False),
        sa.Column("decision_id", sa.String(length=64), nullable=False),
        sa.Column("buyer_organization_id", sa.String(length=64), nullable=False),
        sa.Column("seller_organization_id", sa.String(length=64), nullable=False),
        sa.Column("input_digest", sa.String(length=80), nullable=False),
        sa.Column("shared_fields_hash", sa.String(length=80), nullable=False),
        sa.Column(
            "receipt_payload",
            sa.JSON()
            .with_variant(postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), "cockroachdb")
            .with_variant(postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["buyer_organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["engagement_id"], ["marketplace_engagements.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["seller_organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "decision_id", "seller_organization_id", name="uq_qualified_introduction_effect"
        ),
        sa.UniqueConstraint("engagement_id", name="uq_qualified_introduction_engagement"),
    )
    op.create_table(
        "qualification_active_product_bundles",
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("bundle_id", sa.String(length=64), nullable=False),
        sa.Column("bundle_digest", sa.String(length=80), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("generation >= 1", name="ck_qualification_active_bundle_generation"),
        sa.ForeignKeyConstraint(
            ["organization_id", "bundle_id", "bundle_digest"],
            [
                "qualification_product_bundles.organization_id",
                "qualification_product_bundles.id",
                "qualification_product_bundles.digest",
            ],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("product_id"),
    )
    op.create_index(
        op.f("ix_qualification_active_product_bundles_organization_id"),
        "qualification_active_product_bundles",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "qualification_attempt_checkpoints",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("attempt_id", sa.String(length=64), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=48), nullable=False),
        sa.Column(
            "payload",
            sa.JSON()
            .with_variant(postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), "cockroachdb")
            .with_variant(postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.CheckConstraint("sequence >= 1", name="ck_qualification_checkpoint_sequence"),
        sa.ForeignKeyConstraint(
            ["organization_id", "attempt_id", "generation"],
            [
                "qualification_attempts.organization_id",
                "qualification_attempts.id",
                "qualification_attempts.generation",
            ],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "attempt_id", "sequence", name="uq_qualification_checkpoint_sequence"
        ),
    )
    op.create_index(
        op.f("ix_qualification_attempt_checkpoints_organization_id"),
        "qualification_attempt_checkpoints",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "qualification_attempt_dependencies",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("attempt_id", sa.String(length=64), nullable=False),
        sa.Column("dependency_kind", sa.String(length=40), nullable=False),
        sa.Column("dependency_organization_id", sa.String(length=64), nullable=False),
        sa.Column("dependency_id", sa.String(length=64), nullable=False),
        sa.Column("dependency_version", sa.String(length=80), nullable=False),
        sa.Column("dependency_hash", sa.String(length=80), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "attempt_id"],
            ["qualification_attempts.organization_id", "qualification_attempts.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "attempt_id",
            "dependency_kind",
            "dependency_id",
            name="uq_qualification_attempt_dependency",
        ),
    )
    op.create_index(
        op.f("ix_qualification_attempt_dependencies_organization_id"),
        "qualification_attempt_dependencies",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "qualification_decisions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("mission_id", sa.String(length=64), nullable=False),
        sa.Column("attempt_id", sa.String(length=64), nullable=False),
        sa.Column("input_digest", sa.String(length=80), nullable=False),
        sa.Column("decision_digest", sa.String(length=80), nullable=False),
        sa.Column("recommended_product_id", sa.String(length=64), nullable=False),
        sa.Column(
            "payload",
            sa.JSON()
            .with_variant(postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), "cockroachdb")
            .with_variant(postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("approval_state", sa.String(length=24), nullable=False),
        sa.Column("current", sa.Boolean(), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "approval_state IN ('PENDING','APPROVED','REJECTED','INVALIDATED')",
            name="ck_qualification_decision_approval",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "attempt_id"],
            ["qualification_attempts.organization_id", "qualification_attempts.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "attempt_id", name="uq_qualification_decision_attempt"
        ),
        sa.UniqueConstraint("organization_id", "id", name="uq_qualification_decision_tenant_id"),
        sa.UniqueConstraint(
            "organization_id", "mission_id", "input_digest", name="uq_qualification_decision_input"
        ),
    )
    op.create_index(
        op.f("ix_qualification_decisions_organization_id"),
        "qualification_decisions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "uq_qualification_current_decision",
        "qualification_decisions",
        ["organization_id", "mission_id"],
        unique=True,
        cockroachdb_where=sa.text("current"),
        postgresql_where=sa.text("current"),
    )
    op.create_table(
        "qualification_product_bundle_members",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("bundle_id", sa.String(length=64), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("member_kind", sa.String(length=32), nullable=False),
        sa.Column("member_id", sa.String(length=64), nullable=False),
        sa.Column("member_hash", sa.String(length=80), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "member_kind IN ('PRODUCT_TWIN','CATALOG_PROJECTION','EVIDENCE')",
            name="ck_qualification_bundle_member_kind",
        ),
        sa.CheckConstraint("ordinal >= 0", name="ck_qualification_bundle_member_ordinal"),
        sa.ForeignKeyConstraint(
            ["organization_id", "bundle_id"],
            ["qualification_product_bundles.organization_id", "qualification_product_bundles.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "bundle_id",
            "member_kind",
            "member_id",
            name="uq_qualification_bundle_member",
        ),
        sa.UniqueConstraint(
            "organization_id", "bundle_id", "ordinal", name="uq_qualification_bundle_ordinal"
        ),
    )
    op.create_index(
        op.f("ix_qualification_product_bundle_members_organization_id"),
        "qualification_product_bundle_members",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "qualification_product_embeddings",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("bundle_id", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("visibility", sa.String(length=24), nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        sa.Column("model_id", sa.String(length=160), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector1024(), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "visibility IN ('BUYER_SAFE','PUBLIC')", name="ck_qualification_embedding_visibility"
        ),
        sa.CheckConstraint("dimensions = 1024", name="ck_qualification_embedding_dimensions"),
        sa.ForeignKeyConstraint(
            ["organization_id", "bundle_id"],
            ["qualification_product_bundles.organization_id", "qualification_product_bundles.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "bundle_id", "content_hash", name="uq_qualification_embedding"
        ),
    )
    op.create_index(
        "ix_qualification_embedding_scope",
        "qualification_product_embeddings",
        ["organization_id", "category", "visibility", "bundle_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_qualification_product_embeddings_organization_id"),
        "qualification_product_embeddings",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "qualification_decision_dependencies",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("decision_id", sa.String(length=64), nullable=False),
        sa.Column("dependency_kind", sa.String(length=40), nullable=False),
        sa.Column("dependency_organization_id", sa.String(length=64), nullable=False),
        sa.Column("dependency_id", sa.String(length=64), nullable=False),
        sa.Column("dependency_version", sa.String(length=80), nullable=False),
        sa.Column("dependency_hash", sa.String(length=80), nullable=False),
        sa.Column("cited", sa.Boolean(), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "decision_id"],
            ["qualification_decisions.organization_id", "qualification_decisions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "decision_id",
            "dependency_kind",
            "dependency_id",
            name="uq_qualification_decision_dependency",
        ),
    )
    op.create_index(
        op.f("ix_qualification_decision_dependencies_organization_id"),
        "qualification_decision_dependencies",
        ["organization_id"],
        unique=False,
    )
    _install_security_and_vector_index()
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    _remove_security_and_vector_index()
    op.drop_index(
        op.f("ix_qualification_decision_dependencies_organization_id"),
        table_name="qualification_decision_dependencies",
    )
    op.drop_table("qualification_decision_dependencies")
    op.drop_index(
        op.f("ix_qualification_product_embeddings_organization_id"),
        table_name="qualification_product_embeddings",
    )
    op.drop_index("ix_qualification_embedding_scope", table_name="qualification_product_embeddings")
    op.drop_table("qualification_product_embeddings")
    op.drop_index(
        op.f("ix_qualification_product_bundle_members_organization_id"),
        table_name="qualification_product_bundle_members",
    )
    op.drop_table("qualification_product_bundle_members")
    op.drop_index(
        "uq_qualification_current_decision",
        table_name="qualification_decisions",
        cockroachdb_where=sa.text("current"),
        postgresql_where=sa.text("current"),
    )
    op.drop_index(
        op.f("ix_qualification_decisions_organization_id"), table_name="qualification_decisions"
    )
    op.drop_table("qualification_decisions")
    op.drop_index(
        op.f("ix_qualification_attempt_dependencies_organization_id"),
        table_name="qualification_attempt_dependencies",
    )
    op.drop_table("qualification_attempt_dependencies")
    op.drop_index(
        op.f("ix_qualification_attempt_checkpoints_organization_id"),
        table_name="qualification_attempt_checkpoints",
    )
    op.drop_table("qualification_attempt_checkpoints")
    op.drop_index(
        op.f("ix_qualification_active_product_bundles_organization_id"),
        table_name="qualification_active_product_bundles",
    )
    op.drop_table("qualification_active_product_bundles")
    op.drop_table("qualified_introductions")
    op.drop_index(
        op.f("ix_qualification_product_bundles_organization_id"),
        table_name="qualification_product_bundles",
    )
    op.drop_table("qualification_product_bundles")
    op.drop_index(
        op.f("ix_qualification_mission_bundles_organization_id"),
        table_name="qualification_mission_bundles",
    )
    op.drop_table("qualification_mission_bundles")
    op.drop_index(
        op.f("ix_qualification_attempts_organization_id"), table_name="qualification_attempts"
    )
    op.drop_index("ix_qualification_attempt_claim", table_name="qualification_attempts")
    op.drop_table("qualification_attempts")
    op.drop_index(
        op.f("ix_marketplace_seller_responses_organization_id"),
        table_name="marketplace_seller_responses",
    )
    op.drop_table("marketplace_seller_responses")
    op.drop_index(
        op.f("ix_marketplace_seller_projections_organization_id"),
        table_name="marketplace_seller_projections",
    )
    op.drop_table("marketplace_seller_projections")
    op.drop_index(
        op.f("ix_marketplace_consents_organization_id"), table_name="marketplace_consents"
    )
    op.drop_table("marketplace_consents")
    op.drop_index(
        op.f("ix_marketplace_buyer_projections_organization_id"),
        table_name="marketplace_buyer_projections",
    )
    op.drop_table("marketplace_buyer_projections")
    op.drop_index(
        op.f("ix_qualification_product_twin_versions_organization_id"),
        table_name="qualification_product_twin_versions",
    )
    op.drop_table("qualification_product_twin_versions")
    op.drop_index(
        op.f("ix_qualification_missions_organization_id"), table_name="qualification_missions"
    )
    op.drop_table("qualification_missions")
    op.drop_index(
        op.f("ix_qualification_evidence_versions_organization_id"),
        table_name="qualification_evidence_versions",
    )
    op.drop_table("qualification_evidence_versions")
    op.drop_index(
        op.f("ix_qualification_effects_organization_id"), table_name="qualification_effects"
    )
    op.drop_table("qualification_effects")
    op.drop_index(
        op.f("ix_qualification_consumer_receipts_organization_id"),
        table_name="qualification_consumer_receipts",
    )
    op.drop_table("qualification_consumer_receipts")
    op.drop_index(
        op.f("ix_qualification_catalog_projection_versions_organization_id"),
        table_name="qualification_catalog_projection_versions",
    )
    op.drop_table("qualification_catalog_projection_versions")
    op.drop_table("marketplace_engagements")
    # ### end Alembic commands ###
