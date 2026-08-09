from __future__ import annotations

import asyncio
import os
import secrets
import subprocess
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Jsonb
from sira_api.fixtures import DemoFixtureBundle
from sira_api.marketplace import SellerPrincipalBinding, StaticSellerOrganizationDirectory
from sira_api.service import WorkflowService
from sqlalchemy import delete, func, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

from persistence.database import Database, DatabaseSettings
from persistence.models import (
    Base,
    Engagement,
    Organization,
    OutcomeCheckpoint,
    PurchaseIntent,
    PurchaseRequest,
    PurchaseReversal,
)
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
def postgres_runtime_database(database_url: URL) -> Iterator[URL]:
    """Create a real restricted login for tests that must not rely on SET ROLE."""

    plain_url = database_url_with_driver(database_url, "postgresql")
    suffix = uuid.uuid4().hex[:12]
    runtime_role = f"sira_runtime_test_{suffix}"
    runtime_password = secrets.token_urlsafe(24)
    database_name = database_url.database
    assert database_name is not None

    with psycopg.connect(plain_url, autocommit=True) as connection:
        current_user = str(connection.info.user)
        connection.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOREPLICATION NOBYPASSRLS"
            ).format(sql.Identifier(runtime_role), sql.Literal(runtime_password))
        )
        connection.execute(
            sql.SQL("GRANT {} TO {}").format(
                sql.Identifier(runtime_role), sql.Identifier(current_user)
            )
        )
        connection.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(database_name), sql.Identifier(runtime_role)
            )
        )
        connection.execute(
            sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(runtime_role))
        )
        connection.execute(
            sql.SQL(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}"
            ).format(sql.Identifier(runtime_role))
        )
        connection.execute(
            sql.SQL("GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {}").format(
                sql.Identifier(runtime_role)
            )
        )

    runtime_url = database_url.set(username=runtime_role, password=runtime_password)
    try:
        yield runtime_url
    finally:
        with psycopg.connect(plain_url, autocommit=True) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE usename = %s AND pid <> pg_backend_pid()",
                (runtime_role,),
            )
            connection.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(runtime_role)))
            connection.execute(
                sql.SQL("REVOKE {} FROM {}").format(
                    sql.Identifier(runtime_role), sql.Identifier(current_user)
                )
            )
            connection.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(runtime_role)))


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
                """
            ).fetchall()
            policies = {(row[0], row[1]): row for row in policy_rows}
            for table_name in tenant_tables - {"engagements"}:
                access = policies[(table_name, "tenant_access")]
                isolation = policies[(table_name, "tenant_isolation")]
                assert access[2] == "PERMISSIVE"
                assert isolation[2] == "RESTRICTIVE"
                assert access[3] == isolation[3] == "ALL"
                assert "app.organization_id" in str(access[4])
                assert "app.organization_id" in str(access[5])
                assert "app.organization_id" in str(isolation[4])
                assert "app.organization_id" in str(isolation[5])

            engagement_policies = {
                name: policies[("engagements", name)]
                for name in (
                    "engagement_party_select",
                    "engagement_owner_insert",
                    "engagement_party_update",
                    "engagement_owner_delete",
                )
            }
            assert engagement_policies["engagement_party_select"][3] == "SELECT"
            assert engagement_policies["engagement_owner_insert"][3] == "INSERT"
            assert engagement_policies["engagement_party_update"][3] == "UPDATE"
            assert engagement_policies["engagement_owner_delete"][3] == "DELETE"
            for policy in engagement_policies.values():
                assert policy[2] == "PERMISSIVE"
                assert "app.organization_id" in str(policy[4] or policy[5])
            assert "seller_organization_id" in str(
                engagement_policies["engagement_party_select"][4]
            )
            assert "seller_organization_id" in str(
                engagement_policies["engagement_party_update"][4]
            )


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_engagement_is_visible_only_to_bound_parties() -> None:
    with postgres_test_database() as database_url:
        upgrade_database_to_head(database_url)
        fixtures = DemoFixtureBundle.load()
        seller_directory = StaticSellerOrganizationDirectory(
            tuple(
                SellerPrincipalBinding(
                    candidate_id=candidate_id,
                    seller_actor_id=str(pack["seller_id"]),
                    seller_organization_id=f"org_{pack['seller_id']}",
                )
                for candidate_id, pack in sorted(fixtures.packs.items())
            )
        )
        async_url = database_url_with_driver(database_url, "postgresql+asyncpg")
        database = Database(DatabaseSettings(database_url=async_url))
        try:
            service = WorkflowService(
                database,
                fixtures,
                allow_development_tenant_bootstrap=True,
                seller_directory=seller_directory,
            )
            await service.reset_demo("org_consultco")
            _, response = await service.candidate_action(
                organization_id="org_consultco",
                actor_id="usr_demo_requester",
                actor_party="BUYER",
                request_id="req_demo",
                candidate_id="fixture_selected_fit",
                idempotency_key=f"postgres-engagement-{uuid.uuid4().hex}",
                body={"action": "REQUEST_OFFER", "reason": "PostgreSQL RLS proof"},
            )
            engagement_id = str(response["engagement_id"])
            await service.record_consent(
                organization_id="org_consultco",
                actor_id="usr_demo_requester",
                actor_party="BUYER",
                engagement_id=engagement_id,
                idempotency_key=f"postgres-buyer-consent-{uuid.uuid4().hex}",
                body={"consent": True},
            )
        finally:
            await database.close()

        plain_url = database_url_with_driver(database_url, "postgresql")
        runtime_role = f"sira_engagement_test_{uuid.uuid4().hex[:12]}"
        forged_engagement_id = f"eng_forged_{uuid.uuid4().hex}"
        forged_grant_hash = "sha256:" + uuid.uuid4().hex + uuid.uuid4().hex
        with psycopg.connect(plain_url, autocommit=True) as connection:
            current_user = str(connection.info.user)
            connection.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN PASSWORD NULL NOSUPERUSER NOCREATEDB "
                    "NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                ).format(sql.Identifier(runtime_role))
            )
            try:
                connection.execute(
                    sql.SQL("GRANT {} TO {}").format(
                        sql.Identifier(runtime_role), sql.Identifier(current_user)
                    )
                )
                connection.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                        sql.Identifier(runtime_role)
                    )
                )
                connection.execute(
                    sql.SQL("GRANT SELECT, INSERT ON engagements TO {}").format(
                        sql.Identifier(runtime_role)
                    )
                )
                connection.execute(
                    sql.SQL(
                        "GRANT SELECT ON purchase_requests, purchase_brief_versions, "
                        "requirement_brief_versions, stack_snapshots TO {}"
                    ).format(sql.Identifier(runtime_role))
                )
                connection.execute(
                    sql.SQL("GRANT UPDATE ON engagements TO {}").format(
                        sql.Identifier(runtime_role)
                    )
                )

                for organization_id in ("org_consultco", "org_seller_fixture_d"):
                    with connection.transaction():
                        connection.execute(
                            sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(runtime_role))
                        )
                        connection.execute(
                            "SELECT set_config('app.organization_id', %s, true)",
                            (organization_id,),
                        )
                        visible = connection.execute(
                            "SELECT id FROM engagements WHERE id = %s", (engagement_id,)
                        ).fetchall()
                        assert visible == [(engagement_id,)]

                with connection.transaction():
                    connection.execute(
                        sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(runtime_role))
                    )
                    connection.execute(
                        "SELECT set_config('app.organization_id', %s, true)",
                        ("org_seller_fixture_d",),
                    )
                    for table_name in (
                        "purchase_requests",
                        "purchase_brief_versions",
                        "requirement_brief_versions",
                        "stack_snapshots",
                    ):
                        private_count = connection.execute(
                            sql.SQL("SELECT count(*) FROM {} WHERE organization_id = %s").format(
                                sql.Identifier(table_name)
                            ),
                            ("org_consultco",),
                        ).fetchone()
                        assert private_count == (0,)
                    assert (
                        connection.execute(
                            "UPDATE engagements SET status = status WHERE id = %s",
                            (engagement_id,),
                        ).rowcount
                        == 1
                    )

                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with connection.transaction():
                        connection.execute(
                            sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(runtime_role))
                        )
                        connection.execute(
                            "SELECT set_config('app.organization_id', %s, true)",
                            ("org_consultco",),
                        )
                        connection.execute(
                            """
                            INSERT INTO engagements (
                                id,
                                organization_id,
                                purchase_request_id,
                                requirement_brief_id,
                                requirement_brief_version,
                                requirement_brief_hash,
                                candidate_id,
                                seller_organization_id,
                                expected_buyer_actor_id,
                                expected_seller_actor_id,
                                grant_scope,
                                grant_status,
                                grant_hash,
                                seller_visible_requirement_brief,
                                granted_at,
                                status,
                                buyer_consented,
                                seller_consented,
                                buyer_consent_actor_id,
                                seller_consent_actor_id,
                                contact_exchange
                            )
                            SELECT
                                %s,
                                organization_id,
                                purchase_request_id,
                                requirement_brief_id,
                                requirement_brief_version,
                                requirement_brief_hash,
                                candidate_id,
                                seller_organization_id,
                                expected_buyer_actor_id,
                                expected_seller_actor_id,
                                grant_scope,
                                grant_status,
                                %s,
                                seller_visible_requirement_brief,
                                granted_at,
                                'INTRODUCTION_READY',
                                true,
                                true,
                                expected_buyer_actor_id,
                                expected_seller_actor_id,
                                jsonb_build_object(
                                    'buyer', expected_buyer_actor_id,
                                    'seller', expected_seller_actor_id
                                )
                            FROM engagements
                            WHERE id = %s
                            """,
                            (forged_engagement_id, forged_grant_hash, engagement_id),
                        )
                        raise AssertionError("buyer created a pre-consented engagement")

                with pytest.raises(psycopg.errors.CheckViolation):
                    with connection.transaction():
                        connection.execute(
                            sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(runtime_role))
                        )
                        connection.execute(
                            "SELECT set_config('app.organization_id', %s, true)",
                            ("org_seller_fixture_d",),
                        )
                        connection.execute(
                            """
                            UPDATE engagements
                               SET seller_consented = true,
                                   seller_consent_actor_id = expected_seller_actor_id,
                                   status = 'INTRODUCTION_READY',
                                   contact_exchange = %s
                             WHERE id = %s
                            """,
                            (
                                Jsonb({"buyer": "forged", "seller": "forged"}),
                                engagement_id,
                            ),
                        )
                        raise AssertionError("seller supplied non-canonical contact data")

                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with connection.transaction():
                        connection.execute(
                            sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(runtime_role))
                        )
                        connection.execute(
                            "SELECT set_config('app.organization_id', %s, true)",
                            ("org_seller_fixture_d",),
                        )
                        connection.execute(
                            """
                            UPDATE engagements
                               SET buyer_consented = true,
                                   buyer_consent_actor_id = 'spoofed_buyer',
                                   status = 'INTRODUCTION_READY',
                                   contact_exchange = %s
                             WHERE id = %s
                            """,
                            (Jsonb({"buyer": "leaked", "seller": "leaked"}), engagement_id),
                        )
                        raise AssertionError("seller changed buyer-owned consent state")

                with connection.transaction():
                    connection.execute(
                        sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(runtime_role))
                    )
                    connection.execute(
                        "SELECT set_config('app.organization_id', %s, true)",
                        ("org_unrelated",),
                    )
                    assert (
                        connection.execute(
                            "SELECT id FROM engagements WHERE id = %s", (engagement_id,)
                        ).fetchall()
                        == []
                    )
                    assert (
                        connection.execute(
                            "UPDATE engagements SET status = status WHERE id = %s",
                            (engagement_id,),
                        ).rowcount
                        == 0
                    )
            finally:
                connection.execute("RESET ROLE")
                connection.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(runtime_role)))
                connection.execute(
                    sql.SQL("REVOKE {} FROM {}").format(
                        sql.Identifier(runtime_role), sql.Identifier(current_user)
                    )
                )
                connection.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(runtime_role)))


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
                connection.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(runtime_role)))
                connection.execute(
                    sql.SQL("REVOKE {} FROM {}").format(
                        sql.Identifier(runtime_role),
                        sql.Identifier(str(connection.info.user)),
                    )
                )
                connection.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(runtime_role)))


@pytest.mark.postgres
def test_postgres_proof_exchange_inverse_runtime_roles() -> None:
    with postgres_test_database() as database_url:
        upgrade_database_to_head(database_url)
        plain_url = database_url_with_driver(database_url, "postgresql")
        suffix = uuid.uuid4().hex[:12]
        buyer_org = f"org_proof_buyer_{suffix}"
        seller_org = f"org_proof_seller_{suffix}"
        projection_id = f"bpap_{suffix}"
        approval_id = f"papr_{suffix}"
        product_id = f"seller_product_{suffix}"
        digest = "sha256:" + "a" * 64

        with psycopg.connect(plain_url, autocommit=True) as admin:
            admin.execute(
                "INSERT INTO organizations (id, name, version) VALUES (%s, 'Proof Buyer', 1), "
                "(%s, 'Proof Seller', 1)",
                (buyer_org, seller_org),
            )
            admin.execute(
                """
                INSERT INTO seller_products
                    (id, name, category, public_summary, publisher_authority, state,
                     owner_actor_id, current_draft_id, current_pack_version_id,
                     current_version, fixture_label, organization_id)
                VALUES (%s, 'Private Seller Draft', 'proof-adapter', 'private',
                        'SELLER_SEALED', 'SELLER_DRAFT', 'seller_actor', NULL, NULL,
                        1, NULL, %s)
                """,
                (product_id, seller_org),
            )
            admin.execute(
                """
                INSERT INTO buyer_proof_adapter_projections
                    (id, organization_id, source_seller_organization_id,
                     source_pack_version_id, source_pack_content_hash,
                     publication_event_key, adapter_id, artifact_digest,
                     protocol_version, capabilities, declared_region, fixed_price,
                     public_evidence_references, conformance_hash, projection_hash, state)
                VALUES (%s, %s, %s, 'pack-v1', %s, %s, 'adapter-a', %s,
                        'TrialCase/v0', %s, 'EU', %s, %s, %s, %s, 'AVAILABLE')
                """,
                (
                    projection_id,
                    buyer_org,
                    seller_org,
                    "sha256:" + "b" * 64,
                    f"seller-pack-published:{suffix}",
                    digest,
                    Jsonb(["SUPPORT_SUMMARIZATION"]),
                    Jsonb({"amount": "0.02", "currency": "USD"}),
                    Jsonb([]),
                    "sha256:" + "c" * 64,
                    "sha256:" + "d" * 64,
                ),
            )
            admin.execute(
                """
                INSERT INTO proof_approvals
                    (id, organization_id, subject_hash, manifest_hash,
                     environment_fingerprint, decision_hash, adapter_projection_hash,
                     adapter_digest, datahub_owner_urn, actor_id, actor_role, status,
                     expires_at, revoked_at, consumed_effect_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                        'urn:li:corpGroup:support-data-owners', 'seeded_support_owner',
                        'DATA_OWNER', 'ACTIVE', NOW() + INTERVAL '15 minutes', NULL, NULL)
                """,
                (
                    approval_id,
                    buyer_org,
                    "sha256:" + "e" * 64,
                    "sha256:" + "f" * 64,
                    "sha256:" + "1" * 64,
                    "sha256:" + "2" * 64,
                    "sha256:" + "d" * 64,
                    digest,
                ),
            )

        try:
            with postgres_runtime_database(database_url) as runtime_url:
                runtime_plain = database_url_with_driver(runtime_url, "postgresql")
                with psycopg.connect(runtime_plain) as runtime:
                    with runtime.transaction():
                        runtime.execute(
                            "SELECT set_config('app.organization_id', %s, true)", (buyer_org,)
                        )
                        assert runtime.execute(
                            "SELECT id FROM buyer_proof_adapter_projections"
                        ).fetchall() == [(projection_id,)]
                        assert runtime.execute("SELECT id FROM proof_approvals").fetchall() == [
                            (approval_id,)
                        ]
                        assert runtime.execute("SELECT id FROM seller_products").fetchall() == []

                    with runtime.transaction():
                        runtime.execute(
                            "SELECT set_config('app.organization_id', %s, true)", (seller_org,)
                        )
                        assert runtime.execute("SELECT id FROM seller_products").fetchall() == [
                            (product_id,)
                        ]
                        assert (
                            runtime.execute(
                                "SELECT id FROM buyer_proof_adapter_projections"
                            ).fetchall()
                            == []
                        )
                        assert runtime.execute("SELECT id FROM proof_approvals").fetchall() == []
        finally:
            with psycopg.connect(plain_url, autocommit=True) as admin:
                admin.execute("DELETE FROM proof_approvals WHERE id = %s", (approval_id,))
                admin.execute(
                    "DELETE FROM buyer_proof_adapter_projections WHERE id = %s", (projection_id,)
                )
                admin.execute("DELETE FROM seller_products WHERE id = %s", (product_id,))
                admin.execute(
                    "DELETE FROM organizations WHERE id IN (%s, %s)", (buyer_org, seller_org)
                )


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_readiness_requires_direct_restricted_runtime_login() -> None:
    with postgres_test_database() as database_url:
        upgrade_database_to_head(database_url)

        admin_database = Database(
            DatabaseSettings(
                database_url=database_url_with_driver(database_url, "postgresql+asyncpg")
            )
        )
        try:
            assert await admin_database.is_ready() is False
        finally:
            await admin_database.close()

        with postgres_runtime_database(database_url) as runtime_url:
            runtime_database = Database(
                DatabaseSettings(
                    database_url=database_url_with_driver(runtime_url, "postgresql+asyncpg")
                )
            )
            try:
                assert await runtime_database.is_ready() is True
                assert (
                    await runtime_database.is_ready(
                        expected_alembic_heads=frozenset({"intentionally_stale"})
                    )
                    is False
                )
            finally:
                await runtime_database.close()


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_readiness_rejects_dangerous_role_state() -> None:
    with postgres_test_database() as database_url:
        upgrade_database_to_head(database_url)
        plain_url = database_url_with_driver(database_url, "postgresql")

        with postgres_runtime_database(database_url) as runtime_url:
            runtime_role = runtime_url.username
            assert runtime_role is not None
            dangerous_role = f"sira_dangerous_test_{uuid.uuid4().hex[:12]}"
            runtime_database = Database(
                DatabaseSettings(
                    database_url=database_url_with_driver(runtime_url, "postgresql+asyncpg")
                )
            )
            try:
                assert await runtime_database.is_ready() is True
                with psycopg.connect(plain_url, autocommit=True) as connection:
                    connection.execute(
                        sql.SQL("ALTER ROLE {} CREATEROLE").format(sql.Identifier(runtime_role))
                    )
                    try:
                        assert await runtime_database.is_ready() is False
                    finally:
                        connection.execute(
                            sql.SQL("ALTER ROLE {} NOCREATEROLE").format(
                                sql.Identifier(runtime_role)
                            )
                        )
                    assert await runtime_database.is_ready() is True

                    connection.execute(
                        sql.SQL(
                            "CREATE ROLE {} NOLOGIN NOSUPERUSER CREATEDB "
                            "NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                        ).format(sql.Identifier(dangerous_role))
                    )
                    try:
                        connection.execute(
                            sql.SQL("GRANT {} TO {}").format(
                                sql.Identifier(dangerous_role),
                                sql.Identifier(runtime_role),
                            )
                        )
                        assert await runtime_database.is_ready() is False
                    finally:
                        connection.execute(
                            sql.SQL("REVOKE {} FROM {}").format(
                                sql.Identifier(dangerous_role),
                                sql.Identifier(runtime_role),
                            )
                        )
                        connection.execute(
                            sql.SQL("DROP ROLE {}").format(sql.Identifier(dangerous_role))
                        )
                    assert await runtime_database.is_ready() is True
            finally:
                await runtime_database.close()


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_readiness_rejects_rls_policy_and_trigger_drift() -> None:
    with postgres_test_database() as database_url:
        upgrade_database_to_head(database_url)
        plain_url = database_url_with_driver(database_url, "postgresql")
        suffix = uuid.uuid4().hex[:12]
        probe_table = f"readiness_tenant_probe_{suffix}"
        renamed_policy = f"readiness_disabled_select_{suffix}"

        with postgres_runtime_database(database_url) as runtime_url:
            runtime_database = Database(
                DatabaseSettings(
                    database_url=database_url_with_driver(runtime_url, "postgresql+asyncpg")
                )
            )
            try:
                assert await runtime_database.is_ready() is True
                with psycopg.connect(plain_url, autocommit=True) as connection:
                    connection.execute(
                        "ALTER TABLE public.purchase_requests DISABLE ROW LEVEL SECURITY"
                    )
                    try:
                        assert await runtime_database.is_ready() is False
                    finally:
                        connection.execute(
                            "ALTER TABLE public.purchase_requests ENABLE ROW LEVEL SECURITY"
                        )
                        connection.execute(
                            "ALTER TABLE public.purchase_requests FORCE ROW LEVEL SECURITY"
                        )
                    assert await runtime_database.is_ready() is True

                    connection.execute(
                        sql.SQL("CREATE TABLE public.{} (organization_id text NOT NULL)").format(
                            sql.Identifier(probe_table)
                        )
                    )
                    try:
                        connection.execute(
                            sql.SQL("ALTER TABLE public.{} ENABLE ROW LEVEL SECURITY").format(
                                sql.Identifier(probe_table)
                            )
                        )
                        connection.execute(
                            sql.SQL("ALTER TABLE public.{} FORCE ROW LEVEL SECURITY").format(
                                sql.Identifier(probe_table)
                            )
                        )
                        assert await runtime_database.is_ready() is False
                    finally:
                        connection.execute(
                            sql.SQL("DROP TABLE public.{}").format(sql.Identifier(probe_table))
                        )
                    assert await runtime_database.is_ready() is True

                    connection.execute(
                        sql.SQL(
                            "ALTER POLICY engagement_party_select ON public.engagements "
                            "RENAME TO {}"
                        ).format(sql.Identifier(renamed_policy))
                    )
                    try:
                        assert await runtime_database.is_ready() is False
                    finally:
                        connection.execute(
                            sql.SQL(
                                "ALTER POLICY {} ON public.engagements "
                                "RENAME TO engagement_party_select"
                            ).format(sql.Identifier(renamed_policy))
                        )
                    assert await runtime_database.is_ready() is True

                    connection.execute(
                        "ALTER TABLE public.engagements "
                        "DISABLE TRIGGER engagement_party_update_guard"
                    )
                    try:
                        assert await runtime_database.is_ready() is False
                    finally:
                        connection.execute(
                            "ALTER TABLE public.engagements "
                            "ENABLE TRIGGER engagement_party_update_guard"
                        )
                    assert await runtime_database.is_ready() is True
            finally:
                await runtime_database.close()


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_first_idempotency_claim_is_atomic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with postgres_test_database() as database_url:
        upgrade_database_to_head(database_url)
        idempotency_key = f"postgres-intent-race-{uuid.uuid4().hex}"
        backend_pids: set[int] = set()
        entrant_lock = asyncio.Lock()
        first_claimed = asyncio.Event()
        second_entered = asyncio.Event()
        entrant_count = 0
        original_claim = WorkflowRepository.claim_idempotency

        async def synchronized_claim(repository: WorkflowRepository, **kwargs: Any) -> Any:
            nonlocal entrant_count
            async with entrant_lock:
                entrant_count += 1
                entrant_number = entrant_count
                backend_pid = await repository.session.scalar(text("SELECT pg_backend_pid()"))
                assert backend_pid is not None
                backend_pids.add(int(backend_pid))
                if entrant_number == 2:
                    second_entered.set()

            if entrant_number == 1:
                claim = await original_claim(repository, **kwargs)
                first_claimed.set()
                await asyncio.wait_for(second_entered.wait(), timeout=5)
                # Keep the first outer transaction open long enough for the second
                # connection to block on the unique idempotency scope.
                await asyncio.sleep(0.1)
                return claim

            await asyncio.wait_for(first_claimed.wait(), timeout=5)
            return await original_claim(repository, **kwargs)

        with postgres_runtime_database(database_url) as runtime_url:
            async_url = database_url_with_driver(runtime_url, "postgresql+asyncpg")
            database = Database(DatabaseSettings(database_url=async_url))
            try:
                service = WorkflowService(database, DemoFixtureBundle.load())
                await service.reset_demo("org_consultco")
                monkeypatch.setattr(
                    WorkflowRepository,
                    "claim_idempotency",
                    synchronized_claim,
                )

                async def lock_intent() -> tuple[int, dict[str, Any]]:
                    return await service.lock_purchase_intent(
                        organization_id="org_consultco",
                        actor_id="usr_requester",
                        decision_id="dec_consultco_v1",
                        idempotency_key=idempotency_key,
                        body={"solution_plan_id": None},
                    )

                first, second = await asyncio.wait_for(
                    asyncio.gather(lock_intent(), lock_intent()),
                    timeout=15,
                )
            finally:
                await database.close()

        assert len(backend_pids) == 2
        assert first[0] == second[0] == 201
        assert first[1] == second[1]
        intent_id = str(first[1]["purchase_intent_id"])

        plain_url = database_url_with_driver(database_url, "postgresql")
        with psycopg.connect(plain_url) as connection:
            intent_count = connection.execute(
                "SELECT count(*) FROM purchase_intents WHERE organization_id = %s AND id = %s",
                ("org_consultco", intent_id),
            ).fetchone()
            idempotency_rows = connection.execute(
                "SELECT state, response_reference FROM idempotency_records "
                "WHERE organization_id = %s AND actor_id = %s "
                "AND operation = %s AND idempotency_key = %s",
                (
                    "org_consultco",
                    "usr_requester",
                    "purchase_intents.create",
                    idempotency_key,
                ),
            ).fetchall()
        assert intent_count == (1,)
        assert idempotency_rows == [("COMPLETED", intent_id)]


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_demo_reset_clears_reversals_and_outcomes() -> None:
    with postgres_test_database() as database_url:
        upgrade_database_to_head(database_url)
        async_url = database_url_with_driver(database_url, "postgresql+asyncpg")
        database = Database(DatabaseSettings(database_url=async_url))
        try:
            service = WorkflowService(database, DemoFixtureBundle.load())
            async with database.transaction("org_consultco") as session:
                await session.execute(
                    delete(PurchaseReversal).where(
                        PurchaseReversal.organization_id == "org_consultco"
                    )
                )
                await session.execute(
                    delete(OutcomeCheckpoint).where(
                        OutcomeCheckpoint.organization_id == "org_consultco"
                    )
                )
            await service.reset_demo("org_consultco")
            _, intent_view = await service.lock_purchase_intent(
                organization_id="org_consultco",
                actor_id="usr_requester",
                decision_id="dec_consultco_v1",
                idempotency_key=f"postgres-reset-intent-{uuid.uuid4().hex}",
                body={"solution_plan_id": None},
            )
            intent_id = str(intent_view["purchase_intent_id"])
            now = datetime.now(UTC)
            async with database.transaction("org_consultco") as session:
                intent = await session.get(PurchaseIntent, intent_id)
                assert intent is not None
                session.add(
                    PurchaseReversal(
                        id=f"rev_{uuid.uuid4().hex}",
                        organization_id="org_consultco",
                        purchase_intent_id=intent.id,
                        intent_hash=intent.intent_hash,
                        kind="REFUND",
                        status="REQUESTED",
                        requested_amount=Decimal("1.00"),
                        refunded_amount=Decimal("0.00"),
                        currency=intent.currency,
                        merchant_order_id="merchant_order_reset_proof",
                        provider_reference=None,
                        provider_adapter_id="fixture_reset_proof",
                        provider_confirmed=False,
                        reason_code="RESET_PROOF",
                        reason_hash="sha256:" + "a" * 64,
                        requested_by_actor_id="usr_requester",
                        safe_error_code=None,
                        completed_at=None,
                    )
                )
                session.add(
                    OutcomeCheckpoint(
                        id=f"outcome_{uuid.uuid4().hex}",
                        organization_id="org_consultco",
                        purchase_intent_id=intent.id,
                        decision_id=intent.decision_id,
                        decision_hash=intent.decision_hash,
                        solution_plan_id=intent.solution_plan_id,
                        metric_id="reset_proof_metric",
                        target_value=Decimal("1.000000"),
                        target_operator="gte",
                        observed_value=Decimal("0.000000"),
                        checkpoint_days=30,
                        measurement_started_at=now,
                        checkpoint_due_at=now + timedelta(days=30),
                        observed_at=now,
                        state="NOT_ACHIEVED",
                        source_class="HUMAN_ATTESTATION",
                        source_reference_hash="sha256:" + "b" * 64,
                        recorded_by_actor_id="usr_requester",
                        checkpoint_hash="sha256:" + "c" * 64,
                        preference_proposal=None,
                    )
                )

            try:
                await service.reset_demo("org_consultco")
            finally:
                async with database.transaction("org_consultco") as session:
                    await session.execute(
                        delete(PurchaseReversal).where(
                            PurchaseReversal.organization_id == "org_consultco"
                        )
                    )
                    await session.execute(
                        delete(OutcomeCheckpoint).where(
                            OutcomeCheckpoint.organization_id == "org_consultco"
                        )
                    )

            async with database.transaction("org_consultco") as session:
                reversal_count = await session.scalar(
                    select(func.count()).select_from(PurchaseReversal)
                )
                outcome_count = await session.scalar(
                    select(func.count()).select_from(OutcomeCheckpoint)
                )
            assert reversal_count == 0
            assert outcome_count == 0
        finally:
            await database.close()
