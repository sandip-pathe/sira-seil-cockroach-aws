"""bind engagement consent to immutable participants

Revision ID: c2d4e6f8a101
Revises: 9f2a6b11c403
Create Date: 2026-08-02 06:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c2d4e6f8a101"
down_revision: str | None = "9f2a6b11c403"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("engagements") as batch:
        batch.add_column(sa.Column("expected_buyer_actor_id", sa.String(100), nullable=True))
        batch.add_column(sa.Column("expected_seller_actor_id", sa.String(100), nullable=True))

    op.execute(
        sa.text(
            "UPDATE engagements SET "
            "expected_buyer_actor_id = COALESCE(buyer_consent_actor_id, "
            "'legacy_buyer_' || id), "
            "expected_seller_actor_id = COALESCE(seller_consent_actor_id, "
            "'legacy_seller_' || id)"
        )
    )

    with op.batch_alter_table("engagements") as batch:
        batch.alter_column("expected_buyer_actor_id", existing_type=sa.String(100), nullable=False)
        batch.alter_column("expected_seller_actor_id", existing_type=sa.String(100), nullable=False)
        batch.create_check_constraint(
            "ck_engagement_distinct_participants",
            "expected_buyer_actor_id <> expected_seller_actor_id",
        )


def downgrade() -> None:
    with op.batch_alter_table("engagements") as batch:
        batch.drop_constraint("ck_engagement_distinct_participants", type_="check")
        batch.drop_column("expected_seller_actor_id")
        batch.drop_column("expected_buyer_actor_id")
