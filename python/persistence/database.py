"""CockroachDB engine, tenant context, readiness, and transaction retries."""

from __future__ import annotations

import asyncio
import logging
import random
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import TypeVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

EXPECTED_ALEMBIC_HEADS: frozenset[str] = frozenset({"cdb0007"})
logger = logging.getLogger(__name__)

_ORGANIZATION_ID = re.compile(r"[A-Za-z0-9_-]{1,48}\Z")
_TENANT_RLS_GAP_QUERY = text(
    """
    SELECT count(*)
    FROM information_schema.columns AS columns
    JOIN pg_catalog.pg_class AS relation ON relation.relname = columns.table_name
    JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = relation.relnamespace
    WHERE columns.table_schema = 'public'
      AND columns.column_name = 'organization_id'
      AND namespace.nspname = columns.table_schema
      AND relation.relkind = 'r'
      AND (NOT relation.relrowsecurity OR NOT relation.relforcerowsecurity)
    """
)
_UNSAFE_RUNTIME_ROLE_QUERY = text(
    """
    SELECT (
        role.rolsuper
        OR role.rolcreatedb
        OR role.rolcreaterole
        OR role.rolbypassrls
        OR pg_has_role(current_user, 'admin', 'MEMBER')
        OR EXISTS (
            SELECT 1
            FROM pg_catalog.pg_tables
            WHERE schemaname = 'public' AND tableowner = current_user
        )
    )
    FROM pg_catalog.pg_roles AS role
    WHERE role.rolname = current_user
    """
)

ResultT = TypeVar("ResultT")
RetryableWork = Callable[[AsyncSession], Awaitable[ResultT]]


class DatabaseSettings(BaseSettings):
    """Database configuration loaded only by server processes."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    database_url: str = Field(
        default="cockroachdb+asyncpg://sira_app@127.0.0.1:26257/sira?ssl=disable",
        validation_alias="DATABASE_URL",
    )
    sql_echo: bool = Field(default=False, validation_alias="SQL_ECHO")


def _validated_organization_id(organization_id: str) -> str:
    if not _ORGANIZATION_ID.fullmatch(organization_id):
        raise ValueError(
            "organization_id must contain 1-48 ASCII letters, digits, underscores, or hyphens"
        )
    return organization_id


def _sqlstate(error: BaseException) -> str | None:
    """Find a driver SQLSTATE without coupling the retry kernel to one driver."""

    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        for attribute in ("sqlstate", "pgcode"):
            value = getattr(current, attribute, None)
            if isinstance(value, str):
                return value
        wrapped = getattr(current, "orig", None)
        current = (
            wrapped
            if isinstance(wrapped, BaseException)
            else current.__cause__ or current.__context__
        )
    return None


class Database:
    """Own the engine and provide tenant-scoped atomic units of work.

    CockroachDB RLS reads the organization from transaction-local
    ``application_name``. The value comes from authenticated server context and
    is validated before it reaches SQL. Retryable callbacks must contain only
    database work; network calls and other side effects belong behind the outbox.
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

    async def _set_tenant_context(self, session: AsyncSession, organization_id: str) -> None:
        bind = session.get_bind()
        if bind.dialect.name == "cockroachdb":
            await session.execute(
                text("SELECT set_config('application_name', :application_name, true)"),
                {"application_name": f"sira-api.{organization_id}"},
            )
        elif bind.dialect.name == "postgresql":
            # Retained only for local migration compatibility; production rejects PostgreSQL.
            await session.execute(
                text("SELECT set_config('app.organization_id', :organization_id, true)"),
                {"organization_id": organization_id},
            )

    @asynccontextmanager
    async def transaction(self, organization_id: str) -> AsyncIterator[AsyncSession]:
        tenant = _validated_organization_id(organization_id)
        async with self.sessions() as session, session.begin():
            await self._set_tenant_context(session, tenant)
            yield session

    async def run_retryable(
        self,
        organization_id: str,
        work: RetryableWork[ResultT],
        *,
        max_attempts: int = 5,
        base_delay_seconds: float = 0.025,
    ) -> ResultT:
        """Run one database-only unit of work with bounded Cockroach retries."""

        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        tenant = _validated_organization_id(organization_id)
        for attempt in range(1, max_attempts + 1):
            try:
                async with self.transaction(tenant) as session:
                    return await work(session)
            except DBAPIError as error:
                if _sqlstate(error) != "40001" or attempt == max_attempts:
                    raise
                delay = base_delay_seconds * (2 ** (attempt - 1))
                jitter = random.uniform(0, delay * 0.25)  # noqa: S311
                logger.info("Retrying CockroachDB transaction after SQLSTATE 40001")
                await asyncio.sleep(delay + jitter)
        raise AssertionError("retry loop exhausted without returning or raising")

    async def close(self) -> None:
        await self.engine.dispose()

    async def is_ready(
        self,
        *,
        expected_alembic_heads: frozenset[str] = EXPECTED_ALEMBIC_HEADS,
    ) -> bool:
        """Prove connectivity, schema revision, runtime identity, and tenant RLS."""

        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
                if connection.dialect.name == "sqlite":
                    return True
                if connection.dialect.name != "cockroachdb":
                    logger.warning("Database readiness failed: CockroachDB is required")
                    return False

                current_user = str(await connection.scalar(text("SELECT current_user")))
                if bool(await connection.scalar(_UNSAFE_RUNTIME_ROLE_QUERY)):
                    logger.warning(
                        "Database readiness failed: unsafe runtime identity %s", current_user
                    )
                    return False

                revisions = frozenset(
                    str(revision)
                    for revision in (
                        await connection.execute(
                            text("SELECT version_num FROM public.alembic_version")
                        )
                    ).scalars()
                )
                if revisions != expected_alembic_heads:
                    logger.warning(
                        "Database readiness failed: Alembic heads %s, expected %s",
                        sorted(revisions),
                        sorted(expected_alembic_heads),
                    )
                    return False
                if int(await connection.scalar(_TENANT_RLS_GAP_QUERY) or 0) != 0:
                    logger.warning(
                        "Database readiness failed: tenant tables are missing forced RLS"
                    )
                    return False
                return True
        except Exception as error:
            logger.warning(
                "Database readiness failed with %s: %s",
                type(error).__name__,
                error,
            )
            return False
