"""make seller responses readable by both verified parties

Revision ID: cdb0006
Revises: cdb0005
Create Date: 2026-08-13 08:10:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "cdb0006"
down_revision: str | None = "cdb0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT = "split_part(current_setting('application_name', true), '.', 2)"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE marketplace_seller_responses "
        "ADD COLUMN IF NOT EXISTS buyer_organization_id STRING"
    )
    op.execute(
        "ALTER TABLE marketplace_seller_responses "
        "ADD COLUMN IF NOT EXISTS seller_organization_id STRING"
    )
    op.execute(
        "UPDATE marketplace_seller_responses AS response SET "
        "buyer_organization_id = engagement.buyer_organization_id, "
        "seller_organization_id = engagement.seller_organization_id "
        "FROM marketplace_engagements AS engagement "
        "WHERE response.engagement_id = engagement.id AND "
        "(response.buyer_organization_id IS NULL OR "
        "response.seller_organization_id IS NULL)"
    )
    op.alter_column("marketplace_seller_responses", "buyer_organization_id", nullable=False)
    op.alter_column("marketplace_seller_responses", "seller_organization_id", nullable=False)
    op.execute(
        "ALTER TABLE marketplace_seller_responses ADD CONSTRAINT IF NOT EXISTS "
        "fk_marketplace_response_buyer FOREIGN KEY (buyer_organization_id) "
        "REFERENCES organizations (id) ON DELETE RESTRICT"
    )
    op.execute(
        "ALTER TABLE marketplace_seller_responses ADD CONSTRAINT IF NOT EXISTS "
        "fk_marketplace_response_seller FOREIGN KEY (seller_organization_id) "
        "REFERENCES organizations (id) ON DELETE RESTRICT"
    )
    op.execute(
        "ALTER TABLE marketplace_seller_responses ADD CONSTRAINT IF NOT EXISTS "
        "ck_marketplace_response_distinct_parties CHECK "
        "(buyer_organization_id <> seller_organization_id)"
    )
    op.execute(
        "ALTER TABLE marketplace_seller_responses ADD CONSTRAINT IF NOT EXISTS "
        "ck_marketplace_response_seller_owned CHECK "
        "(organization_id = seller_organization_id)"
    )
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON marketplace_seller_responses")
    op.execute(
        "CREATE POLICY bilateral_response_read ON marketplace_seller_responses "
        f"FOR SELECT TO sira_runtime USING ({_TENANT} IN "
        "(buyer_organization_id, seller_organization_id))"
    )
    op.execute(
        "CREATE POLICY seller_response_insert ON marketplace_seller_responses "
        f"FOR INSERT TO sira_runtime WITH CHECK ({_TENANT} = seller_organization_id "
        "AND organization_id = seller_organization_id)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS seller_response_insert ON marketplace_seller_responses")
    op.execute("DROP POLICY IF EXISTS bilateral_response_read ON marketplace_seller_responses")
    op.execute(
        "CREATE POLICY tenant_isolation ON marketplace_seller_responses "
        f"FOR ALL TO sira_runtime USING (organization_id = {_TENANT}) "
        f"WITH CHECK (organization_id = {_TENANT})"
    )
    op.execute(
        "ALTER TABLE marketplace_seller_responses "
        "DROP CONSTRAINT IF EXISTS ck_marketplace_response_seller_owned"
    )
    op.execute(
        "ALTER TABLE marketplace_seller_responses "
        "DROP CONSTRAINT IF EXISTS ck_marketplace_response_distinct_parties"
    )
    op.execute(
        "ALTER TABLE marketplace_seller_responses "
        "DROP CONSTRAINT IF EXISTS fk_marketplace_response_seller"
    )
    op.execute(
        "ALTER TABLE marketplace_seller_responses "
        "DROP CONSTRAINT IF EXISTS fk_marketplace_response_buyer"
    )
    op.drop_column("marketplace_seller_responses", "seller_organization_id")
    op.drop_column("marketplace_seller_responses", "buyer_organization_id")
