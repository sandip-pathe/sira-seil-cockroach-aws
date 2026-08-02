"""Alembic environment using the administrative PostgreSQL connection."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import engine_from_config, pool

from persistence.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


class MigrationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    database_admin_url: str = Field(default="", validation_alias="DATABASE_ADMIN_URL")


def _database_url() -> str:
    value = MigrationSettings().database_admin_url or config.get_main_option("sqlalchemy.url")
    if not value:
        raise RuntimeError("DATABASE_ADMIN_URL is required for migrations")
    # Migrations use a synchronous driver even when the API uses asyncpg.
    return value.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=False,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=False,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
