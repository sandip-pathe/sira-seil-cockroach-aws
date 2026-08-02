"""version immutable Decision Records and link superseded versions

Revision ID: d7a1c4e9b203
Revises: b8e1d3f5a702
Create Date: 2026-08-02 10:00:00
"""

from collections import defaultdict
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d7a1c4e9b203"
down_revision: str | None = "b8e1d3f5a702"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("decision_records") as batch:
        batch.add_column(sa.Column("version", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("supersedes_id", sa.String(64), nullable=True))

    bind = op.get_bind()
    decisions = sa.table(
        "decision_records",
        sa.column("id", sa.String(64)),
        sa.column("organization_id", sa.String(64)),
        sa.column("purchase_request_id", sa.String(64)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("version", sa.Integer()),
        sa.column("supersedes_id", sa.String(64)),
    )
    rows = bind.execute(
        sa.select(
            decisions.c.id,
            decisions.c.organization_id,
            decisions.c.purchase_request_id,
            decisions.c.created_at,
        ).order_by(
            decisions.c.organization_id,
            decisions.c.purchase_request_id,
            decisions.c.created_at,
            decisions.c.id,
        )
    ).mappings()
    by_request: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in rows:
        by_request[(str(row["organization_id"]), str(row["purchase_request_id"]))].append(
            str(row["id"])
        )
    for decision_ids in by_request.values():
        previous_id: str | None = None
        for version, decision_id in enumerate(decision_ids, start=1):
            bind.execute(
                sa.update(decisions)
                .where(decisions.c.id == decision_id)
                .values(version=version, supersedes_id=previous_id)
            )
            previous_id = decision_id

    with op.batch_alter_table("decision_records") as batch:
        batch.alter_column("version", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key(
            "fk_decision_records_supersedes_id_decision_records",
            "decision_records",
            ["supersedes_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_check_constraint("ck_decision_record_version_positive", "version >= 1")
        batch.create_unique_constraint(
            "uq_decision_record_version",
            ["organization_id", "purchase_request_id", "version"],
        )


def downgrade() -> None:
    with op.batch_alter_table("decision_records") as batch:
        batch.drop_constraint("uq_decision_record_version", type_="unique")
        batch.drop_constraint("ck_decision_record_version_positive", type_="check")
        batch.drop_constraint(
            "fk_decision_records_supersedes_id_decision_records", type_="foreignkey"
        )
        batch.drop_column("supersedes_id")
        batch.drop_column("version")
