"""bind seller evidence to immutable versioned object identities

Revision ID: cdb0009
Revises: cdb0008
Create Date: 2026-08-13 16:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cdb0009"
down_revision: str | None = "cdb0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for column in (
        sa.Column("object_bucket", sa.String(255), nullable=True),
        sa.Column("object_key", sa.String(500), nullable=True),
        sa.Column("object_version_id", sa.String(200), nullable=True),
        sa.Column("object_checksum", sa.String(80), nullable=True),
        sa.Column("content_type", sa.String(120), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
    ):
        op.add_column("seller_evidence_attachments", column)
    op.create_check_constraint(
        "ck_seller_evidence_object_identity",
        "seller_evidence_attachments",
        "(object_bucket IS NULL AND object_key IS NULL AND object_version_id IS NULL "
        "AND object_checksum IS NULL AND content_type IS NULL AND size_bytes IS NULL) OR "
        "(object_bucket IS NOT NULL AND object_key IS NOT NULL "
        "AND object_version_id IS NOT NULL AND object_checksum IS NOT NULL "
        "AND content_type IS NOT NULL AND size_bytes > 0)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_seller_evidence_object_identity",
        "seller_evidence_attachments",
        type_="check",
    )
    for name in (
        "size_bytes",
        "content_type",
        "object_checksum",
        "object_version_id",
        "object_key",
        "object_bucket",
    ):
        op.drop_column("seller_evidence_attachments", name)
