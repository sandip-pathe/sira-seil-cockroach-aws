"""add immutable decision source snapshots

Revision ID: a4c8e1f7b205
Revises: e3a9c7b2d104
Create Date: 2026-08-02 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4c8e1f7b205"
down_revision: str | None = "e3a9c7b2d104"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decision_source_snapshots",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("purchase_request_id", sa.String(64), nullable=False),
        sa.Column("purchase_brief_id", sa.String(64), nullable=False),
        sa.Column("stack_snapshot_id", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(80), nullable=False),
        sa.Column("accepted_by_actor_id", sa.String(100), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.CheckConstraint("version >= 1", name="ck_decision_source_snapshot_version"),
        sa.CheckConstraint(
            "source_kind IN ('DEVELOPMENT_FIXTURE','PROVIDER_COMPILED','MANUAL_VERIFIED')",
            name="ck_decision_source_snapshot_kind",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["purchase_request_id"], ["purchase_requests.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["purchase_brief_id"], ["purchase_brief_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["stack_snapshot_id"], ["stack_snapshots.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "purchase_request_id",
            "version",
            name="uq_decision_source_snapshot_version",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "purchase_request_id",
            "content_hash",
            name="uq_decision_source_snapshot_hash",
        ),
    )
    op.create_index(
        op.f("ix_decision_source_snapshots_organization_id"),
        "decision_source_snapshots",
        ["organization_id"],
        unique=False,
    )
    if op.get_bind().dialect.name == "postgresql":
        expression = "organization_id = NULLIF(current_setting('app.organization_id', true), '')"
        op.execute(sa.text('ALTER TABLE "decision_source_snapshots" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "decision_source_snapshots" FORCE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(
                'CREATE POLICY tenant_access ON "decision_source_snapshots" '
                f"AS PERMISSIVE FOR ALL TO PUBLIC USING ({expression}) WITH CHECK ({expression})"
            )
        )
        op.execute(
            sa.text(
                'CREATE POLICY tenant_isolation ON "decision_source_snapshots" '
                f"AS RESTRICTIVE FOR ALL TO PUBLIC USING ({expression}) WITH CHECK ({expression})"
            )
        )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_decision_source_snapshots_organization_id"),
        table_name="decision_source_snapshots",
    )
    op.drop_table("decision_source_snapshots")
