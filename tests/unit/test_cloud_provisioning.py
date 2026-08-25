from __future__ import annotations

import json

import pytest
from scripts.provision_cloud import _USERS, _admin_url, _async_url, _xray_logs_policy
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


def test_runtime_users_receive_only_their_narrow_composed_roles() -> None:
    assert _USERS == {
        "sira_app": ("sira_runtime", "sira_api_tenant_bootstrap"),
        "sira_worker_app": (
            "sira_runtime",
            "sira_qualification_worker",
            "sira_worker_directory_reader",
        ),
        "sira_catalog_app": ("sira_catalog_reader",),
    }


def test_xray_logs_policy_is_account_and_region_scoped() -> None:
    policy = json.loads(_xray_logs_policy(account_id="123456789012", region="us-east-1"))
    statement = policy["Statement"][0]

    assert statement["Principal"] == {"Service": "xray.amazonaws.com"}
    assert statement["Action"] == "logs:PutLogEvents"
    assert statement["Condition"] == {
        "ArnLike": {"aws:SourceArn": "arn:aws:xray:us-east-1:123456789012:*"},
        "StringEquals": {"aws:SourceAccount": "123456789012"},
    }
    assert statement["Resource"] == [
        "arn:aws:logs:us-east-1:123456789012:log-group:aws/spans:*",
        "arn:aws:logs:us-east-1:123456789012:log-group:/aws/application-signals/data:*",
    ]
