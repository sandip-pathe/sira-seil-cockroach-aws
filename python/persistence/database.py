"""Async PostgreSQL engine and transaction-scoped tenant context."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

EXPECTED_ALEMBIC_HEADS = frozenset({"a1d4e7f9b203"})
logger = logging.getLogger(__name__)

_POSTGRES_RUNTIME_ROLE_QUERY = text(
    """
    SELECT
        role.rolsuper,
        role.rolbypassrls,
        role.rolcreatedb,
        role.rolcreaterole,
        role.rolreplication,
        NOT role.rolcanlogin AS cannot_login,
        current_user <> session_user AS assumed_role,
        database.datdba = role.oid AS owns_database,
        pg_has_role(role.oid, database.datdba, 'MEMBER') AS member_of_database_owner,
        EXISTS (
            SELECT 1
            FROM pg_catalog.pg_roles AS dangerous_role
            WHERE dangerous_role.oid <> role.oid
              AND (
                  dangerous_role.rolsuper
                  OR dangerous_role.rolbypassrls
                  OR dangerous_role.rolcreatedb
                  OR dangerous_role.rolcreaterole
                  OR dangerous_role.rolreplication
              )
              AND (
                  pg_has_role(role.oid, dangerous_role.oid, 'USAGE')
                  OR pg_has_role(role.oid, dangerous_role.oid, 'SET')
              )
        ) AS can_inherit_or_set_dangerous_role,
        EXISTS (
            SELECT 1
            FROM pg_catalog.pg_namespace AS owned_schema
            WHERE owned_schema.nspname = 'public'
              AND pg_has_role(role.oid, owned_schema.nspowner, 'MEMBER')
        ) AS owns_or_inherits_schema,
        EXISTS (
            SELECT 1
            FROM pg_catalog.pg_class AS relation
            JOIN pg_catalog.pg_namespace AS namespace
              ON namespace.oid = relation.relnamespace
            JOIN pg_catalog.pg_attribute AS attribute
              ON attribute.attrelid = relation.oid
             AND attribute.attname = 'organization_id'
             AND attribute.attnum > 0
             AND NOT attribute.attisdropped
            WHERE namespace.nspname = 'public'
              AND relation.relkind IN ('r', 'p')
              AND pg_has_role(role.oid, relation.relowner, 'MEMBER')
        ) AS owns_or_inherits_tenant_table,
        EXISTS (
            SELECT 1
            FROM pg_catalog.pg_class AS relation
            JOIN pg_catalog.pg_namespace AS namespace
              ON namespace.oid = relation.relnamespace
            WHERE namespace.nspname = 'public'
              AND relation.relkind IN ('r', 'p')
              AND EXISTS (
                  SELECT 1
                  FROM pg_catalog.pg_attribute AS attribute
                  WHERE attribute.attrelid = relation.oid
                    AND attribute.attname = 'organization_id'
                    AND attribute.attnum > 0
                    AND NOT attribute.attisdropped
              )
              AND (
                  NOT relation.relrowsecurity
                  OR NOT relation.relforcerowsecurity
                  OR (
                      relation.relname <> 'engagements'
                      AND (
                          NOT EXISTS (
                              SELECT 1
                              FROM pg_catalog.pg_policy AS access_policy
                              WHERE access_policy.polrelid = relation.oid
                                AND access_policy.polname = 'tenant_access'
                                AND access_policy.polcmd = '*'
                                AND access_policy.polpermissive
                                AND 0::oid = ANY(access_policy.polroles)
                          )
                          OR NOT EXISTS (
                              SELECT 1
                              FROM pg_catalog.pg_policy AS isolation_policy
                              WHERE isolation_policy.polrelid = relation.oid
                                AND isolation_policy.polname = 'tenant_isolation'
                                AND isolation_policy.polcmd = '*'
                                AND NOT isolation_policy.polpermissive
                                AND 0::oid = ANY(isolation_policy.polroles)
                          )
                      )
                  )
              )
        ) AS tenant_rls_or_policy_gap,
        EXISTS (
            SELECT 1
            FROM (
                VALUES
                    ('engagement_party_select', 'r'),
                    ('engagement_owner_insert', 'a'),
                    ('engagement_party_update', 'w'),
                    ('engagement_owner_delete', 'd')
            ) AS expected_policy(policy_name, command)
            WHERE NOT EXISTS (
                SELECT 1
                FROM pg_catalog.pg_policy AS policy
                JOIN pg_catalog.pg_class AS relation
                  ON relation.oid = policy.polrelid
                JOIN pg_catalog.pg_namespace AS namespace
                  ON namespace.oid = relation.relnamespace
                WHERE namespace.nspname = 'public'
                  AND relation.relname = 'engagements'
                  AND relation.relkind IN ('r', 'p')
                  AND policy.polname = expected_policy.policy_name
                  AND policy.polcmd::text = expected_policy.command
                  AND policy.polpermissive
                  AND 0::oid = ANY(policy.polroles)
            )
        ) AS engagement_policy_gap,
        NOT EXISTS (
            SELECT 1
            FROM pg_catalog.pg_trigger AS guard_trigger
            JOIN pg_catalog.pg_class AS relation
              ON relation.oid = guard_trigger.tgrelid
            JOIN pg_catalog.pg_namespace AS namespace
              ON namespace.oid = relation.relnamespace
            JOIN pg_catalog.pg_proc AS routine
              ON routine.oid = guard_trigger.tgfoid
            JOIN pg_catalog.pg_namespace AS routine_namespace
              ON routine_namespace.oid = routine.pronamespace
            WHERE namespace.nspname = 'public'
              AND relation.relname = 'engagements'
              AND relation.relkind IN ('r', 'p')
              AND guard_trigger.tgname = 'engagement_party_update_guard'
              AND NOT guard_trigger.tgisinternal
              AND guard_trigger.tgenabled IN ('O', 'A')
              AND guard_trigger.tgtype & 1 = 1
              AND guard_trigger.tgtype & 2 = 2
              AND guard_trigger.tgtype & 4 = 4
              AND guard_trigger.tgtype & 16 = 16
              AND routine_namespace.nspname = 'public'
              AND routine.proname = 'enforce_engagement_party_update'
              AND routine.pronargs = 0
        ) AS engagement_trigger_gap
    FROM pg_catalog.pg_roles AS role
    JOIN pg_catalog.pg_database AS database
      ON database.datname = current_database()
    WHERE role.rolname = current_user
    """
)


class DatabaseSettings(BaseSettings):
    """Database configuration loaded only by server processes."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    database_url: str = Field(
        default="postgresql+asyncpg://localhost:5432/sira",
        validation_alias="DATABASE_URL",
    )
    allow_unsafe_database_role: bool = Field(
        default=False, validation_alias="ALLOW_UNSAFE_DATABASE_ROLE"
    )
    sql_echo: bool = Field(default=False, validation_alias="SQL_ECHO")


