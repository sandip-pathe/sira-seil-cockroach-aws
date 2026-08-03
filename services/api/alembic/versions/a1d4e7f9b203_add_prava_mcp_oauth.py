"""add encrypted Prava MCP OAuth connections

Revision ID: a1d4e7f9b203
Revises: f8c1d2e3a4b5
Create Date: 2026-08-03 19:20:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1d4e7f9b203"
down_revision: str | None = "f8c1d2e3a4b5"
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
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def _protect(table: str) -> None:
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"CREATE POLICY tenant_access ON {table} AS PERMISSIVE FOR ALL TO PUBLIC "
            "USING (organization_id = NULLIF(current_setting('app.organization_id', true), '')) "
            "WITH CHECK (organization_id = NULLIF(current_setting('app.organization_id', true), ''))"
        )
    )
    op.execute(
        sa.text(
            f"CREATE POLICY tenant_isolation ON {table} AS RESTRICTIVE FOR ALL TO PUBLIC "
            "USING (organization_id = NULLIF(current_setting('app.organization_id', true), '')) "
            "WITH CHECK (organization_id = NULLIF(current_setting('app.organization_id', true), ''))"
        )
    )


def upgrade() -> None:
    op.create_table(
        "prava_mcp_connections",
        sa.Column("id", sa.String(64), primary_key=True),
        *_tenant_columns(),
        sa.Column("actor_id", sa.String(100), nullable=False),
        sa.Column("client_id", sa.String(160), nullable=False),
        sa.Column("encrypted_tokens", sa.Text(), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", name="uq_prava_mcp_connection_org"),
        sa.CheckConstraint(
            "status IN ('CONNECTED','REFRESH_REQUIRED','REVOKED')",
            name="ck_prava_mcp_connection_status",
        ),
    )
    op.create_index(
        "ix_prava_mcp_connections_organization_id",
        "prava_mcp_connections",
        ["organization_id"],
    )
    op.create_table(
        "prava_mcp_authorizations",
        sa.Column("id", sa.String(64), primary_key=True),
        *_tenant_columns(),
        sa.Column("actor_id", sa.String(100), nullable=False),
        sa.Column("state_hash", sa.String(80), nullable=False),
        sa.Column("client_id", sa.String(160), nullable=False),
        sa.Column("encrypted_code_verifier", sa.Text(), nullable=False),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "organization_id", "state_hash", name="uq_prava_mcp_oauth_state"
        ),
    )
    op.create_index(
        "ix_prava_mcp_authorizations_organization_id",
        "prava_mcp_authorizations",
        ["organization_id"],
    )
    _protect("prava_mcp_connections")
    _protect("prava_mcp_authorizations")
    op.create_table(
        "prava_shopping_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        *_tenant_columns(),
        sa.Column("actor_id", sa.String(100), nullable=False),
        sa.Column(
            "purchase_intent_id",
            sa.String(64),
            sa.ForeignKey("purchase_intents.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("product_id", sa.String(200), nullable=False),
        sa.Column("variant_id", sa.String(200), nullable=False),
        sa.Column("merchant", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("checkout_session_id", sa.String(200), nullable=False),
        sa.Column("payment_session_id", sa.String(200), nullable=True),
        sa.Column("payment_url", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("quote_payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("order_id", sa.String(200), nullable=True),
        sa.Column("safe_error_code", sa.String(80), nullable=True),
        sa.UniqueConstraint(
            "organization_id", "checkout_session_id", name="uq_prava_shopping_checkout"
        ),
        sa.CheckConstraint("quantity >= 1", name="ck_prava_shopping_quantity"),
        sa.CheckConstraint("amount > 0", name="ck_prava_shopping_amount"),
        sa.CheckConstraint("currency = upper(currency)", name="ck_prava_shopping_currency"),
        sa.CheckConstraint(
            "status IN ('QUOTED','AWAITING_APPROVAL','QUEUED','RUNNING','PAID','FAILED')",
            name="ck_prava_shopping_status",
        ),
    )
    op.create_index(
        "ix_prava_shopping_runs_organization_id",
        "prava_shopping_runs",
        ["organization_id"],
    )
    _protect("prava_shopping_runs")


def downgrade() -> None:
    op.drop_index(
        "ix_prava_shopping_runs_organization_id", table_name="prava_shopping_runs"
    )
    op.drop_table("prava_shopping_runs")
    op.drop_index(
        "ix_prava_mcp_authorizations_organization_id",
        table_name="prava_mcp_authorizations",
    )
    op.drop_table("prava_mcp_authorizations")
    op.drop_index(
        "ix_prava_mcp_connections_organization_id",
        table_name="prava_mcp_connections",
    )
    op.drop_table("prava_mcp_connections")
