"""add versioned private company context

Revision ID: cdb0008
Revises: cdb0007
Create Date: 2026-08-13 09:45:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from persistence.qualification_models import Vector1024

revision: str = "cdb0008"
down_revision: str | None = "cdb0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT = "organization_id = split_part(current_setting('application_name', true), '.', 2)"


def upgrade() -> None:
    op.create_table(
        "qualification_company_context_items",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("current_version_id", sa.String(64), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("current_hash", sa.String(80), nullable=False),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('REQUIREMENT','CONSTRAINT','STACK','POLICY','PREFERENCE','NOTE')",
            name="ck_qualification_context_kind",
        ),
        sa.CheckConstraint("state IN ('ACTIVE','RETIRED')", name="ck_qualification_context_state"),
        sa.CheckConstraint("current_version >= 1", name="ck_qualification_context_version"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("organization_id", "id", name="uq_qualification_context_item_tenant_id"),
        sa.UniqueConstraint(
            "organization_id", "id", "current_version_id", "current_hash",
            name="uq_qualification_context_current_binding",
        ),
    )
    op.create_index(
        op.f("ix_qualification_company_context_items_organization_id"),
        "qualification_company_context_items",
        ["organization_id"],
    )
    op.create_table(
        "qualification_company_context_versions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("item_id", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("changed_by_actor_id", sa.String(100), nullable=False),
        sa.Column("change_reason", sa.String(500), nullable=False),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_qualification_context_revision"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "item_id"],
            ["qualification_company_context_items.organization_id", "qualification_company_context_items.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("organization_id", "item_id", "version", name="uq_qualification_context_revision"),
        sa.UniqueConstraint("organization_id", "id", "content_hash", name="uq_qualification_context_binding"),
    )
    op.create_index(
        op.f("ix_qualification_company_context_versions_organization_id"),
        "qualification_company_context_versions",
        ["organization_id"],
    )
    op.create_table(
        "qualification_company_context_embeddings",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("item_id", sa.String(64), nullable=False),
        sa.Column("version_id", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("content_hash", sa.String(80), nullable=False),
        sa.Column("model_id", sa.String(160), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector1024(), nullable=False),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("dimensions = 1024", name="ck_qualification_context_embedding_dimensions"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "version_id", "content_hash"],
            [
                "qualification_company_context_versions.organization_id",
                "qualification_company_context_versions.id",
                "qualification_company_context_versions.content_hash",
            ],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organization_id", "version_id", "content_hash", name="uq_qualification_context_embedding"
        ),
    )
    op.create_index(
        op.f("ix_qualification_company_context_embeddings_organization_id"),
        "qualification_company_context_embeddings",
        ["organization_id"],
    )
    op.create_index(
        "ix_qualification_context_embedding_scope",
        "qualification_company_context_embeddings",
        ["organization_id", "kind", "version_id"],
    )
    op.execute(
        "CREATE VECTOR INDEX qualification_company_context_dvi "
        "ON qualification_company_context_embeddings "
        "(organization_id, kind, embedding vector_cosine_ops)"
    )
    for table, privileges in (
        ("qualification_company_context_items", "SELECT, INSERT, UPDATE"),
        ("qualification_company_context_versions", "SELECT, INSERT"),
        ("qualification_company_context_embeddings", "SELECT, INSERT"),
    ):
        op.execute(f'GRANT {privileges} ON TABLE "{table}" TO sira_runtime')
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(
            f'CREATE POLICY tenant_isolation ON "{table}" FOR ALL TO sira_runtime '
            f"USING ({_TENANT}) WITH CHECK ({_TENANT})"
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS qualification_company_context_dvi")
    for table in (
        "qualification_company_context_embeddings",
        "qualification_company_context_versions",
        "qualification_company_context_items",
    ):
        op.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON TABLE "{table}" FROM sira_runtime')
        op.drop_table(table)
