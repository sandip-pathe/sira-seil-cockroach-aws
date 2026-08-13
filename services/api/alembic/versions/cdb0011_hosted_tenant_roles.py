"""add narrow hosted tenant bootstrap and worker discovery roles

Revision ID: cdb0011
Revises: cdb0010
Create Date: 2026-08-13 18:30:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "cdb0011"
down_revision: str | None = "cdb0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT = "split_part(current_setting('application_name', true), '.', 2)"


def upgrade() -> None:
    op.execute("CREATE ROLE IF NOT EXISTS sira_api_tenant_bootstrap")
    op.execute("CREATE ROLE IF NOT EXISTS sira_worker_directory_reader")
    op.execute("GRANT INSERT ON TABLE organizations TO sira_api_tenant_bootstrap")
    op.execute("GRANT SELECT ON TABLE organizations TO sira_worker_directory_reader")
    op.execute(
        "CREATE POLICY IF NOT EXISTS hosted_tenant_self_insert ON organizations "
        "FOR INSERT TO sira_api_tenant_bootstrap WITH CHECK ("
        f"id = {_TENANT} AND (id LIKE 'org_guest_%' OR id LIKE 'org_user_%'))"
    )
    op.execute(
        "CREATE POLICY IF NOT EXISTS worker_organization_directory_select ON organizations "
        "FOR SELECT TO sira_worker_directory_reader USING (true)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS worker_organization_directory_select ON organizations")
    op.execute("DROP POLICY IF EXISTS hosted_tenant_self_insert ON organizations")
    op.execute("REVOKE SELECT ON TABLE organizations FROM sira_worker_directory_reader")
    op.execute("REVOKE INSERT ON TABLE organizations FROM sira_api_tenant_bootstrap")
    op.execute("DROP ROLE IF EXISTS sira_worker_directory_reader")
    op.execute("DROP ROLE IF EXISTS sira_api_tenant_bootstrap")
