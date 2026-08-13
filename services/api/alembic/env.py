"""Alembic environment using the administrative CockroachDB connection."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import JSON, Integer, Text, engine_from_config, pool

from persistence import qualification_models as _qualification_models  # noqa: F401
from persistence.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
_PARTIAL_INDEX_NAMES = {
    "uq_charged_or_uncertain_intent",
    "uq_open_payment_attempt",
    "uq_provider_event_ref",
    "uq_qualification_current_decision",
}


def _include_object(
    _object: object,
    name: str | None,
    object_type: str,
    reflected: bool,
    compare_to: object | None,
) -> bool:
    # The Cockroach adapter reflects index columns as expression objects, which
    # otherwise produces false remove/add pairs on every autogenerate pass.
    if object_type == "index":
        if name in _PARTIAL_INDEX_NAMES:
            return False
        return not reflected and compare_to is None
    # Cockroach reflects partial unique indexes as constraints. The indexes are
    # maintained explicitly by migrations and verified by integration tests.
    return not (object_type == "unique_constraint" and name in _PARTIAL_INDEX_NAMES)


def _compare_cockroach_type(
    migration_context: object,
    _inspected_column: object,
    _metadata_column: object,
    inspected_type: object,
    metadata_type: object,
) -> bool | None:
    dialect = getattr(migration_context, "dialect", None)
    if getattr(dialect, "name", None) != "cockroachdb":
        return None
    if isinstance(inspected_type, JSON) and isinstance(metadata_type, JSON):
        return False
    # CockroachDB's INT family is 64-bit and reflects SQLAlchemy BigInteger as INTEGER.
    if isinstance(inspected_type, Integer) and isinstance(metadata_type, Integer):
        return False
    if isinstance(metadata_type, Text):
        return False
    return None


class MigrationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    database_admin_url: str = Field(default="", validation_alias="DATABASE_ADMIN_URL")


def _database_url() -> str:
    value = MigrationSettings().database_admin_url or config.get_main_option("sqlalchemy.url")
    if not value:
        raise RuntimeError("DATABASE_ADMIN_URL is required for migrations")
    # Migrations use a synchronous driver even when the API uses asyncpg.
    return value.replace("cockroachdb+asyncpg://", "cockroachdb+psycopg://", 1)


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
            compare_type=_compare_cockroach_type,
            include_object=_include_object,
            render_as_batch=False,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
