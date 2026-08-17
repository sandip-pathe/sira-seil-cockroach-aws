"""replace legacy checkout execution with a provider-neutral payment handoff

Revision ID: cdb0012
Revises: cdb0011
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cdb0012"
down_revision: str | None = "cdb0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT_EXPRESSION = (
    "organization_id = split_part(current_setting('application_name', true), '.', 2)"
)


def upgrade() -> None:
    op.create_table(
        "payment_handoffs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("purchase_intent_id", sa.String(length=64), nullable=False),
        sa.Column("approval_request_id", sa.String(length=64), nullable=False),
        sa.Column("intent_hash", sa.String(length=80), nullable=False),
        sa.Column("handoff_hash", sa.String(length=80), nullable=False),
        sa.Column("destination_url", sa.Text(), nullable=False),
        sa.Column("recipient", sa.String(length=200), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("reference", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.CheckConstraint("amount >= 0", name="ck_payment_handoff_amount_nonnegative"),
        sa.CheckConstraint(
            "currency = upper(currency)", name="ck_payment_handoff_currency_upper"
        ),
        sa.CheckConstraint(
            "status IN ('READY','OPENED','EXPIRED','CANCELLED')",
            name="ck_payment_handoff_status",
        ),
        sa.CheckConstraint(
            "(status = 'OPENED' AND opened_at IS NOT NULL) OR "
            "(status <> 'OPENED' AND opened_at IS NULL)",
            name="ck_payment_handoff_opened_state",
        ),
        sa.ForeignKeyConstraint(
            ["approval_request_id"], ["approval_requests.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["purchase_intent_id"], ["purchase_intents.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "purchase_intent_id",
            "approval_request_id",
            name="uq_payment_handoff_approval",
        ),
        sa.UniqueConstraint(
            "organization_id", "handoff_hash", name="uq_payment_handoff_hash"
        ),
    )
    op.create_index(
        "ix_payment_handoff_intent_status",
        "payment_handoffs",
        ["organization_id", "purchase_intent_id", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payment_handoffs_organization_id"),
        "payment_handoffs",
        ["organization_id"],
        unique=False,
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE payment_handoffs TO sira_runtime")
    op.execute("ALTER TABLE payment_handoffs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE payment_handoffs FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON payment_handoffs "
        f"FOR ALL TO sira_runtime USING ({_TENANT_EXPRESSION}) "
        f"WITH CHECK ({_TENANT_EXPRESSION})"
    )
    op.execute("ALTER TABLE result_artifacts DROP COLUMN IF EXISTS receipt_id CASCADE")
    for table in (
        "transaction_transitions",
        "entitlements",
        "payment_attempts",
        "browser_return_bindings",
        "payment_sessions",
        "merchant_orders",
        "prava_shopping_runs",
        "purchase_reversals",
        "receipts",
    ):
        op.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
    op.execute(
        "ALTER TABLE purchase_intents DROP COLUMN IF EXISTS payment_status CASCADE"
    )
    op.execute(
        "ALTER TABLE purchase_intents DROP COLUMN IF EXISTS fulfillment_status CASCADE"
    )


def downgrade() -> None:
    raise RuntimeError(
        "cdb0012 intentionally removes the unshipped checkout prototype; restore from backup "
        "instead of recreating payment-processing tables"
    )
