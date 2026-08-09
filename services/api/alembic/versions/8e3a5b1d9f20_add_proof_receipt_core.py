"""add immutable proof receipt core

Revision ID: 8e3a5b1d9f20
Revises: 7d2f4a9c8e10
Create Date: 2026-08-10 04:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8e3a5b1d9f20"
down_revision: str | None = "7d2f4a9c8e10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_POLICY_EXPRESSION = (
    "organization_id = NULLIF(current_setting('app.organization_id', true), '')"
)


def upgrade() -> None:
    op.create_table(
        "proof_receipt_cores",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("approval_subject_hash", sa.String(length=80), nullable=False),
        sa.Column("verified_adapter_digest", sa.String(length=80), nullable=False),
        sa.Column("route_state_at_verification", sa.String(length=32), nullable=False),
        sa.Column("datahub_anchor_urn", sa.String(length=300), nullable=False),
        sa.Column("datahub_projection_hash", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("core_hash", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "route_state_at_verification IN ('ACTIVE_VERIFIED','ROLLBACK_VERIFIED')",
            name="ck_proof_receipt_route_state",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("organization_id", "core_hash", name="uq_proof_receipt_core_hash"),
        sa.UniqueConstraint(
            "organization_id",
            "approval_subject_hash",
            name="uq_proof_receipt_approval_subject",
        ),
    )
    op.create_index(
        "ix_proof_receipt_cores_organization_id",
        "proof_receipt_cores",
        ["organization_id"],
    )
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        op.execute("ALTER TABLE proof_receipt_cores ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE proof_receipt_cores FORCE ROW LEVEL SECURITY")
        op.execute(
            sa.text(
                "CREATE POLICY tenant_access ON proof_receipt_cores AS PERMISSIVE "
                "FOR ALL TO PUBLIC "
                f"USING ({TENANT_POLICY_EXPRESSION}) WITH CHECK ({TENANT_POLICY_EXPRESSION})"
            )
        )
        op.execute(
            sa.text(
                "CREATE POLICY tenant_isolation ON proof_receipt_cores AS RESTRICTIVE "
                "FOR ALL TO PUBLIC "
                f"USING ({TENANT_POLICY_EXPRESSION}) WITH CHECK ({TENANT_POLICY_EXPRESSION})"
            )
        )
        op.execute(
            """
            CREATE FUNCTION reject_proof_receipt_core_mutation() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'proof receipt core is immutable';
            END;
            $$
            """
        )
        op.execute(
            """
            CREATE TRIGGER proof_receipt_core_insert_only
            BEFORE UPDATE OR DELETE ON proof_receipt_cores
            FOR EACH ROW EXECUTE FUNCTION reject_proof_receipt_core_mutation()
            """
        )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        op.execute("DROP TRIGGER proof_receipt_core_insert_only ON proof_receipt_cores")
        op.execute("DROP FUNCTION reject_proof_receipt_core_mutation()")
    op.drop_index("ix_proof_receipt_cores_organization_id", table_name="proof_receipt_cores")
    op.drop_table("proof_receipt_cores")
