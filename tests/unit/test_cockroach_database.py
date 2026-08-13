from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from persistence.database import (
    Database,
    DatabaseSettings,
    RetryExhausted,
    _validated_organization_id,
)


class RetryError(Exception):
    sqlstate = "40001"


async def test_retryable_work_gets_a_fresh_session_after_40001() -> None:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    session_ids: list[int] = []

    async def work(session: object) -> str:
        session_ids.append(id(session))
        if len(session_ids) == 1:
            raise DBAPIError("SELECT 1", {}, RetryError(), False)
        return "committed"

    try:
        result = await database.run_retryable("org_test", work, base_delay_seconds=0)
    finally:
        await database.close()

    assert result == "committed"
    assert len(session_ids) == 2
    assert session_ids[0] != session_ids[1]


async def test_non_retryable_database_error_is_not_replayed() -> None:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    attempts = 0

    async def work(session: object) -> None:
        nonlocal attempts
        attempts += 1
        raise DBAPIError("SELECT 1", {}, ValueError("bad query"), False)

    try:
        try:
            await database.run_retryable("org_test", work, base_delay_seconds=0)
        except DBAPIError:
            pass
        else:
            raise AssertionError("non-retryable error should be raised")
    finally:
        await database.close()

    assert attempts == 1


async def test_retry_exhaustion_is_visible_and_bounded() -> None:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    sessions: list[int] = []

    async def work(session: object) -> None:
        sessions.append(id(session))
        raise DBAPIError("SELECT 1", {}, RetryError(), False)

    try:
        try:
            await database.run_retryable("org_test", work, max_attempts=3, base_delay_seconds=0)
        except RetryExhausted as error:
            assert error.attempts == 3
            assert error.sqlstate == "40001"
        else:
            raise AssertionError("retry exhaustion should be raised")
    finally:
        await database.close()

    assert len(sessions) == 3
    assert len(set(sessions)) == 3


async def test_sqlite_transaction_does_not_require_session_variables() -> None:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    try:
        async with database.transaction("org_test") as session:
            assert await session.scalar(text("SELECT 1")) == 1
    finally:
        await database.close()


def test_organization_id_is_strictly_bounded() -> None:
    assert _validated_organization_id("org_valid-01") == "org_valid-01"
    for invalid in ("", " org", "org.with.dot", "x" * 49, "org/escape"):
        try:
            _validated_organization_id(invalid)
        except ValueError:
            continue
        raise AssertionError(f"invalid organization id accepted: {invalid!r}")
