"""add proof exchange projection and exact authority

Revision ID: 7d2f4a9c8e10
Revises: c3d4e5f60718
Create Date: 2026-08-10 03:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7d2f4a9c8e10"
down_revision: str | None = "c3d4e5f60718"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_POLICY_EXPRESSION = (
    "organization_id = NULLIF(current_setting('app.organization_id', true), '')"
)


def _enable_forced_rls(table_name: str) -> None:
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return
    table = connection.dialect.identifier_preparer.quote(table_name)
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"CREATE POLICY tenant_access ON {table} AS PERMISSIVE FOR ALL TO PUBLIC "
            f"USING ({TENANT_POLICY_EXPRESSION}) WITH CHECK ({TENANT_POLICY_EXPRESSION})"
        )
    )
    op.execute(
        sa.text(
            f"CREATE POLICY tenant_isolation ON {table} AS RESTRICTIVE FOR ALL TO PUBLIC "
            f"USING ({TENANT_POLICY_EXPRESSION}) WITH CHECK ({TENANT_POLICY_EXPRESSION})"
        )
    )


def upgrade() -> None:
    op.add_column(
        "seller_pack_draft_revisions",
        sa.Column("proof_adapter", sa.JSON(), nullable=True),
    )
    op.create_table(
        "buyer_proof_adapter_projections",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("source_seller_organization_id", sa.String(length=64), nullable=False),
        sa.Column("source_pack_version_id", sa.String(length=64), nullable=False),
        sa.Column("source_pack_content_hash", sa.String(length=80), nullable=False),
        sa.Column("publication_event_key", sa.String(length=255), nullable=False),
        sa.Column("adapter_id", sa.String(length=100), nullable=False),
        sa.Column("artifact_digest", sa.String(length=80), nullable=False),
        sa.Column("protocol_version", sa.String(length=40), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("declared_region", sa.String(length=32), nullable=False),
        sa.Column("fixed_price", sa.JSON(), nullable=False),
        sa.Column("public_evidence_references", sa.JSON(), nullable=False),
        sa.Column("conformance_hash", sa.String(length=80), nullable=False),
        sa.Column("projection_hash", sa.String(length=80), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "state IN ('AVAILABLE','SUPERSEDED','REVOKED')",
            name="ck_buyer_proof_adapter_projection_state",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "organization_id", "publication_event_key", name="uq_buyer_proof_projection_event"
        ),
        sa.UniqueConstraint(
            "organization_id", "projection_hash", name="uq_buyer_proof_projection_hash"
        ),
    )
    op.create_index(
        "ix_buyer_proof_adapter_projections_organization_id",
        "buyer_proof_adapter_projections",
        ["organization_id"],
    )
    op.create_table(
        "proof_approvals",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("subject_hash", sa.String(length=80), nullable=False),
        sa.Column("manifest_hash", sa.String(length=80), nullable=False),
        sa.Column("environment_fingerprint", sa.String(length=80), nullable=False),
        sa.Column("decision_hash", sa.String(length=80), nullable=False),
        sa.Column("adapter_projection_hash", sa.String(length=80), nullable=False),
        sa.Column("adapter_digest", sa.String(length=80), nullable=False),
        sa.Column("datahub_owner_urn", sa.String(length=300), nullable=False),
        sa.Column("actor_id", sa.String(length=100), nullable=False),
        sa.Column("actor_role", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_effect_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("actor_role = 'DATA_OWNER'", name="ck_proof_approval_owner_role"),
        sa.CheckConstraint(
            "status IN ('ACTIVE','REVOKED','EXPIRED','CONSUMED','SUPERSEDED')",
            name="ck_proof_approval_status",
        ),
        sa.CheckConstraint(
            "(status = 'REVOKED' AND revoked_at IS NOT NULL) OR "
            "(status <> 'REVOKED' AND revoked_at IS NULL)",
            name="ck_proof_approval_revocation",
        ),
        sa.CheckConstraint(
            "(status = 'CONSUMED' AND consumed_effect_id IS NOT NULL) OR "
            "(status <> 'CONSUMED' AND consumed_effect_id IS NULL)",
            name="ck_proof_approval_consumption",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("organization_id", "subject_hash", name="uq_proof_approval_subject"),
    )
    op.create_index("ix_proof_approvals_organization_id", "proof_approvals", ["organization_id"])
    _enable_forced_rls("buyer_proof_adapter_projections")
    _enable_forced_rls("proof_approvals")


def downgrade() -> None:
    op.drop_index("ix_proof_approvals_organization_id", table_name="proof_approvals")
    op.drop_table("proof_approvals")
    op.drop_index(
        "ix_buyer_proof_adapter_projections_organization_id",
        table_name="buyer_proof_adapter_projections",
    )
    op.drop_table("buyer_proof_adapter_projections")
    op.drop_column("seller_pack_draft_revisions", "proof_adapter")
