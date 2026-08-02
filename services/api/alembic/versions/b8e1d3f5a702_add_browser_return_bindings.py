"""add safe single-use browser return bindings

Revision ID: b8e1d3f5a702
Revises: f4b7c9d2e601
Create Date: 2026-08-02 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8e1d3f5a702"
down_revision: str | None = "f4b7c9d2e601"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "browser_return_bindings",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("purchase_intent_id", sa.String(64), nullable=False),
        sa.Column("payment_session_id", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(100), nullable=False),
        sa.Column("state_hash", sa.String(80), nullable=False),
        sa.Column("provider_session_hash", sa.String(80), nullable=False),
        sa.Column("return_url_hash", sa.String(80), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["payment_session_id"], ["payment_sessions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["purchase_intent_id"], ["purchase_intents.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "state_hash", name="uq_browser_return_state_hash"),
        sa.UniqueConstraint(
            "organization_id",
            "payment_session_id",
            name="uq_browser_return_payment_session",
        ),
    )
    op.create_index(
        op.f("ix_browser_return_bindings_organization_id"),
        "browser_return_bindings",
        ["organization_id"],
        unique=False,
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text('ALTER TABLE "browser_return_bindings" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "browser_return_bindings" FORCE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(
                'CREATE POLICY tenant_isolation ON "browser_return_bindings" '
                "USING (organization_id = current_setting('app.organization_id', true)) "
                "WITH CHECK (organization_id = current_setting('app.organization_id', true))"
            )
        )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_browser_return_bindings_organization_id"),
        table_name="browser_return_bindings",
    )
    op.drop_table("browser_return_bindings")
