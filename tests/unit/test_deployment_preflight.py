from __future__ import annotations

import pytest

from integrations.deployment_preflight import (
    build_preflight_result,
    validate_database_url,
    validate_runtime_secret,
)


def _runtime_secret() -> dict[str, str]:
    base = "cluster.example.cockroachlabs.cloud:26257/sira?sslmode=verify-full"
    return {
        "DATABASE_URL": f"cockroachdb+asyncpg://sira_app:password@{base}",
        "SIRA_WORKER_DATABASE_URL": f"cockroachdb+asyncpg://sira_worker_app:password@{base}",
        "SIRA_CATALOG_DATABASE_URL": f"cockroachdb+asyncpg://sira_catalog_app:password@{base}",
        "BROWSER_RETURN_SIGNING_KEY": "b" * 48,
        "GUEST_SESSION_SIGNING_KEY": "g" * 48,
    }


def test_deployment_preflight_returns_only_sanitized_evidence() -> None:
    result = build_preflight_result(
        account_id="123456789012",
        configured_region="us-east-1",
        caller_region="us-east-1",
        stage="hackathon",
        runtime_secret=_runtime_secret(),
        secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:sira",
    )

    assert result.status == "PASS"
    assert all(result.checks.values())
    assert result.account_hash.startswith("sha256:")
    assert result.database_host_hash is not None
    assert "123456789012" not in repr(result)
    assert "cluster.example" not in repr(result)


@pytest.mark.parametrize(
    "url",
    [
        "cockroachdb+asyncpg://user:password@127.0.0.1:26257/sira?ssl=disable",
        "cockroachdb+asyncpg://user:password@cluster.example:26257/defaultdb?ssl=verify-full",
        "cockroachdb+asyncpg://user:password@cluster.example:26257/sira?ssl=require",
    ],
)
def test_deployment_preflight_rejects_local_system_or_unverified_database(url: str) -> None:
    with pytest.raises(ValueError):
        validate_database_url(url)


def test_runtime_secret_requires_role_and_signing_key_separation() -> None:
    secret = _runtime_secret()
    secret["SIRA_WORKER_DATABASE_URL"] = secret["DATABASE_URL"]
    with pytest.raises(ValueError, match="identities must be distinct"):
        validate_runtime_secret(secret)

    secret = _runtime_secret()
    secret["GUEST_SESSION_SIGNING_KEY"] = secret["BROWSER_RETURN_SIGNING_KEY"]
    with pytest.raises(ValueError, match="signing keys must be distinct"):
        validate_runtime_secret(secret)
