"""add exact provider-neutral bilateral payment handoffs

Revision ID: cdb0018
Revises: cdb0017
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cdb0018"
down_revision: str | None = "cdb0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT = "organization_id = split_part(current_setting('application_name', true), '.', 2)"


def upgrade() -> None:
    op.create_table(
        "bilateral_exchange_handoffs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("offer_hash", sa.String(length=80), nullable=False),
        sa.Column("approval_hash", sa.String(length=80), nullable=False),
        sa.Column("handoff_hash", sa.String(length=80), nullable=False),
        sa.Column("destination_url", sa.Text(), nullable=False),
        sa.Column("recipient", sa.String(length=200), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("reference", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "status IN ('READY','OPENED','EXPIRED','CANCELLED')",
            name="ck_bilateral_handoff_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "case_id", "offer_hash", name="uq_bilateral_handoff_offer"
        ),
        sa.UniqueConstraint(
            "organization_id", "handoff_hash", name="uq_bilateral_handoff_hash"
        ),
    )
    op.create_index(
        "ix_bilateral_handoff_case",
        "bilateral_exchange_handoffs",
        ["organization_id", "case_id", "created_at"],
    )
    op.create_index(
        op.f("ix_bilateral_exchange_handoffs_organization_id"),
        "bilateral_exchange_handoffs",
        ["organization_id"],
    )
    for role, privileges in {
        "sira_runtime": "SELECT, INSERT, UPDATE, DELETE",
        "sira_api_runtime": "SELECT, INSERT, UPDATE",
        "sira_coordinator": "SELECT, INSERT, UPDATE",
    }.items():
        op.execute(
            f'GRANT {privileges} ON TABLE "bilateral_exchange_handoffs" TO {role}'
        )
    op.execute('ALTER TABLE "bilateral_exchange_handoffs" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "bilateral_exchange_handoffs" FORCE ROW LEVEL SECURITY')
    for role in ("sira_runtime", "sira_api_runtime", "sira_coordinator"):
        op.execute(
            f'CREATE POLICY "tenant_isolation_{role}" ON "bilateral_exchange_handoffs" '
            f"FOR ALL TO {role} USING ({_TENANT}) WITH CHECK ({_TENANT})"
        )


def downgrade() -> None:
    op.drop_table("bilateral_exchange_handoffs")
