"""add exact disclosure envelopes and immutable offer versions

Revision ID: cdb0017
Revises: cdb0016
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "cdb0017"
down_revision: str | None = "cdb0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_DOCUMENT = postgresql.JSONB(astext_type=sa.Text())
_TENANT_EXPRESSION = (
    "organization_id = split_part(current_setting('application_name', true), '.', 2)"
)


def _tenant_column() -> sa.Column[str]:
    return sa.Column("organization_id", sa.String(length=64), nullable=False)


def _secure(table: str, grants: dict[str, str]) -> None:
    for role, privileges in grants.items():
        op.execute(f'GRANT {privileges} ON TABLE "{table}" TO {role}')
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    for role in grants:
        op.execute(
            f'CREATE POLICY "tenant_isolation_{role}" ON "{table}" '
            f"FOR ALL TO {role} USING ({_TENANT_EXPRESSION}) "
            f"WITH CHECK ({_TENANT_EXPRESSION})"
        )


def upgrade() -> None:
    op.create_table(
        "bilateral_release_manifests",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("owner_party", sa.String(length=12), nullable=False),
        sa.Column("recipient_party", sa.String(length=12), nullable=False),
        sa.Column("purpose", sa.String(length=240), nullable=False),
        sa.Column("payload", JSON_DOCUMENT, nullable=False),
        sa.Column("approved_payload_hash", sa.String(length=80), nullable=False),
        sa.Column("approval_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("manifest_hash", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        _tenant_column(),
        sa.CheckConstraint(
            "owner_party IN ('BUYER','SELLER') AND recipient_party IN ('BUYER','SELLER') "
            "AND owner_party <> recipient_party",
            name="ck_release_manifest_parties",
        ),
        sa.CheckConstraint("status IN ('ACTIVE','REVOKED')", name="ck_release_manifest_status"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "manifest_hash", name="uq_release_manifest_hash"),
    )
    op.create_index(
        "ix_release_manifest_case",
        "bilateral_release_manifests",
        ["organization_id", "case_id", "created_at"],
    )
    op.create_index(
        op.f("ix_bilateral_release_manifests_organization_id"),
        "bilateral_release_manifests",
        ["organization_id"],
    )

    op.create_table(
        "bilateral_exchange_envelopes",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("sender_party", sa.String(length=12), nullable=False),
        sa.Column("recipient_party", sa.String(length=12), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("causation_id", sa.String(length=64), nullable=False),
        sa.Column("manifest_hash", sa.String(length=80), nullable=False),
        sa.Column("payload", JSON_DOCUMENT, nullable=False),
        sa.Column("payload_hash", sa.String(length=80), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        _tenant_column(),
        sa.CheckConstraint(
            "sender_party IN ('BUYER','SELLER') AND recipient_party IN ('BUYER','SELLER') "
            "AND sender_party <> recipient_party",
            name="ck_exchange_envelope_parties",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "case_id", "sender_party", "sequence",
            name="uq_exchange_envelope_sequence",
        ),
        sa.UniqueConstraint("organization_id", "payload_hash", name="uq_exchange_envelope_hash"),
    )
    op.create_index(
        "ix_exchange_envelope_recipient",
        "bilateral_exchange_envelopes",
        ["organization_id", "case_id", "recipient_party"],
    )
    op.create_index(
        op.f("ix_bilateral_exchange_envelopes_organization_id"),
        "bilateral_exchange_envelopes",
        ["organization_id"],
    )

    op.create_table(
        "bilateral_exchange_receipts",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("envelope_id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("recipient_party", sa.String(length=12), nullable=False),
        sa.Column("envelope_hash", sa.String(length=80), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        _tenant_column(),
        sa.CheckConstraint(
            "recipient_party IN ('BUYER','SELLER')", name="ck_exchange_receipt_party"
        ),
        sa.ForeignKeyConstraint(
            ["envelope_id"], ["bilateral_exchange_envelopes.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "envelope_id", name="uq_exchange_receipt_envelope"),
    )
    op.create_index(
        op.f("ix_bilateral_exchange_receipts_organization_id"),
        "bilateral_exchange_receipts",
        ["organization_id"],
    )

    op.create_table(
        "bilateral_offer_versions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("proposer_party", sa.String(length=12), nullable=False),
        sa.Column("recipient_party", sa.String(length=12), nullable=False),
        sa.Column("predecessor_hash", sa.String(length=80), nullable=True),
        sa.Column("terms", JSON_DOCUMENT, nullable=False),
        sa.Column("offer_hash", sa.String(length=80), nullable=False),
        sa.Column("approval_status", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        _tenant_column(),
        sa.CheckConstraint(
            "proposer_party IN ('BUYER','SELLER') AND recipient_party IN ('BUYER','SELLER') "
            "AND proposer_party <> recipient_party",
            name="ck_offer_version_parties",
        ),
        sa.CheckConstraint("version >= 1", name="ck_offer_version_positive"),
        sa.CheckConstraint(
            "approval_status IN ('PENDING','APPROVED','REJECTED','REVOKED','SUPERSEDED')",
            name="ck_offer_version_approval_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "case_id", "version", name="uq_offer_case_version"),
        sa.UniqueConstraint("organization_id", "offer_hash", name="uq_offer_hash"),
    )
    op.create_index(
        "ix_offer_case_latest",
        "bilateral_offer_versions",
        ["organization_id", "case_id", "version"],
    )
    op.create_index(
        op.f("ix_bilateral_offer_versions_organization_id"),
        "bilateral_offer_versions",
        ["organization_id"],
    )

    op.create_table(
        "bilateral_offer_approvals",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("offer_hash", sa.String(length=80), nullable=False),
        sa.Column("approver_id", sa.String(length=100), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approval_hash", sa.String(length=80), nullable=False),
        _tenant_column(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "case_id", "offer_hash", name="uq_offer_approval"),
        sa.UniqueConstraint("organization_id", "approval_hash", name="uq_offer_approval_hash"),
    )
    op.create_index(
        op.f("ix_bilateral_offer_approvals_organization_id"),
        "bilateral_offer_approvals",
        ["organization_id"],
    )

    coordinator = {"sira_runtime": "SELECT, INSERT, UPDATE, DELETE", "sira_coordinator": "SELECT, INSERT, UPDATE"}
    _secure("bilateral_release_manifests", coordinator)
    _secure("bilateral_exchange_envelopes", coordinator)
    _secure("bilateral_exchange_receipts", coordinator)
    _secure("bilateral_offer_versions", coordinator)
    _secure("bilateral_offer_approvals", coordinator)
    # AgentCore runtimes still receive no database grants or credentials.


def downgrade() -> None:
    for table in (
        "bilateral_offer_approvals",
        "bilateral_offer_versions",
        "bilateral_exchange_receipts",
        "bilateral_exchange_envelopes",
        "bilateral_release_manifests",
    ):
        op.drop_table(table)
