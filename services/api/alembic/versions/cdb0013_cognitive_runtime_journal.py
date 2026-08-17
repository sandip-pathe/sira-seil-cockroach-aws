"""add durable cognitive runtime journal

Revision ID: cdb0013
Revises: cdb0012
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "cdb0013"
down_revision: str | None = "cdb0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_DOCUMENT = postgresql.JSONB(astext_type=sa.Text())
_TENANT_EXPRESSION = (
    "organization_id = split_part(current_setting('application_name', true), '.', 2)"
)


def _tenant_security(table: str) -> None:
    op.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "{table}" TO sira_runtime')
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f'CREATE POLICY tenant_isolation ON "{table}" '
        f"FOR ALL TO sira_runtime USING ({_TENANT_EXPRESSION}) "
        f"WITH CHECK ({_TENANT_EXPRESSION})"
    )


def _tenant_column() -> sa.Column[str]:
    return sa.Column("organization_id", sa.String(length=64), nullable=False)


def _timestamps() -> tuple[sa.Column[object], sa.Column[object]]:
    return (
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
    )


def upgrade() -> None:
    op.create_table(
        "cognitive_runs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("principal", sa.String(length=8), nullable=False),
        sa.Column("actor_id", sa.String(length=100), nullable=False),
        sa.Column("conversation_id", sa.String(length=128), nullable=False),
        sa.Column("turn_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("purpose", sa.String(length=100), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("input_hash", sa.String(length=80), nullable=False),
        sa.Column("manifest_hash", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("budget", JSON_DOCUMENT, nullable=False),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        _tenant_column(),
        sa.CheckConstraint("principal IN ('SIRA','SEIL')", name="ck_cognitive_run_principal"),
        sa.CheckConstraint(
            "status IN ('CAPTURED','DECIDING','EXECUTING','WAITING','COMPLETED','FAILED','CANCELLED')",
            name="ck_cognitive_run_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "actor_id", "idempotency_key", name="uq_cognitive_run_idempotency"
        ),
        sa.UniqueConstraint(
            "organization_id", "conversation_id", "turn_id", name="uq_cognitive_run_turn"
        ),
    )
    op.create_index(
        "ix_cognitive_run_conversation",
        "cognitive_runs",
        ["organization_id", "conversation_id", "created_at"],
    )
    op.create_index(
        op.f("ix_cognitive_runs_organization_id"), "cognitive_runs", ["organization_id"]
    )

    op.create_table(
        "cognitive_steps",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("payload", JSON_DOCUMENT, nullable=False),
        sa.Column("payload_hash", sa.String(length=80), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        _tenant_column(),
        sa.CheckConstraint(
            "kind IN ('INPUT','DECISION','TOOL_REQUEST','TOOL_RESULT','CHECKPOINT','OUTPUT','FAILURE')",
            name="ck_cognitive_step_kind",
        ),
        sa.CheckConstraint(
            "status IN ('RECORDED','AUTHORIZED','DENIED','COMPLETED','FAILED')",
            name="ck_cognitive_step_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["cognitive_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "run_id", "sequence", name="uq_cognitive_step_sequence"
        ),
    )
    op.create_index(
        op.f("ix_cognitive_steps_organization_id"), "cognitive_steps", ["organization_id"]
    )

    op.create_table(
        "cognitive_checkpoints",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("run_version", sa.Integer(), nullable=False),
        sa.Column("projection", JSON_DOCUMENT, nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        _tenant_column(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["cognitive_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "run_id", "sequence", name="uq_cognitive_checkpoint_sequence"
        ),
    )
    op.create_index(
        op.f("ix_cognitive_checkpoints_organization_id"),
        "cognitive_checkpoints",
        ["organization_id"],
    )

    op.create_table(
        "cognitive_tool_invocations",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("call_id", sa.String(length=100), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("contract_version", sa.String(length=16), nullable=False),
        sa.Column("risk", sa.String(length=24), nullable=False),
        sa.Column("arguments", JSON_DOCUMENT, nullable=False),
        sa.Column("arguments_hash", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("output", JSON_DOCUMENT, nullable=True),
        sa.Column("output_hash", sa.String(length=80), nullable=True),
        sa.Column("safe_error_code", sa.String(length=80), nullable=True),
        *_timestamps(),
        _tenant_column(),
        sa.CheckConstraint(
            "risk IN ('read','mutation','protected_effect')", name="ck_cognitive_tool_risk"
        ),
        sa.CheckConstraint(
            "status IN ('REQUESTED','AUTHORIZED','RUNNING','COMPLETED','DENIED','FAILED','CANCELLED')",
            name="ck_cognitive_tool_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["cognitive_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "run_id", "call_id", name="uq_cognitive_tool_call"),
    )
    op.create_index(
        op.f("ix_cognitive_tool_invocations_organization_id"),
        "cognitive_tool_invocations",
        ["organization_id"],
    )

    op.create_table(
        "cognitive_user_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("message", sa.String(length=800), nullable=False),
        sa.Column("retryable", sa.Boolean(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        _tenant_column(),
        sa.CheckConstraint(
            "kind IN ('message_received','work_started','clarification_needed','approval_needed',"
            "'work_completed','waiting','could_not_complete')",
            name="ck_cognitive_user_event_kind",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["cognitive_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "run_id", "sequence", name="uq_cognitive_user_event_sequence"
        ),
    )
    op.create_index(
        op.f("ix_cognitive_user_events_organization_id"),
        "cognitive_user_events",
        ["organization_id"],
    )

    for table in (
        "cognitive_runs",
        "cognitive_steps",
        "cognitive_checkpoints",
        "cognitive_tool_invocations",
        "cognitive_user_events",
    ):
        _tenant_security(table)


def downgrade() -> None:
    for table in (
        "cognitive_user_events",
        "cognitive_tool_invocations",
        "cognitive_checkpoints",
        "cognitive_steps",
        "cognitive_runs",
    ):
        op.drop_table(table)
