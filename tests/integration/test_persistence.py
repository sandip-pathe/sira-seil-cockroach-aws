from __future__ import annotations

import os
import subprocess
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Jsonb
from sira_api.fixtures import DemoFixtureBundle
from sira_api.service import WorkflowService
from sqlalchemy import select
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

from persistence.database import Database, DatabaseSettings
from persistence.models import Base, Engagement, Organization, PurchaseRequest
from persistence.repositories import PersistenceConflict, WorkflowRepository

ROOT = Path(__file__).resolve().parents[2]
LOCAL_TEST_DATABASE_ENV = "SIRA_TEST_DATABASE_ADMIN_URL"


def validated_test_database_url(value: str) -> URL:
    try:
        url = make_url(value)
    except ArgumentError:
        raise ValueError(f"{LOCAL_TEST_DATABASE_ENV} is not a valid SQLAlchemy URL") from None
    if url.get_backend_name() != "postgresql":
        raise ValueError(f"{LOCAL_TEST_DATABASE_ENV} must use PostgreSQL")
    database_name = url.database or ""
    if database_name != "sira_test" and not database_name.startswith("sira_test_"):
        raise ValueError(
            f"{LOCAL_TEST_DATABASE_ENV} database name must be 'sira_test' or start "
            f"with 'sira_test_'; received {database_name!r}"
        )
    return url


def database_url_with_driver(url: URL, drivername: str) -> str:
    return url.set(drivername=drivername).render_as_string(hide_password=False)


@contextmanager
def postgres_test_database() -> Iterator[URL]:
    configured = os.getenv(LOCAL_TEST_DATABASE_ENV, "").strip()
    if not configured:
        pytest.skip(
            f"Set {LOCAL_TEST_DATABASE_ENV} to a dedicated local PostgreSQL database "
            "named sira_test or sira_test_*; Docker is not required"
        )
    # This guard must run before Alembic or fixture reset can write anything.
    yield validated_test_database_url(configured)


def upgrade_database_to_head(database_url: URL) -> None:
    sync_url = database_url_with_driver(database_url, "postgresql+psycopg")
    environment = {**os.environ, "DATABASE_ADMIN_URL": sync_url}
    migration = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert migration.returncode == 0, migration.stderr


def test_local_postgres_guard_accepts_only_dedicated_database_names() -> None:
    for database_name in ("sira_test", "sira_test_laptop", "sira_test_2026_08_02"):
        url = validated_test_database_url(f"postgresql+psycopg://localhost:5432/{database_name}")
        assert url.database == database_name

    for unsafe_url in (
        "postgresql+psycopg://localhost:5432/sira",
        "postgresql+psycopg://localhost:5432/sira_testimony",
        "postgresql+psycopg://localhost:5432/postgres",
        "sqlite:///sira_test",
    ):
        with pytest.raises(ValueError):
            validated_test_database_url(unsafe_url)


def test_persistence_schema_has_no_provider_credential_column() -> None:
    prohibited = {"credential", "token", "cvv", "card_number", "prava_secret"}
    all_columns = {
        column.name.lower() for table in Base.metadata.tables.values() for column in table.columns
    }
    assert prohibited.isdisjoint(all_columns)
    assert "payment_status" in all_columns
    assert "fulfillment_status" in all_columns


def test_engagement_schema_requires_distinct_bound_participants() -> None:
    engagements = Base.metadata.tables[Engagement.__tablename__]
    buyer = engagements.c.expected_buyer_actor_id
    seller = engagements.c.expected_seller_actor_id
    assert buyer.nullable is False
    assert seller.nullable is False
    constraint_names = {constraint.name for constraint in engagements.constraints}
    assert "ck_engagement_distinct_participants" in constraint_names


