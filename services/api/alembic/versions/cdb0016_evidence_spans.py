"""add immutable evidence sources and distributed vector spans

Revision ID: cdb0016
Revises: cdb0015
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "cdb0016"
down_revision: str | None = "cdb0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_DOCUMENT = postgresql.JSONB(astext_type=sa.Text())
_TENANT_EXPRESSION = (
    "organization_id = split_part(current_setting('application_name', true), '.', 2)"
)


def _secure(table: str, *, worker_privileges: str) -> None:
    op.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "{table}" TO sira_runtime')
    op.execute(f'GRANT {worker_privileges} ON TABLE "{table}" TO sira_evidence_worker')
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    for role in ("sira_runtime", "sira_evidence_worker"):
        op.execute(
            f'CREATE POLICY "tenant_isolation_{role}" ON "{table}" '
            f"FOR ALL TO {role} USING ({_TENANT_EXPRESSION}) "
            f"WITH CHECK ({_TENANT_EXPRESSION})"
        )


def upgrade() -> None:
    op.create_table(
        "evidence_source_versions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("object_bucket", sa.String(length=255), nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("object_version_id", sa.String(length=200), nullable=False),
        sa.Column("object_checksum", sa.String(length=80), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("parser_version", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("text_hash", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "status IN ('PARSED','VALIDATED','PUBLISHED','REJECTED')",
            name="ck_evidence_source_status",
        ),
        sa.CheckConstraint("size_bytes > 0", name="ck_evidence_source_size"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "product_id", "object_checksum", name="uq_evidence_source_object"
        ),
    )
    op.create_index(
        op.f("ix_evidence_source_versions_organization_id"),
        "evidence_source_versions",
        ["organization_id"],
    )
    op.create_table(
        "evidence_spans",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("source_version_id", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("visibility", sa.String(length=20), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("text_content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        sa.Column("instruction_markers", JSON_DOCUMENT, nullable=False),
        sa.Column("embedding_model_id", sa.String(length=120), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "visibility IN ('PRIVATE','BUYER_SAFE','PUBLIC')", name="ck_evidence_span_visibility"
        ),
        sa.CheckConstraint("sequence >= 1", name="ck_evidence_span_sequence"),
        sa.CheckConstraint(
            "start_offset >= 0 AND end_offset > start_offset", name="ck_evidence_span_offsets"
        ),
        sa.ForeignKeyConstraint(
            ["source_version_id"], ["evidence_source_versions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "source_version_id", "sequence", name="uq_evidence_span_sequence"
        ),
    )
    # CockroachDB owns the physical VECTOR type and distributed vector index.
    op.execute("ALTER TABLE evidence_spans ALTER COLUMN embedding TYPE VECTOR(1024)")
    op.create_index(
        "ix_evidence_span_scope",
        "evidence_spans",
        ["organization_id", "product_id", "visibility", "source_version_id"],
    )
    op.create_index(
        op.f("ix_evidence_spans_organization_id"), "evidence_spans", ["organization_id"]
    )
    op.execute(
        "CREATE VECTOR INDEX evidence_span_dvi ON evidence_spans "
        "(organization_id, product_id, visibility, embedding vector_cosine_ops)"
    )
    _secure("evidence_source_versions", worker_privileges="SELECT, INSERT, UPDATE")
    _secure("evidence_spans", worker_privileges="SELECT, INSERT, UPDATE")


def downgrade() -> None:
    op.execute("DROP INDEX evidence_span_dvi")
    op.drop_table("evidence_spans")
    op.drop_table("evidence_source_versions")
