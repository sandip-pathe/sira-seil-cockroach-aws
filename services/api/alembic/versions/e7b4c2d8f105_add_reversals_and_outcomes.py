"""add reversal and measured outcome records

Revision ID: e7b4c2d8f105
Revises: d9e2f7a1c604
Create Date: 2026-08-02 17:15:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7b4c2d8f105"  # pragma: allowlist secret
down_revision: str | None = "d9e2f7a1c604"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tenant_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column(
            "organization_id",
            sa.String(64),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def _protect(table_name: str) -> None:
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return
    table = connection.dialect.identifier_preparer.quote(table_name)
    expression = "organization_id = NULLIF(current_setting('app.organization_id', true), '')"
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"CREATE POLICY tenant_access ON {table} AS PERMISSIVE FOR ALL TO PUBLIC "
            f"USING ({expression}) WITH CHECK ({expression})"
        )
    )
    op.execute(
        sa.text(
            f"CREATE POLICY tenant_isolation ON {table} AS RESTRICTIVE FOR ALL TO PUBLIC "
            f"USING ({expression}) WITH CHECK ({expression})"
        )
    )


def upgrade() -> None:
    op.create_table(
        "purchase_reversals",
        sa.Column("id", sa.String(64), primary_key=True),
        *_tenant_columns(),
        sa.Column(
            "purchase_intent_id",
            sa.String(64),
            sa.ForeignKey("purchase_intents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("intent_hash", sa.String(80), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("requested_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("refunded_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("merchant_order_id", sa.String(160), nullable=False),
        sa.Column("provider_reference", sa.String(160), nullable=True),
        sa.Column("provider_adapter_id", sa.String(100), nullable=False),
        sa.Column("provider_confirmed", sa.Boolean(), nullable=False),
        sa.Column("reason_code", sa.String(80), nullable=False),
        sa.Column("reason_hash", sa.String(80), nullable=False),
        sa.Column("requested_by_actor_id", sa.String(100), nullable=False),
        sa.Column("safe_error_code", sa.String(80), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('CANCELLATION','REFUND')", name="ck_reversal_kind"),
        sa.CheckConstraint(
            "status IN ('REQUESTED','PROVIDER_PENDING','PARTIALLY_REFUNDED','REFUNDED',"
            "'REJECTED','FAILED_RETRYABLE','COMPENSATION_REQUIRED','COMPENSATED','CANCELLED')",
            name="ck_reversal_status",
        ),
        sa.CheckConstraint("requested_amount > 0", name="ck_reversal_requested_positive"),
        sa.CheckConstraint("refunded_amount >= 0", name="ck_reversal_refunded_nonnegative"),
        sa.CheckConstraint(
            "refunded_amount <= requested_amount", name="ck_reversal_refunded_bounded"
        ),
        sa.CheckConstraint("currency = upper(currency)", name="ck_reversal_currency_upper"),
        sa.UniqueConstraint(
            "organization_id",
            "purchase_intent_id",
            "reason_hash",
            name="uq_reversal_request",
        ),
    )
    op.create_index(
        "ix_purchase_reversals_organization_id", "purchase_reversals", ["organization_id"]
    )
    op.create_index(
        "ix_reversal_intent_status",
        "purchase_reversals",
        ["organization_id", "purchase_intent_id", "status"],
    )

    op.create_table(
        "outcome_checkpoints",
        sa.Column("id", sa.String(64), primary_key=True),
        *_tenant_columns(),
        sa.Column(
            "purchase_intent_id",
            sa.String(64),
            sa.ForeignKey("purchase_intents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "decision_id",
            sa.String(64),
            sa.ForeignKey("decision_records.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("decision_hash", sa.String(80), nullable=False),
        sa.Column("solution_plan_id", sa.String(64), nullable=False),
        sa.Column("metric_id", sa.String(128), nullable=False),
        sa.Column("target_value", sa.Numeric(30, 6), nullable=False),
        sa.Column("target_operator", sa.String(8), nullable=False),
        sa.Column("observed_value", sa.Numeric(30, 6), nullable=False),
        sa.Column("checkpoint_days", sa.Integer(), nullable=False),
        sa.Column("measurement_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checkpoint_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("source_class", sa.String(40), nullable=False),
        sa.Column("source_reference_hash", sa.String(80), nullable=False),
        sa.Column("recorded_by_actor_id", sa.String(100), nullable=False),
        sa.Column("checkpoint_hash", sa.String(80), nullable=False),
        sa.Column("preference_proposal", sa.JSON(), nullable=True),
        sa.CheckConstraint("checkpoint_days BETWEEN 1 AND 365", name="ck_outcome_checkpoint_days"),
        sa.CheckConstraint("target_operator IN ('gte','lte')", name="ck_outcome_target_operator"),
        sa.CheckConstraint(
            "state IN ('MEASURING','ACHIEVED','NOT_ACHIEVED','INCONCLUSIVE')",
            name="ck_outcome_state",
        ),
        sa.CheckConstraint(
            "source_class IN ('SYSTEM_OBSERVATION','HUMAN_ATTESTATION','PROVIDER_REPORT')",
            name="ck_outcome_source_class",
        ),
        sa.UniqueConstraint(
            "organization_id", "checkpoint_hash", name="uq_outcome_checkpoint_hash"
        ),
    )
    op.create_index(
        "ix_outcome_checkpoints_organization_id",
        "outcome_checkpoints",
        ["organization_id"],
    )
    op.create_index(
        "ix_outcome_intent_metric",
        "outcome_checkpoints",
        ["organization_id", "purchase_intent_id", "metric_id", "observed_at"],
    )
    _protect("purchase_reversals")
    _protect("outcome_checkpoints")


def downgrade() -> None:
    op.drop_index("ix_outcome_intent_metric", table_name="outcome_checkpoints")
    op.drop_index("ix_outcome_checkpoints_organization_id", table_name="outcome_checkpoints")
    op.drop_table("outcome_checkpoints")
    op.drop_index("ix_reversal_intent_status", table_name="purchase_reversals")
    op.drop_index("ix_purchase_reversals_organization_id", table_name="purchase_reversals")
    op.drop_table("purchase_reversals")