@pytest.mark.asyncio
async def test_repository_rejects_cross_tenant_write() -> None:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        async with database.sessions() as session, session.begin():
            session.add_all(
                [Organization(id="org_a", name="A"), Organization(id="org_b", name="B")]
            )
        async with database.transaction("org_a") as session:
            repository = WorkflowRepository(session, "org_a")
            record = PurchaseRequest(
                id="req_cross_tenant",
                organization_id="org_b",
                intent="This write belongs to another tenant and must be rejected",
                status="DRAFT",
                visibility="PRIVATE",
                version=1,
                payload={},
                request_hash="sha256:" + "1" * 64,
            )
            with pytest.raises(PersistenceConflict):
                await repository.add_purchase_request(record)
    finally:
        await database.close()


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_migrations_rls_and_demo_seed() -> None:
    with postgres_test_database() as database_url:
        upgrade_database_to_head(database_url)

        async_url = database_url_with_driver(database_url, "postgresql+asyncpg")
        database = Database(DatabaseSettings(database_url=async_url))
        try:
            await WorkflowService(database, DemoFixtureBundle.load()).reset_demo("org_consultco")
            async with database.transaction("org_consultco") as session:
                visible = (
                    await session.execute(
                        select(PurchaseRequest).where(PurchaseRequest.id == "req_demo")
                    )
                ).scalar_one()
                assert visible.organization_id == "org_consultco"
        finally:
            await database.close()

        plain_url = database_url_with_driver(database_url, "postgresql")
        with psycopg.connect(plain_url) as connection:
            tenant_tables = {
                table.name for table in Base.metadata.sorted_tables if "organization_id" in table.c
            }
            protected_tables = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT c.relname
                    FROM pg_class AS c
                    JOIN pg_namespace AS n ON n.oid = c.relnamespace
                    JOIN information_schema.columns AS cols
                      ON cols.table_schema = n.nspname
                     AND cols.table_name = c.relname
                    WHERE n.nspname = current_schema()
                      AND cols.column_name = 'organization_id'
                      AND c.relkind = 'r'
                      AND c.relrowsecurity
                      AND c.relforcerowsecurity
                    """
                ).fetchall()
            }
            assert protected_tables == tenant_tables

            policy_rows = connection.execute(
                """
                SELECT tablename, policyname, permissive, cmd, qual, with_check
                FROM pg_policies
                WHERE schemaname = current_schema()
                  AND policyname IN ('tenant_access', 'tenant_isolation')
                """
            ).fetchall()
            policies = {(row[0], row[1]): row for row in policy_rows}
            for table_name in tenant_tables:
                access = policies[(table_name, "tenant_access")]
                isolation = policies[(table_name, "tenant_isolation")]
                assert access[2] == "PERMISSIVE"
                assert isolation[2] == "RESTRICTIVE"
                assert access[3] == isolation[3] == "ALL"
                assert "app.organization_id" in str(access[4])
                assert "app.organization_id" in str(access[5])
                assert "app.organization_id" in str(isolation[4])
                assert "app.organization_id" in str(isolation[5])


@pytest.mark.postgres
def test_postgres_runtime_role_cannot_cross_tenant_boundary() -> None:
    with postgres_test_database() as database_url:
        upgrade_database_to_head(database_url)
        plain_url = database_url_with_driver(database_url, "postgresql")
        suffix = uuid.uuid4().hex[:12]
        runtime_role = f"sira_rls_test_{suffix}"
        organization_a = f"org_rls_a_{suffix}"
        organization_b = f"org_rls_b_{suffix}"
        request_a = f"req_rls_a_{suffix}"
        request_b = f"req_rls_b_{suffix}"

        with psycopg.connect(plain_url, autocommit=True) as connection:
            role_authority = connection.execute(
                """
                SELECT rolsuper OR rolcreaterole
                FROM pg_roles
                WHERE rolname = current_user
                """
            ).fetchone()
            assert role_authority is not None and role_authority[0], (
                f"{LOCAL_TEST_DATABASE_ENV} must use a PostgreSQL admin role with "
                "CREATEROLE (or SUPERUSER) so the test can create an ephemeral "
                "NOSUPERUSER NOBYPASSRLS role"
            )

            connection.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN PASSWORD NULL NOSUPERUSER NOCREATEDB "
                    "NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                ).format(sql.Identifier(runtime_role))
            )
            try:
                connection.execute(
                    sql.SQL("GRANT {} TO {}").format(
                        sql.Identifier(runtime_role),
                        sql.Identifier(str(connection.info.user)),
                    )
                )
                connection.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                        sql.Identifier(runtime_role)
                    )
                )
                connection.execute(
                    sql.SQL(
                        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}"
                    ).format(sql.Identifier(runtime_role))
                )
                connection.execute(
                    """
                    INSERT INTO organizations (id, name, version)
                    VALUES (%s, %s, 1), (%s, %s, 1)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (organization_a, "RLS tenant A", organization_b, "RLS tenant B"),
                )
                for organization_id, request_id, marker in (
                    (organization_a, request_a, "a"),
                    (organization_b, request_b, "b"),
                ):
                    with connection.transaction():
                        connection.execute(
                            "SELECT set_config('app.organization_id', %s, true)",
                            (organization_id,),
                        )
                        connection.execute(
                            """
                            INSERT INTO purchase_requests
                                (id, intent, status, visibility, version, payload,
                                 request_hash, organization_id)
                            VALUES (%s, %s, 'DRAFT', 'PRIVATE', 1, %s, %s, %s)
                            """,
                            (
                                request_id,
                                f"tenant {marker.upper()} request",
                                Jsonb({}),
                                "sha256:" + marker * 52 + suffix,
                                organization_id,
                            ),
                        )

                with connection.transaction():
                    connection.execute(
                        sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(runtime_role))
                    )
                    connection.execute(
                        "SELECT set_config('app.organization_id', %s, true)",
                        (organization_a,),
                    )
                    role_attributes = connection.execute(
                        """
                        SELECT rolsuper, rolbypassrls, rolcanlogin
                        FROM pg_roles
                        WHERE rolname = current_user
                        """
                    ).fetchone()
                    assert role_attributes == (False, False, True)
                    assert connection.execute("SELECT current_user").fetchone() == (runtime_role,)

                    visible = connection.execute(
                        "SELECT id FROM purchase_requests ORDER BY id"
                    ).fetchall()
                    assert visible == [(request_a,)]
                    hidden_update_count = connection.execute(
                        "UPDATE purchase_requests SET status = 'READY' WHERE id = %s",
                        (request_b,),
                    ).rowcount
                    assert hidden_update_count == 0

                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with connection.transaction():
                        connection.execute(
                            sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(runtime_role))
                        )
                        connection.execute(
                            "SELECT set_config('app.organization_id', %s, true)",
                            (organization_a,),
                        )
                        connection.execute(
                            """
                            INSERT INTO purchase_requests
                                (id, intent, status, visibility, version, payload,
                                 request_hash, organization_id)
                            VALUES (%s, %s, 'DRAFT', 'PRIVATE', 1, %s, %s, %s)
                            """,
                            (
                                f"req_cross_{suffix}",
                                "forbidden cross-tenant write",
                                Jsonb({}),
                                "sha256:" + "c" * 52 + suffix,
                                organization_b,
                            ),
                        )

                with connection.transaction():
                    connection.execute(
                        sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(runtime_role))
                    )
                    no_context_rows = connection.execute(
                        "SELECT id FROM purchase_requests WHERE id IN (%s, %s)",
                        (request_a, request_b),
                    ).fetchall()
                    assert no_context_rows == []
            finally:
                connection.execute("RESET ROLE")
                for organization_id in (organization_a, organization_b):
                    with connection.transaction():
                        connection.execute(
                            "SELECT set_config('app.organization_id', %s, true)",
                            (organization_id,),
                        )
                        connection.execute(
                            "DELETE FROM purchase_requests WHERE organization_id = %s",
                            (organization_id,),
                        )
                connection.execute(
                    "DELETE FROM organizations WHERE id IN (%s, %s)",
                    (organization_a, organization_b),
                )
                connection.execute(
                    sql.SQL("REVOKE {} FROM {}").format(
                        sql.Identifier(runtime_role),
                        sql.Identifier(str(connection.info.user)),
                    )
                )
                connection.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(runtime_role)))
                connection.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(runtime_role)))
