"""Create the restricted PostgreSQL login used by the Railway API service."""

from __future__ import annotations

import os

import psycopg
from psycopg import sql


ROLE_NAME = "sira_runtime"


def main() -> None:
    admin_url = os.environ["DATABASE_ADMIN_URL"].replace(
        "postgresql+psycopg://", "postgresql://", 1
    )
    password = os.environ["SIRA_DB_RUNTIME_PASSWORD"]

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
        else:
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
            sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}")
            .format(role)
        )
        connection.execute(
            sql.SQL("GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {}")
            .format(role)
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


if __name__ == "__main__":
    main()
