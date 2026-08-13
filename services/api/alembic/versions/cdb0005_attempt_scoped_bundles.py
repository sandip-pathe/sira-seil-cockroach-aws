"""attempt-scoped bundles and buyer-safe engagement projection

Revision ID: cdb0005
Revises: cdb0004
Create Date: 2026-08-13 07:15:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "cdb0005"
down_revision: str | None = "cdb0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # CockroachDB DDL is non-transactional. IF NOT EXISTS lets a migration
    # safely resume after an interrupted schema-change job.
    op.execute(
        "ALTER TABLE qualification_mission_bundles "
        "ADD COLUMN IF NOT EXISTS attempt_id STRING"
    )
    op.execute(
        "UPDATE qualification_mission_bundles AS b SET attempt_id = ("
        "SELECT a.id FROM qualification_attempts AS a "
        "WHERE a.organization_id = b.organization_id AND a.mission_id = b.mission_id "
        "ORDER BY a.replacement_depth, a.created_at, a.id LIMIT 1)"
    )
    op.alter_column("qualification_mission_bundles", "attempt_id", nullable=False)
    op.execute(
        "DROP INDEX IF EXISTS "
        "qualification_mission_bundles@uq_qualification_mission_product CASCADE"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_qualification_attempt_product "
        "ON qualification_mission_bundles (organization_id, attempt_id, product_id)"
    )
    op.execute(
        "ALTER TABLE qualification_mission_bundles ADD CONSTRAINT IF NOT EXISTS "
        "fk_qualification_mission_bundle_attempt FOREIGN KEY "
        "(organization_id, attempt_id) REFERENCES qualification_attempts "
        "(organization_id, id) ON DELETE RESTRICT"
    )

    op.execute(
        "ALTER TABLE marketplace_engagements "
        "ADD COLUMN IF NOT EXISTS buyer_safe_requirement JSONB"
    )
    op.execute(
        "ALTER TABLE marketplace_engagements "
        "ADD COLUMN IF NOT EXISTS buyer_safe_hash STRING(80)"
    )
    op.execute(
        "UPDATE marketplace_engagements SET "
        "buyer_safe_requirement = COALESCE(buyer_safe_requirement, '{}'::JSONB), "
        "buyer_safe_hash = COALESCE(buyer_safe_hash, "
        "'sha256:' || repeat('0', 64)) "
        "WHERE buyer_safe_requirement IS NULL OR buyer_safe_hash IS NULL"
    )
    op.alter_column("marketplace_engagements", "buyer_safe_requirement", nullable=False)
    op.alter_column("marketplace_engagements", "buyer_safe_hash", nullable=False)


def downgrade() -> None:
    op.drop_column("marketplace_engagements", "buyer_safe_hash")
    op.drop_column("marketplace_engagements", "buyer_safe_requirement")
    op.drop_constraint(
        "fk_qualification_mission_bundle_attempt",
        "qualification_mission_bundles",
        type_="foreignkey",
    )
    op.execute(
        "DROP INDEX IF EXISTS "
        "qualification_mission_bundles@uq_qualification_attempt_product CASCADE"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_qualification_mission_product "
        "ON qualification_mission_bundles (organization_id, mission_id, product_id)"
    )
    op.drop_column("qualification_mission_bundles", "attempt_id")
