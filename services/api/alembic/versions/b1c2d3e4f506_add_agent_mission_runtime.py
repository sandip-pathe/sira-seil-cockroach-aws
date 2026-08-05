"""add canonical agent mission runtime

Revision ID: b1c2d3e4f506
Revises: f8c1d2e3a4b5
Create Date: 2026-08-05 12:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b1c2d3e4f506"
down_revision: str | None = "f8c1d2e3a4b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_DOCUMENT = postgresql.JSONB(astext_type=sa.Text())
TENANT_POLICY_EXPRESSION = (
    "organization_id = NULLIF(current_setting('app.organization_id', true), '')"
)

TABLES = (
    "agent_missions",
    "agent_mission_events",
    "agent_mission_tasks",
    "agent_mission_artifacts",
    "agent_mission_checkpoints",
    "agent_capability_grants",
    "agent_effects",
    "agent_experiments",
)


def _tenant_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column(
            "organization_id",
            sa.String(length=64),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
    )


def _timestamp_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def upgrade() -> None:
    op.create_table(
        "agent_missions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        *_tenant_columns(),
        sa.Column("actor_id", sa.String(length=100), nullable=False),
        sa.Column("mode", sa.String(length=12), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("budget", JSON_DOCUMENT, nullable=False),
        sa.Column("plan", JSON_DOCUMENT, nullable=False),
        sa.Column("world_model", JSON_DOCUMENT, nullable=False),
        sa.Column("current_checkpoint_id", sa.String(length=64), nullable=True),
        sa.Column("stop_reason", sa.String(length=120), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        *_timestamp_columns(),
        sa.CheckConstraint("mode IN ('SIRA','SEIL')", name="ck_agent_mission_mode"),
        sa.CheckConstraint(
            "state IN ('CREATED','ORIENTING','PLANNING','EXPLORING','EXPERIMENTING',"
            "'SYNTHESIZING','PROPOSING','AWAITING_AUTHORITY','EXECUTING','VERIFYING',"
            "'MONITORING','COMPLETED','PAUSED','BLOCKED','FAILED','CANCELLED')",
            name="ck_agent_mission_state",
        ),
    )
    op.create_index(
        "ix_agent_mission_actor_state",
        "agent_missions",
        ["organization_id", "actor_id", "state"],
    )

    op.create_table(
        "agent_mission_events",
        sa.Column("id", sa.String(length=64), primary_key=True),
        *_tenant_columns(),
        sa.Column(
            "mission_id",
            sa.String(length=64),
            sa.ForeignKey("agent_missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("event_key", sa.String(length=160), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=100), nullable=False),
        sa.Column("payload", JSON_DOCUMENT, nullable=False),
        sa.Column("payload_hash", sa.String(length=80), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "organization_id", "mission_id", "sequence", name="uq_agent_mission_event_sequence"
        ),
        sa.UniqueConstraint("organization_id", "event_key", name="uq_agent_mission_event_key"),
    )
    op.create_index(
        "ix_agent_mission_event_stream",
        "agent_mission_events",
        ["organization_id", "mission_id", "sequence"],
    )

    op.create_table(
        "agent_mission_tasks",
        sa.Column("id", sa.String(length=64), primary_key=True),
        *_tenant_columns(),
        sa.Column(
            "mission_id",
            sa.String(length=64),
            sa.ForeignKey("agent_missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_task_id",
            sa.String(length=64),
            sa.ForeignKey("agent_mission_tasks.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("owner_type", sa.String(length=24), nullable=False),
        sa.Column("assigned_role", sa.String(length=80), nullable=True),
        sa.Column("input_payload", JSON_DOCUMENT, nullable=False),
        sa.Column("budget", JSON_DOCUMENT, nullable=False),
        sa.Column("output_artifact_id", sa.String(length=64), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("safe_error_code", sa.String(length=80), nullable=True),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "status IN ('PENDING','RUNNING','WAITING','COMPLETED','FAILED','CANCELLED')",
            name="ck_agent_mission_task_status",
        ),
        sa.CheckConstraint(
            "owner_type IN ('ROOT_AGENT','SUBAGENT','HUMAN','SYSTEM')",
            name="ck_agent_mission_task_owner",
        ),
    )
    op.create_index(
        "ix_agent_mission_task_queue",
        "agent_mission_tasks",
        ["organization_id", "mission_id", "status"],
    )

    op.create_table(
        "agent_mission_artifacts",
        sa.Column("id", sa.String(length=64), primary_key=True),
        *_tenant_columns(),
        sa.Column(
            "mission_id",
            sa.String(length=64),
            sa.ForeignKey("agent_missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            sa.String(length=64),
            sa.ForeignKey("agent_mission_tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("kind", sa.String(length=48), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("authority", sa.String(length=32), nullable=False),
        sa.Column("payload", JSON_DOCUMENT, nullable=False),
        sa.Column("source_refs", JSON_DOCUMENT, nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=False),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "status IN ('DRAFT','READY','STALE','FAILED','SUPERSEDED')",
            name="ck_agent_mission_artifact_status",
        ),
        sa.CheckConstraint(
            "authority IN ('OBSERVED','VERIFIED','INFERRED','SELLER_ASSERTED','USER_ASSERTED')",
            name="ck_agent_mission_artifact_authority",
        ),
        sa.UniqueConstraint(
            "organization_id", "mission_id", "content_hash", name="uq_agent_artifact_hash"
        ),
    )
    op.create_index(
        "ix_agent_mission_artifact_kind",
        "agent_mission_artifacts",
        ["organization_id", "mission_id", "kind"],
    )

    op.create_table(
        "agent_mission_checkpoints",
        sa.Column("id", sa.String(length=64), primary_key=True),
        *_tenant_columns(),
        sa.Column(
            "mission_id",
            sa.String(length=64),
            sa.ForeignKey("agent_missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("mission_version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("projection", JSON_DOCUMENT, nullable=False),
        sa.Column("unresolved_task_ids", JSON_DOCUMENT, nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "organization_id", "mission_id", "sequence", name="uq_agent_checkpoint_sequence"
        ),
    )

    op.create_table(
        "agent_capability_grants",
        sa.Column("id", sa.String(length=64), primary_key=True),
        *_tenant_columns(),
        sa.Column(
            "mission_id",
            sa.String(length=64),
            sa.ForeignKey("agent_missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subject_type", sa.String(length=24), nullable=False),
        sa.Column("subject_id", sa.String(length=100), nullable=False),
        sa.Column("capability", sa.String(length=100), nullable=False),
        sa.Column("scope", JSON_DOCUMENT, nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("granted_by", sa.String(length=100), nullable=False),
        sa.Column("grant_hash", sa.String(length=80), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("uses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "subject_type IN ('ROOT_AGENT','SUBAGENT','USER','SYSTEM')",
            name="ck_agent_capability_subject",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','REVOKED','EXPIRED','CONSUMED')",
            name="ck_agent_capability_status",
        ),
        sa.CheckConstraint(
            "max_uses > 0 AND uses >= 0 AND uses <= max_uses", name="ck_agent_grant_uses"
        ),
        sa.UniqueConstraint("organization_id", "grant_hash", name="uq_agent_capability_hash"),
    )

    op.create_table(
        "agent_effects",
        sa.Column("id", sa.String(length=64), primary_key=True),
        *_tenant_columns(),
        sa.Column(
            "mission_id",
            sa.String(length=64),
            sa.ForeignKey("agent_missions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            sa.String(length=64),
            sa.ForeignKey("agent_mission_tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "capability_grant_id",
            sa.String(length=64),
            sa.ForeignKey("agent_capability_grants.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("effect_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("request_payload", JSON_DOCUMENT, nullable=False),
        sa.Column("request_hash", sa.String(length=80), nullable=False),
        sa.Column("approval_reference", sa.String(length=128), nullable=True),
        sa.Column("provider_reference", sa.String(length=160), nullable=True),
        sa.Column(
            "result_artifact_id",
            sa.String(length=64),
            sa.ForeignKey("agent_mission_artifacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("safe_error_code", sa.String(length=80), nullable=True),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "status IN ('PROPOSED','AUTHORIZED','DISPATCHING','ACKNOWLEDGED','VERIFIED',"
            "'UNCERTAIN','RECONCILING','COMPENSATING','FAILED','CANCELLED')",
            name="ck_agent_effect_status",
        ),
        sa.UniqueConstraint(
            "organization_id", "mission_id", "idempotency_key", name="uq_agent_effect_key"
        ),
    )

    op.create_table(
        "agent_experiments",
        sa.Column("id", sa.String(length=64), primary_key=True),
        *_tenant_columns(),
        sa.Column(
            "mission_id",
            sa.String(length=64),
            sa.ForeignKey("agent_missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            sa.String(length=64),
            sa.ForeignKey("agent_mission_tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("candidate_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("procedure", JSON_DOCUMENT, nullable=False),
        sa.Column("environment", JSON_DOCUMENT, nullable=False),
        sa.Column("success_signals", JSON_DOCUMENT, nullable=False),
        sa.Column("observations", JSON_DOCUMENT, nullable=False),
        sa.Column("limitations", JSON_DOCUMENT, nullable=False),
        sa.Column("replay_spec", JSON_DOCUMENT, nullable=False),
        sa.Column("cost", JSON_DOCUMENT, nullable=False),
        sa.Column(
            "result_artifact_id",
            sa.String(length=64),
            sa.ForeignKey("agent_mission_artifacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "status IN ('PLANNED','PROVISIONING','RUNNING','COMPLETED','FAILED','CANCELLED')",
            name="ck_agent_experiment_status",
        ),
        sa.UniqueConstraint(
            "organization_id", "mission_id", "content_hash", name="uq_agent_experiment_hash"
        ),
    )

    if op.get_bind().dialect.name == "postgresql":
        for table_name in TABLES:
            op.execute(sa.text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"))
            op.execute(sa.text(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY"))
            op.execute(
                sa.text(
                    f"CREATE POLICY tenant_access ON {table_name} AS PERMISSIVE FOR ALL TO PUBLIC "
                    f"USING ({TENANT_POLICY_EXPRESSION}) WITH CHECK ({TENANT_POLICY_EXPRESSION})"
                )
            )
            op.execute(
                sa.text(
                    f"CREATE POLICY tenant_isolation ON {table_name} AS RESTRICTIVE FOR ALL TO PUBLIC "
                    f"USING ({TENANT_POLICY_EXPRESSION}) WITH CHECK ({TENANT_POLICY_EXPRESSION})"
                )
            )


def downgrade() -> None:
    for table_name in reversed(TABLES):
        op.drop_table(table_name)
