from __future__ import annotations

import pytest
from scripts.provision_cloud import _admin_url, _async_url
from sqlalchemy.engine import make_url


def test_admin_url_normalizes_console_connection_string() -> None:
    url = _admin_url(
        "postgresql://cluster_admin:secret@cluster.example:26257/sira"  # pragma: allowlist secret
        "?sslmode=verify-full"
    )

    assert url.drivername == "cockroachdb+psycopg"
    assert url.database == "sira"
    assert url.query["sslmode"] == "verify-full"


def test_async_url_scopes_identity_and_translates_tls_mode() -> None:
    admin = _admin_url(
        "cockroachdb+psycopg://admin:secret@cluster.example:26257/sira"  # pragma: allowlist secret
        "?sslmode=verify-full&sslrootcert=/tmp/root.crt"
    )

    rendered = _async_url(admin, "sira_app", "p@ss/word")  # pragma: allowlist secret
    parsed = make_url(rendered)

    assert parsed.drivername == "cockroachdb+asyncpg"
    assert parsed.username == "sira_app"
    assert parsed.password == "p@ss/word"  # pragma: allowlist secret
    assert parsed.query == {"ssl": "verify-full"}


def test_admin_url_requires_a_safe_named_database() -> None:
    with pytest.raises(ValueError, match="application database"):
        _admin_url("postgresql://admin:secret@cluster.example:26257/")  # pragma: allowlist secret
