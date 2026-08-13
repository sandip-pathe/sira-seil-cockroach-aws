"""allow runtime verification of public active bundle pointers

Revision ID: cdb0007
Revises: cdb0006
Create Date: 2026-08-13 08:40:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "cdb0007"
down_revision: str | None = "cdb0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # This table contains only the public product-to-bundle pointer and digest.
    # Cross-seller reads let the API revalidate an approval in the same serializable
    # transaction. Private bundle contents remain tenant-isolated.
    op.execute(
        "CREATE POLICY IF NOT EXISTS marketplace_active_bundle_select "
        "ON qualification_active_product_bundles FOR SELECT TO sira_runtime USING (true)"
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS marketplace_active_bundle_select "
        "ON qualification_active_product_bundles"
    )
