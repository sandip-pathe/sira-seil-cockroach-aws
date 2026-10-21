"""Persistent public product observations and private seller identity links.

Revision ID: cdb0020
Revises: cdb0019
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "cdb0020"
down_revision: str | None = "cdb0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "marketplace_products",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("identity_key", sa.String(80), unique=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("website", sa.String(1000), nullable=False),
        sa.Column("edition", sa.String(200), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "marketplace_observations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "product_id", sa.String(64), sa.ForeignKey("marketplace_products.id"), nullable=False
        ),
        sa.Column("origin", sa.String(24), nullable=False),
        sa.Column("source_key", sa.String(160), nullable=False),
        sa.Column("content_hash", sa.String(80), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("source_refs", JSONB(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint(
            "product_id", "origin", "source_key", "content_hash", name="uq_marketplace_observation"
        ),
    )
    op.create_index(
        "ix_marketplace_observation_current",
        "marketplace_observations",
        ["product_id", "active", "observed_at"],
    )
    op.create_table(
        "marketplace_seller_links",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "seller_product_id", sa.String(64), sa.ForeignKey("seller_products.id"), nullable=False
        ),
        sa.Column("website", sa.String(1000), nullable=False),
        sa.Column("edition", sa.String(200), nullable=False),
        sa.Column("seller_name", sa.String(200), nullable=False),
        sa.Column(
            "organization_id",
            sa.String(64),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "organization_id", "seller_product_id", name="uq_marketplace_seller_link"
        ),
    )
    op.create_index(
        "ix_marketplace_seller_links_organization_id",
        "marketplace_seller_links",
        ["organization_id"],
    )
    # Only public, source-linked projections enter these shared tables.
    for table in ("marketplace_products", "marketplace_observations"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE {table} TO sira_runtime")
        op.execute(f"GRANT SELECT ON TABLE {table} TO sira_catalog_reader")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE marketplace_seller_links TO sira_runtime"
    )
    op.execute("ALTER TABLE marketplace_seller_links ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE marketplace_seller_links FORCE ROW LEVEL SECURITY")
    tenant = "organization_id = split_part(current_setting('application_name', true), '.', 2)"
    op.execute(
        "CREATE POLICY tenant_isolation ON marketplace_seller_links "
        f"FOR ALL TO sira_runtime USING ({tenant}) WITH CHECK ({tenant})"
    )


def downgrade() -> None:
    op.drop_table("marketplace_seller_links")
    op.drop_table("marketplace_observations")
    op.drop_table("marketplace_products")