class Database:
    """Own the engine and provide tenant-scoped atomic units of work.

    PostgreSQL RLS reads ``app.organization_id``. It is set with transaction
    scope from authenticated server context, never from a request body.
    """

    def __init__(self, settings: DatabaseSettings | None = None) -> None:
        self.settings = settings or DatabaseSettings()
        self.engine: AsyncEngine = create_async_engine(
            self.settings.database_url,
            echo=self.settings.sql_echo,
            pool_pre_ping=True,
        )
        self.sessions = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    @asynccontextmanager
    async def transaction(self, organization_id: str) -> AsyncIterator[AsyncSession]:
        if not organization_id or organization_id.strip() != organization_id:
            raise ValueError("A verified organization_id is required")

        async with self.sessions() as session, session.begin():
            bind = session.get_bind()
            if bind.dialect.name == "postgresql":
                # set_config(..., true) is equivalent to SET LOCAL and avoids SQL interpolation.
                await session.execute(
                    text("SELECT set_config('app.organization_id', :organization_id, true)"),
                    {"organization_id": organization_id},
                )
            yield session

    async def close(self) -> None:
        await self.engine.dispose()

    async def is_ready(
        self,
        *,
        expected_alembic_heads: frozenset[str] = EXPECTED_ALEMBIC_HEADS,
    ) -> bool:
        """Prove that the database is reachable and the PostgreSQL login is safe."""

        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
                if connection.dialect.name != "postgresql":
                    return True

                role_state = (await connection.execute(_POSTGRES_RUNTIME_ROLE_QUERY)).one_or_none()
                if (
                    not self.settings.allow_unsafe_database_role
                    and (role_state is None or any(bool(value) for value in role_state))
                ):
                    logger.error("Database runtime role safety verification failed")
                    return False

                revisions = frozenset(
                    str(revision)
                    for revision in (
                        await connection.execute(
                            text("SELECT version_num FROM public.alembic_version")
                        )
                    ).scalars()
                )
                ready = revisions == expected_alembic_heads
                if not ready:
                    logger.error("Database schema revision verification failed")
                return ready
        except Exception:
            logger.exception("Database readiness check failed")
            return False
