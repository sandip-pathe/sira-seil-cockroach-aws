from __future__ import annotations

import pytest
from scripts.cockroach_upgrade_drill import sync_url, validate_source_database


def test_upgrade_drill_normalizes_to_the_sync_cockroach_driver() -> None:
    url = sync_url("cockroachdb+asyncpg://root@localhost:26257/sira?sslmode=disable")

    assert url.drivername == "cockroachdb+psycopg"
    assert url.database == "sira"
    assert url.query["connect_timeout"] == "10"


@pytest.mark.parametrize("database", ["", "defaultdb", "postgres", "system", "unsafe-name"])
def test_upgrade_drill_rejects_system_or_unsafe_source_database(database: str) -> None:
    with pytest.raises(ValueError, match="Refusing upgrade drill"):
        validate_source_database(database)


def test_upgrade_drill_accepts_explicit_application_database() -> None:
    validate_source_database("sira")
