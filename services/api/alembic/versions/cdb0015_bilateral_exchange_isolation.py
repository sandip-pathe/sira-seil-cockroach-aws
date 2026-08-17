"""add append-only bilateral exchange and split service roles

Revision ID: cdb0015
Revises: cdb0014
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "cdb0015"
down_revision: str | None = "cdb0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_DOCUMENT = postgresql.JSONB(astext_type=sa.Text())
_TENANT_EXPRESSION = (
    "organization_id = split_part(current_setting('application_name', true), '.', 2)"
)
_ROLES = (
    "sira_api_runtime",
    "sira_coordinator",
    "sira_evidence_worker",
    "sira_outbox_worker",
    "sira_runtime_sira",
    "sira_runtime_seil",
)


def _tenant_security(table: str, grants: dict[str, str]) -> None:
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


def _tenant_column() -> sa.Column[str]:
    return sa.Column("organization_id", sa.String(length=64), nullable=False)


def upgrade() -> None:
    for role in _ROLES:
        op.execute(f"CREATE ROLE IF NOT EXISTS {role}")

    op.create_table(
        "bilateral_exchange_cases",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("seller_organization_id", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("coordinator_state", JSON_DOCUMENT, nullable=False),
        sa.Column("state_hash", sa.String(length=80), nullable=False),
        sa.Column("last_command_id", sa.String(length=64), nullable=True),
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
        _tenant_column(),
        sa.CheckConstraint(
            "state IN ('CREATED','REQUIREMENT_RELEASED','EVIDENCE_RELEASED','OFFERED',"
            "'COUNTERED','AGREED_PENDING_APPROVAL','APPROVED_FOR_HANDOFF','REJECTED','EXPIRED')",
            name="ck_bilateral_exchange_state",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_bilateral_exchange_state",
        "bilateral_exchange_cases",
        ["organization_id", "state", "updated_at"],
    )
    op.create_index(
        op.f("ix_bilateral_exchange_cases_organization_id"),
        "bilateral_exchange_cases",
        ["organization_id"],
    )

    op.create_table(
        "bilateral_party_commands",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("party", sa.String(length=12), nullable=False),
        sa.Column("actor_id", sa.String(length=100), nullable=False),
        sa.Column("command_type", sa.String(length=40), nullable=False),
        sa.Column("expected_version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("payload", JSON_DOCUMENT, nullable=False),
        sa.Column("payload_hash", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        _tenant_column(),
        sa.CheckConstraint(
            "party IN ('BUYER','SELLER','SYSTEM')", name="ck_bilateral_command_party"
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','APPLIED','REJECTED')", name="ck_bilateral_command_status"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "party", "idempotency_key", name="uq_bilateral_command_idempotency"
        ),
    )
    op.create_index(
        "ix_bilateral_command_case",
        "bilateral_party_commands",
        ["organization_id", "case_id", "created_at"],
    )
    op.create_index(
        op.f("ix_bilateral_party_commands_organization_id"),
        "bilateral_party_commands",
        ["organization_id"],
    )

    op.create_table(
        "bilateral_transitions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("command_id", sa.String(length=64), nullable=False),
        sa.Column("command_organization_id", sa.String(length=64), nullable=False),
        sa.Column("previous_state", sa.String(length=40), nullable=False),
        sa.Column("next_state", sa.String(length=40), nullable=False),
        sa.Column("transition_hash", sa.String(length=80), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        _tenant_column(),
        sa.ForeignKeyConstraint(["case_id"], ["bilateral_exchange_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "case_id", "sequence", name="uq_bilateral_transition_sequence"
        ),
        sa.UniqueConstraint(
            "organization_id", "case_id", "command_id", name="uq_bilateral_transition_command"
        ),
    )
    op.create_index(
        op.f("ix_bilateral_transitions_organization_id"),
        "bilateral_transitions",
        ["organization_id"],
    )

    op.create_table(
        "bilateral_party_projections",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("party", sa.String(length=12), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("released", JSON_DOCUMENT, nullable=False),
        sa.Column("source_command_id", sa.String(length=64), nullable=False),
        sa.Column("projection_hash", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        _tenant_column(),
        sa.CheckConstraint("party IN ('BUYER','SELLER')", name="ck_bilateral_projection_party"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "case_id", "party", "version", name="uq_bilateral_projection_version"
        ),
        sa.UniqueConstraint(
            "organization_id", "projection_hash", name="uq_bilateral_projection_hash"
        ),
    )
    op.create_index(
        "ix_bilateral_projection_latest",
        "bilateral_party_projections",
        ["organization_id", "case_id", "party", "version"],
    )
    op.create_index(
        op.f("ix_bilateral_party_projections_organization_id"),
        "bilateral_party_projections",
        ["organization_id"],
    )

    common = {"sira_runtime": "SELECT, INSERT, UPDATE, DELETE"}
    _tenant_security(
        "bilateral_exchange_cases", {**common, "sira_coordinator": "SELECT, INSERT, UPDATE"}
    )
    _tenant_security(
        "bilateral_party_commands",
        {
            **common,
            "sira_api_runtime": "SELECT, INSERT",
            "sira_coordinator": "SELECT, UPDATE",
        },
    )
    _tenant_security("bilateral_transitions", {**common, "sira_coordinator": "SELECT, INSERT"})
    _tenant_security(
        "bilateral_party_projections",
        {
            **common,
            "sira_api_runtime": "SELECT",
            "sira_coordinator": "SELECT, INSERT",
        },
    )
    # AgentCore runtimes intentionally receive no database grants or credentials.


def downgrade() -> None:
    for table in (
        "bilateral_party_projections",
        "bilateral_transitions",
        "bilateral_party_commands",
        "bilateral_exchange_cases",
    ):
        op.drop_table(table)
    for role in reversed(_ROLES):
        op.execute(f"DROP ROLE IF EXISTS {role}")
