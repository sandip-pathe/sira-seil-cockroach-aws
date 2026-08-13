"""add versioned workspace notification and disclosure settings

Revision ID: cdb0010
Revises: cdb0009
Create Date: 2026-08-13 22:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cdb0010"
down_revision: str | None = "cdb0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT = "organization_id = split_part(current_setting('application_name', true), '.', 2)"


def upgrade() -> None:
    op.create_table(
        "qualification_workspace_settings",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("party", sa.String(12), nullable=False),
        sa.Column("current_version_id", sa.String(64), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("current_hash", sa.String(80), nullable=False),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("party IN ('BUYER','SELLER')", name="ck_workspace_settings_party"),
        sa.CheckConstraint("current_version >= 1", name="ck_workspace_settings_version"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("organization_id", "party", name="uq_workspace_settings_party"),
        sa.UniqueConstraint("organization_id", "id", name="uq_workspace_settings_tenant_id"),
    )
    op.create_index(
        op.f("ix_qualification_workspace_settings_organization_id"),
        "qualification_workspace_settings",
        ["organization_id"],
    )
    op.create_table(
        "qualification_workspace_setting_versions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("settings_id", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("changed_by_actor_id", sa.String(100), nullable=False),
        sa.Column("change_reason", sa.String(500), nullable=False),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("version >= 1", name="ck_workspace_settings_revision"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "settings_id"],
            [
                "qualification_workspace_settings.organization_id",
                "qualification_workspace_settings.id",
            ],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organization_id", "settings_id", "version", name="uq_workspace_settings_revision"
        ),
        sa.UniqueConstraint(
            "organization_id", "id", "content_hash", name="uq_workspace_settings_binding"
        ),
    )
    op.create_index(
        op.f("ix_qualification_workspace_setting_versions_organization_id"),
        "qualification_workspace_setting_versions",
        ["organization_id"],
    )
    for table, privileges in (
        ("qualification_workspace_settings", "SELECT, INSERT, UPDATE"),
        ("qualification_workspace_setting_versions", "SELECT, INSERT"),
    ):
        op.execute(f'GRANT {privileges} ON TABLE "{table}" TO sira_runtime')
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(
            f'CREATE POLICY tenant_isolation ON "{table}" FOR ALL TO sira_runtime '
            f"USING ({_TENANT}) WITH CHECK ({_TENANT})"
        )


def downgrade() -> None:
    for table in (
        "qualification_workspace_setting_versions",
        "qualification_workspace_settings",
    ):
        op.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON TABLE "{table}" FROM sira_runtime')
        op.drop_table(table)
