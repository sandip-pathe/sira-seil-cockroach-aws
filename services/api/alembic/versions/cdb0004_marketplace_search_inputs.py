"""marketplace search and mission inputs

Revision ID: cdb0004
Revises: cdb0003
Create Date: 2026-08-13 06:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "cdb0004"
down_revision: str | None = "cdb0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CATALOG_TABLES = (
    "qualification_active_product_bundles",
    "qualification_catalog_projection_versions",
    "qualification_evidence_versions",
    "qualification_product_bundle_members",
    "qualification_product_bundles",
    "qualification_product_embeddings",
)


def upgrade() -> None:
    op.execute("CREATE ROLE IF NOT EXISTS sira_catalog_reader")
    op.execute("GRANT SYSTEM BYPASSRLS TO sira_catalog_reader")
    op.execute("GRANT USAGE ON SCHEMA public TO sira_catalog_reader")
    for table in _CATALOG_TABLES:
        op.execute(f'GRANT SELECT ON TABLE "{table}" TO sira_catalog_reader')
    op.add_column(
        "qualification_missions",
        sa.Column("buyer_context_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "qualification_missions",
        sa.Column(
            "requirement_brief_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "qualification_missions",
        sa.Column(
            "procurement_policy_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "qualification_missions", sa.Column("trace_id", sa.String(length=64), nullable=True)
    )
    op.execute(
        "UPDATE qualification_missions SET "
        "buyer_context_payload = '{}'::JSONB, "
        "requirement_brief_payload = '{}'::JSONB, "
        "procurement_policy_payload = '{}'::JSONB, "
        "trace_id = 'trace_migrated_' || id"
    )
    for column in (
        "buyer_context_payload",
        "requirement_brief_payload",
        "procurement_policy_payload",
        "trace_id",
    ):
        op.alter_column("qualification_missions", column, nullable=False)

    op.execute("DROP INDEX qualification_product_embedding_dvi")
    op.execute(
        "CREATE VECTOR INDEX qualification_product_embedding_dvi "
        "ON qualification_product_embeddings "
        "(category, visibility, embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX qualification_product_embedding_dvi")
    op.execute(
        "CREATE VECTOR INDEX qualification_product_embedding_dvi "
        "ON qualification_product_embeddings "
        "(organization_id, category, visibility, embedding vector_cosine_ops)"
    )
    op.drop_column("qualification_missions", "trace_id")
    op.drop_column("qualification_missions", "procurement_policy_payload")
    op.drop_column("qualification_missions", "requirement_brief_payload")
    op.drop_column("qualification_missions", "buyer_context_payload")
    for table in reversed(_CATALOG_TABLES):
        op.execute(f'REVOKE SELECT ON TABLE "{table}" FROM sira_catalog_reader')
    op.execute("REVOKE USAGE ON SCHEMA public FROM sira_catalog_reader")
    op.execute("REVOKE SYSTEM BYPASSRLS FROM sira_catalog_reader")
    op.execute("DROP ROLE IF EXISTS sira_catalog_reader")
