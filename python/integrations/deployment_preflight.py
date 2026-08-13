"""Credential-safe validation of deployment prerequisites."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy.engine import URL, make_url

_AWS_ACCOUNT_ID = re.compile(r"\d{12}\Z")
_STAGE = re.compile(r"[a-z][a-z0-9-]{1,30}\Z")
_EXPECTED_SECRET_KEYS = frozenset(
    {
        "DATABASE_URL",
        "SIRA_WORKER_DATABASE_URL",
        "SIRA_CATALOG_DATABASE_URL",
        "BROWSER_RETURN_SIGNING_KEY",
        "GUEST_SESSION_SIGNING_KEY",
    }
)


@dataclass(frozen=True, slots=True)
class DeploymentPreflightResult:
    status: str
    checks: Mapping[str, bool]
    account_hash: str
    region: str
    stage: str
    database_host_hash: str | None


def _digest(value: str) -> str:
    return "sha256:" + sha256(value.encode("utf-8")).hexdigest()


def validate_database_url(raw: str) -> URL:
    """Require a remote TLS Cockroach URL without leaking it into reports."""

    parsed = make_url(raw.strip())
    if parsed.get_backend_name() not in {"cockroachdb", "postgresql"}:
        raise ValueError("database URL must use a Cockroach-compatible scheme")
    if not parsed.database or parsed.database in {"defaultdb", "postgres", "system"}:
        raise ValueError("database URL must name the dedicated application database")
    host = (parsed.host or "").lower()
    if not host or host in {"localhost", "127.0.0.1", "::1", "cockroach"}:
        raise ValueError("deployment requires a remote CockroachDB Cloud host")
    ssl_mode = str(parsed.query.get("sslmode", parsed.query.get("ssl", ""))).lower()
    if ssl_mode not in {"verify-full", "verify-ca"}:
        raise ValueError("deployment requires verified TLS")
    return parsed


def validate_runtime_secret(values: Mapping[str, object]) -> None:
    """Validate secret shape and role separation without returning secret values."""

    keys = frozenset(values)
    if keys != _EXPECTED_SECRET_KEYS:
        raise ValueError("runtime secret has an unexpected key set")
    urls = {
        key: validate_database_url(str(values[key]))
        for key in (
            "DATABASE_URL",
            "SIRA_WORKER_DATABASE_URL",
            "SIRA_CATALOG_DATABASE_URL",
        )
    }
    if len({url.username for url in urls.values()}) != 3:
        raise ValueError("runtime SQL identities must be distinct")
    if len({(url.host, url.port, url.database) for url in urls.values()}) != 1:
        raise ValueError("runtime SQL identities must target one application database")
    for key in ("BROWSER_RETURN_SIGNING_KEY", "GUEST_SESSION_SIGNING_KEY"):
        if len(str(values[key]).encode("utf-8")) < 32:
            raise ValueError(f"{key} must contain at least 32 bytes")
    if values["BROWSER_RETURN_SIGNING_KEY"] == values["GUEST_SESSION_SIGNING_KEY"]:
        raise ValueError("browser-return and guest-session signing keys must be distinct")


def build_preflight_result(
    *,
    account_id: str,
    configured_region: str,
    caller_region: str,
    stage: str,
    runtime_secret: Mapping[str, object],
    secret_arn: str,
) -> DeploymentPreflightResult:
    if not _AWS_ACCOUNT_ID.fullmatch(account_id):
        raise ValueError("AWS caller account is invalid")
    if not configured_region.strip() or configured_region != caller_region:
        raise ValueError("AWS caller region does not match the deployment region")
    if not _STAGE.fullmatch(stage):
        raise ValueError("deployment stage is invalid")
    if not secret_arn.startswith("arn:"):
        raise ValueError("runtime secret ARN is unavailable")
    validate_runtime_secret(runtime_secret)
    database = validate_database_url(str(runtime_secret["DATABASE_URL"]))
    checks = {
        "aws_identity": True,
        "region_match": True,
        "runtime_secret_shape": True,
        "remote_cockroach": True,
        "verified_tls": True,
        "separate_sql_roles": True,
        "separate_signing_keys": True,
    }
    return DeploymentPreflightResult(
        status="PASS",
        checks=checks,
        account_hash=_digest(account_id),
        region=configured_region,
        stage=stage,
        database_host_hash=_digest(str(database.host)),
    )
