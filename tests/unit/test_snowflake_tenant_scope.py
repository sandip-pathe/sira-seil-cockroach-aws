from typing import Any

import pytest
from sira_api.snowflake_service import (
    SnowflakeDecisionNotFound,
    SnowflakeDecisionService,
)


class _Cursor:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, tuple[Any, ...] | None]] = []
        self.description: list[Any] = []

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> None:
        self.calls.append((sql, params))

    def fetchone(self) -> Any:
        return self.rows.pop(0) if self.rows else None

    def fetchall(self) -> list[Any]:
        return []


class _Connection:
    def __init__(self, cursor: _Cursor) -> None:
        self._cursor = cursor

    def cursor(self) -> _Cursor:
        return self._cursor

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass


def _service(cursor: _Cursor) -> SnowflakeDecisionService:
    service = object.__new__(SnowflakeDecisionService)
    service._connect = lambda: _Connection(cursor)  # type: ignore[method-assign]
    return service


def test_decision_lookup_is_scoped_to_organization() -> None:
    cursor = _Cursor([None])

    result = _service(cursor)._get_decision("sfreq_other", organization_id="org_current")

    assert result is None
    assert "req.organization_id = %s" in cursor.calls[0][0]
    assert cursor.calls[0][1] == ("sfreq_other", "org_current")


def test_approval_rejects_a_decision_from_another_organization() -> None:
    cursor = _Cursor([None])

    with pytest.raises(SnowflakeDecisionNotFound):
        _service(cursor)._approve(
            organization_id="org_current",
            decision_hash="sha256:" + "a" * 64,
            actor_id="user_current",
            actor_role="BUYER_APPROVER",
        )

    assert "req.organization_id = %s" in cursor.calls[0][0]
    assert len(cursor.calls) == 1
