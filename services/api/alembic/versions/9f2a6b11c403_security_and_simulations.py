"""security authority records and deterministic simulations

Revision ID: 9f2a6b11c403
Revises: 744f4ab939df
Create Date: 2026-08-02 04:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9f2a6b11c403"
down_revision: str | None = "744f4ab939df"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_simulation_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(sa.text('ALTER TABLE "decision_simulations" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text('ALTER TABLE "decision_simulations" FORCE ROW LEVEL SECURITY'))
    op.execute(
        sa.text(
            'CREATE POLICY tenant_isolation ON "decision_simulations" '
            "USING (organization_id = current_setting('app.organization_id', true)) "
            "WITH CHECK (organization_id = current_setting('app.organization_id', true))"
        )
    )


def upgrade() -> None:
    with op.batch_alter_table("engagements") as batch:
        batch.add_column(sa.Column("buyer_consent_actor_id", sa.String(100), nullable=True))
        batch.add_column(sa.Column("seller_consent_actor_id", sa.String(100), nullable=True))

    with op.batch_alter_table("purchase_intents") as batch:
        batch.create_unique_constraint(
            "uq_purchase_intent_business_lock",
            ["organization_id", "decision_id", "solution_plan_id", "quote_id"],
        )

    op.drop_index("uq_open_payment_attempt", table_name="payment_attempts")
    op.drop_index("uq_charged_or_uncertain_intent", table_name="payment_attempts")
    op.create_index(
        "uq_open_payment_attempt",
        "payment_attempts",
        ["purchase_intent_id"],
        unique=True,
        postgresql_where=sa.text("closed_at IS NULL"),
        sqlite_where=sa.text("closed_at IS NULL"),
    )
    op.create_index(
        "uq_charged_or_uncertain_intent",
        "payment_attempts",
        ["purchase_intent_id"],
        unique=True,
        postgresql_where=sa.text("merchant_outcome IN ('APPROVED','UNKNOWN')"),
        sqlite_where=sa.text("merchant_outcome IN ('APPROVED','UNKNOWN')"),
    )

    op.create_table(
        "decision_simulations",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("decision_id", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(100), nullable=False),
        sa.Column("input_hash", sa.String(80), nullable=False),
        sa.Column("input_payload", sa.JSON(), nullable=False),
        sa.Column("result_hash", sa.String(80), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=False),
        sa.Column("authoritative", sa.Boolean(), nullable=False),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["decision_id"], ["decision_records.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "decision_id",
            "actor_id",
            "input_hash",
            name="uq_simulation_input",
        ),
    )
    op.create_index(
        op.f("ix_decision_simulations_organization_id"),
        "decision_simulations",
        ["organization_id"],
        unique=False,
    )
    _enable_simulation_rls()


def downgrade() -> None:
    op.drop_index(
        op.f("ix_decision_simulations_organization_id"),
        table_name="decision_simulations",
    )
    op.drop_table("decision_simulations")

    op.drop_index("uq_charged_or_uncertain_intent", table_name="payment_attempts")
    op.drop_index("uq_open_payment_attempt", table_name="payment_attempts")
    op.create_index(
        "uq_charged_or_uncertain_intent",
        "payment_attempts",
        ["purchase_intent_id"],
        unique=True,
        postgresql_where=sa.text("merchant_outcome IN ('approved','unknown')"),
        sqlite_where=sa.text("merchant_outcome IN ('approved','unknown')"),
    )
    op.create_index(
        "uq_open_payment_attempt",
        "payment_attempts",
        ["purchase_intent_id"],
        unique=True,
        postgresql_where=sa.text("closed_at IS NULL"),
        sqlite_where=sa.text("closed_at IS NULL"),
    )

    with op.batch_alter_table("purchase_intents") as batch:
        batch.drop_constraint("uq_purchase_intent_business_lock", type_="unique")
    with op.batch_alter_table("engagements") as batch:
        batch.drop_column("seller_consent_actor_id")
        batch.drop_column("buyer_consent_actor_id")
