"""Create the restricted PostgreSQL login used by the Railway API service."""

from __future__ import annotations

import asyncio
import os

import psycopg
from psycopg import sql

from persistence.database import (
    _POSTGRES_RUNTIME_ROLE_QUERY,
    EXPECTED_ALEMBIC_HEADS,
    Database,
    DatabaseSettings,
)

ROLE_NAME = "sira_runtime"


def main() -> None:
    admin_url = os.environ["DATABASE_ADMIN_URL"].replace(
        "postgresql+psycopg://", "postgresql://", 1
    )
    password = os.environ["SIRA_DB_RUNTIME_PASSWORD"]
    rotate_password = os.environ.get("ROTATE_RUNTIME_DATABASE_PASSWORD", "false").lower() == "true"

    with psycopg.connect(admin_url, autocommit=True) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", (ROLE_NAME,)
        ).fetchone()
        if exists is None:
            connection.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB "
                    "NOCREATEROLE NOINHERIT NOBYPASSRLS"
                ).format(sql.Identifier(ROLE_NAME), sql.Literal(password))
            )
        elif rotate_password:
            connection.execute(
                sql.SQL(
                    "ALTER ROLE {} WITH LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB "
                    "NOCREATEROLE NOINHERIT NOBYPASSRLS"
                ).format(sql.Identifier(ROLE_NAME), sql.Literal(password))
            )

        role = sql.Identifier(ROLE_NAME)
        database = sql.Identifier(connection.info.dbname)
        connection.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(database, role))
        connection.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
        connection.execute(
            sql.SQL(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}"
            ).format(role)
        )
        connection.execute(
            sql.SQL("GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {}").format(
                role
            )
        )
        connection.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
            ).format(role)
        )
        connection.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                "GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {}"
            ).format(role)
        )

    runtime_url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    with psycopg.connect(runtime_url) as runtime_connection:
        with runtime_connection.cursor() as cursor:
            cursor.execute(str(_POSTGRES_RUNTIME_ROLE_QUERY))
            role_state = cursor.fetchone()
            assert role_state is not None
            unsafe = [
                column.name
                for column, value in zip(cursor.description or (), role_state, strict=True)
                if bool(value)
            ]
            if unsafe:
                raise RuntimeError("unsafe runtime database role: " + ", ".join(unsafe))
            cursor.execute("SELECT version_num FROM public.alembic_version")
            revisions = frozenset(str(row[0]) for row in cursor.fetchall())
            if revisions != EXPECTED_ALEMBIC_HEADS:
                raise RuntimeError(f"unexpected Alembic heads: {sorted(revisions)}")

    async def verify_async_runtime() -> None:
        database = Database(
            DatabaseSettings(
                database_url=os.environ["DATABASE_URL"],
                allow_unsafe_database_role=(
                    os.environ.get("ALLOW_UNSAFE_DATABASE_ROLE", "false").lower() == "true"
                ),
            )
        )
        try:
            if not await database.is_ready():
                raise RuntimeError("async runtime database verification failed")
        finally:
            await database.close()

    asyncio.run(verify_async_runtime())


if __name__ == "__main__":
    main()
