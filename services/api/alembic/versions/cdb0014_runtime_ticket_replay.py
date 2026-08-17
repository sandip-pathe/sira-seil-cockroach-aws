"""add single-use runtime ticket replay guard

Revision ID: cdb0014
Revises: cdb0013
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cdb0014"
down_revision: str | None = "cdb0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT_EXPRESSION = (
    "organization_id = split_part(current_setting('application_name', true), '.', 2)"
)


def upgrade() -> None:
    op.create_table(
        "runtime_ticket_uses",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("ticket_id", sa.String(length=128), nullable=False),
        sa.Column("nonce_hash", sa.String(length=80), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "consumed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "ticket_id", "nonce_hash", name="uq_runtime_ticket_use"
        ),
    )
    op.create_index(
        "ix_runtime_ticket_expiry",
        "runtime_ticket_uses",
        ["organization_id", "expires_at"],
    )
    op.create_index(
        op.f("ix_runtime_ticket_uses_organization_id"),
        "runtime_ticket_uses",
        ["organization_id"],
    )
    op.execute("GRANT SELECT, INSERT, DELETE ON TABLE runtime_ticket_uses TO sira_runtime")
    op.execute("ALTER TABLE runtime_ticket_uses ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE runtime_ticket_uses FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON runtime_ticket_uses "
        f"FOR ALL TO sira_runtime USING ({_TENANT_EXPRESSION}) "
        f"WITH CHECK ({_TENANT_EXPRESSION})"
    )


def downgrade() -> None:
    op.drop_table("runtime_ticket_uses")
