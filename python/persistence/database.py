"""Async PostgreSQL engine and transaction-scoped tenant context."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class DatabaseSettings(BaseSettings):
    """Database configuration loaded only by server processes."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    database_url: str = Field(
        default="postgresql+asyncpg://localhost:5432/sira",
        validation_alias="DATABASE_URL",
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
