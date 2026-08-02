"""harden tenant row-level security

Revision ID: a6f4c2d9e801
Revises: 23a8fff461fe
Create Date: 2026-08-02 12:00:00

The migration deliberately does not create a login role: PostgreSQL roles are
cluster-wide and credentials belong to deployment provisioning, not schema
migrations.  Every application login must be NOSUPERUSER, NOBYPASSRLS, must not
own these tables, and must set app.organization_id inside each transaction.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

revision: str = "a6f4c2d9e801"
down_revision: str | None = "23a8fff461fe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_POLICY_EXPRESSION = (
    "organization_id = NULLIF(current_setting('app.organization_id', true), '')"
)
RUNTIME_ROLE_REQUIREMENT = (
    "Runtime roles must be NOSUPERUSER, NOBYPASSRLS, and must not own tenant tables. "
    "Set app.organization_id transaction-locally before accessing tenant data."
)


def _tenant_tables(connection: Connection) -> tuple[str, ...]:
    rows = connection.execute(
        sa.text(
            """
            SELECT DISTINCT table_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND column_name = 'organization_id'
            ORDER BY table_name
            """
        )
    )
    return tuple(str(table_name) for table_name in rows.scalars())


def _quoted(connection: Connection, identifier: str) -> str:
    return connection.dialect.identifier_preparer.quote(identifier)


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return

    for table_name in _tenant_tables(connection):
        table = _quoted(connection, table_name)
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))

        # A restrictive policy preserves the tenant boundary even if a future
        # feature adds another permissive policy to the same table. PostgreSQL
        # also requires a permissive policy before restrictive policies can
        # admit rows, so tenant_access carries the matching allow rule.
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_access ON {table}"))
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
        op.execute(
            sa.text(
                f"CREATE POLICY tenant_access ON {table} AS PERMISSIVE FOR ALL TO PUBLIC "
                f"USING ({TENANT_POLICY_EXPRESSION}) "
                f"WITH CHECK ({TENANT_POLICY_EXPRESSION})"
            )
        )
        op.execute(
            sa.text(
                f"CREATE POLICY tenant_isolation ON {table} AS RESTRICTIVE FOR ALL TO PUBLIC "
                f"USING ({TENANT_POLICY_EXPRESSION}) "
                f"WITH CHECK ({TENANT_POLICY_EXPRESSION})"
            )
        )
        comment = RUNTIME_ROLE_REQUIREMENT.replace("'", "''")
        op.execute(sa.text(f"COMMENT ON POLICY tenant_isolation ON {table} IS '{comment}'"))


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return

    for table_name in _tenant_tables(connection):
        table = _quoted(connection, table_name)
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_access ON {table}"))
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
        op.execute(
            sa.text(
                f"CREATE POLICY tenant_isolation ON {table} FOR ALL TO PUBLIC "
                f"USING ({TENANT_POLICY_EXPRESSION}) "
                f"WITH CHECK ({TENANT_POLICY_EXPRESSION})"
            )
        )
