"""Provision Cockroach runtime identities and the AWS runtime secret.

The administrative URL is read from DATABASE_ADMIN_URL. Generated credentials
are sent directly to CockroachDB and Secrets Manager and are never printed or
written to the repository.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,62}\Z")
_USERS: Mapping[str, str] = {
    "sira_app": "sira_runtime",
    "sira_worker_app": "sira_runtime",
    "sira_catalog_app": "sira_catalog_reader",
}
_ORGANIZATIONS: Sequence[tuple[str, str]] = (
    ("org_consultco", "ConsultCo Demo Buyer"),
    ("org_seller_a", "Atlas Seller"),
    ("org_seller_b", "Beacon Seller"),
)


@dataclass(frozen=True, slots=True)
class ProvisionedRuntime:
    database_name: str
    runtime_secret: Mapping[str, str]


def _admin_url(raw: str) -> URL:
    if not raw.strip():
        raise ValueError("DATABASE_ADMIN_URL is required")
    parsed = make_url(raw.strip())
    database = parsed.database or ""
    if not _IDENTIFIER.fullmatch(database):
        raise ValueError("the administrative URL must name a valid application database")
    return parsed.set(drivername="cockroachdb+psycopg")


def _async_url(admin: URL, username: str, password: str) -> str:
    query = dict(admin.query)
    ssl_mode = query.pop("sslmode", query.pop("ssl", "verify-full"))
    query.pop("sslrootcert", None)
    query.pop("sslcert", None)
    query.pop("sslkey", None)
    query["ssl"] = ssl_mode
    return admin.set(
        drivername="cockroachdb+asyncpg",
        username=username,
        password=password,
        query=query,
    ).render_as_string(hide_password=False)


def _migrate(admin_url: URL) -> None:
    previous = os.environ.get("DATABASE_ADMIN_URL")
    os.environ["DATABASE_ADMIN_URL"] = admin_url.render_as_string(hide_password=False)
    try:
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_ADMIN_URL", None)
        else:
            os.environ["DATABASE_ADMIN_URL"] = previous


def provision_database(admin_url: URL) -> ProvisionedRuntime:
    _migrate(admin_url)
    passwords = {username: secrets.token_urlsafe(36) for username in _USERS}
    engine = create_engine(admin_url, pool_pre_ping=True)
    try:
        for username, role in _USERS.items():
            with engine.begin() as connection:
                connection.execute(text(f'CREATE USER IF NOT EXISTS "{username}"'))
                connection.execute(
                    text(f'ALTER USER "{username}" WITH PASSWORD :password'),
                    {"password": passwords[username]},
                )
                connection.execute(text(f'GRANT "{role}" TO "{username}"'))
                connection.execute(
                    text(f'GRANT CONNECT ON DATABASE "{admin_url.database}" TO "{username}"')
                )
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPSERT INTO organizations (id, name, version) "
                    "VALUES (:id, :name, 1)"
                ),
                [{"id": organization_id, "name": name} for organization_id, name in _ORGANIZATIONS],
            )
    finally:
        engine.dispose()

    runtime_secret = {
        "DATABASE_URL": _async_url(admin_url, "sira_app", passwords["sira_app"]),
        "SIRA_WORKER_DATABASE_URL": _async_url(
            admin_url, "sira_worker_app", passwords["sira_worker_app"]
        ),
        "SIRA_CATALOG_DATABASE_URL": _async_url(
            admin_url, "sira_catalog_app", passwords["sira_catalog_app"]
        ),
        "BROWSER_RETURN_SIGNING_KEY": secrets.token_urlsafe(48),
        "GUEST_SESSION_SIGNING_KEY": secrets.token_urlsafe(48),
    }
    return ProvisionedRuntime(str(admin_url.database), runtime_secret)


def put_runtime_secret(
    *,
    secret_name: str,
    values: Mapping[str, str],
    region: str,
    profile: str | None,
) -> str:
    import boto3  # type: ignore[import-untyped]
    from botocore.exceptions import ClientError  # type: ignore[import-untyped]

    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    client = session.client("secretsmanager", region_name=region)
    body = json.dumps(values, sort_keys=True, separators=(",", ":"))
    try:
        response: Mapping[str, Any] = client.put_secret_value(
            SecretId=secret_name,
            SecretString=body,
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "ResourceNotFoundException":
            raise
        response = client.create_secret(Name=secret_name, SecretString=body)
    return str(response.get("ARN", ""))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", default="hackathon")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"))
    parser.add_argument("--profile", default=os.getenv("AWS_PROFILE") or None)
    return parser


def main() -> None:
    args = _parser().parse_args()
    admin = _admin_url(os.getenv("DATABASE_ADMIN_URL", ""))
    provisioned = provision_database(admin)
    secret_name = f"sira-{args.stage}/runtime"
    secret_arn = put_runtime_secret(
        secret_name=secret_name,
        values=provisioned.runtime_secret,
        region=args.region,
        profile=args.profile,
    )
    sys.stdout.write(
        json.dumps(
            {
                "database": provisioned.database_name,
                "organizations": [item[0] for item in _ORGANIZATIONS],
                "runtime_secret": secret_name,
                "runtime_secret_arn_configured": bool(secret_arn),
            },
            sort_keys=True,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
