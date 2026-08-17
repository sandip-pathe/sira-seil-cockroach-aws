"""Prove a disposable CockroachDB upgrade from the prior supported head."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import secrets
import sys
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
load_dotenv(ROOT / ".env", override=False)

logger = logging.getLogger(__name__)

_SAFE_DATABASE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_SYSTEM_DATABASES = frozenset({"defaultdb", "postgres", "system"})
_FROM_REVISION = "cdb0017"
_TO_REVISION = "cdb0018"


def sync_url(raw: str, database: str | None = None) -> URL:
    parsed = make_url(raw.strip())
    if parsed.drivername.split("+", 1)[0] != "cockroachdb":
        raise ValueError("CockroachDB administrative URL is required")
    query = dict(parsed.query)
    query.setdefault("connect_timeout", "10")
    return parsed.set(
        drivername="cockroachdb+psycopg",
        database=database or parsed.database,
        query=query,
    )


def validate_source_database(name: str) -> None:
    if not _SAFE_DATABASE.fullmatch(name) or name in _SYSTEM_DATABASES:
        raise ValueError("Refusing upgrade drill for a missing, system, or unsafe database name")


def alembic_config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "services" / "api" / "alembic"))
    return config


def inspect_revision(url: URL) -> dict[str, Any]:
    engine = create_engine(url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
            table_count = connection.scalar(
                text(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
                )
            )
            handoff_table = connection.scalar(
                text(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_schema = 'public' "
                    "AND table_name = 'bilateral_exchange_handoffs'"
                )
            )
            forced_rls = connection.scalar(
                text(
                    "SELECT count(*) FROM pg_catalog.pg_class c "
                    "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'public' "
                    "AND c.relname = 'bilateral_exchange_handoffs' "
                    "AND c.relrowsecurity AND c.relforcerowsecurity"
                )
            )
            policies = connection.scalar(
                text(
                    "SELECT count(*) FROM pg_catalog.pg_policies "
                    "WHERE schemaname = 'public' "
                    "AND tablename = 'bilateral_exchange_handoffs'"
                )
            )
        return {
            "revision": str(revision),
            "table_count": int(table_count or 0),
            "handoff_table_present": bool(handoff_table),
            "handoff_forced_rls": bool(forced_rls),
            "handoff_policy_count": int(policies or 0),
        }
    finally:
        engine.dispose()


def run(database_url: str, *, output: Path) -> dict[str, Any]:
    source_url = sync_url(database_url)
    source_database = source_url.database or ""
    validate_source_database(source_database)
    temporary_database = f"sira_upgrade_drill_{secrets.token_hex(6)}"
    temporary_url = sync_url(database_url, temporary_database)
    admin = create_engine(source_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    created = False
    previous_admin_url = os.environ.get("DATABASE_ADMIN_URL")
    report: dict[str, Any] = {
        "schema_version": "sira.cockroach-upgrade-drill.v1",
        "status": "FAIL",
        "from_revision": _FROM_REVISION,
        "to_revision": _TO_REVISION,
        "temporary_database_removed": False,
    }
    try:
        with admin.connect() as connection:
            exists = connection.scalar(
                text("SELECT count(*) FROM [SHOW DATABASES] WHERE database_name = :name"),
                {"name": temporary_database},
            )
            if exists:
                raise RuntimeError("Generated upgrade target already exists")
            connection.execute(text(f'CREATE DATABASE "{temporary_database}"'))
            created = True

        os.environ["DATABASE_ADMIN_URL"] = temporary_url.render_as_string(hide_password=False)
        config = alembic_config()
        command.upgrade(config, _FROM_REVISION)
        before = inspect_revision(temporary_url)
        command.upgrade(config, _TO_REVISION)
        after = inspect_revision(temporary_url)

        checks = {
            "started_at_prior_head": before["revision"] == _FROM_REVISION,
            "new_table_absent_before_upgrade": not before["handoff_table_present"],
            "finished_at_current_head": after["revision"] == _TO_REVISION,
            "new_table_present_after_upgrade": after["handoff_table_present"],
            "new_table_forces_rls": after["handoff_forced_rls"],
            "new_table_has_three_runtime_policies": after["handoff_policy_count"] == 3,
            "upgrade_did_not_remove_tables": after["table_count"] >= before["table_count"],
        }
        report.update(
            {
                "status": "PASS" if all(checks.values()) else "FAIL",
                "before": before,
                "after": after,
                "checks": checks,
            }
        )
    finally:
        if previous_admin_url is None:
            os.environ.pop("DATABASE_ADMIN_URL", None)
        else:
            os.environ["DATABASE_ADMIN_URL"] = previous_admin_url
        if created:
            with admin.connect() as connection:
                connection.execute(text(f'DROP DATABASE IF EXISTS "{temporary_database}" CASCADE'))
            report["temporary_database_removed"] = True
        admin.dispose()

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_ADMIN_URL", ""))
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".artifacts" / "preflight" / "cockroach-upgrade.json",
    )
    args = parser.parse_args(argv)
    if not args.database_url.strip():
        parser.error("DATABASE_ADMIN_URL or --database-url is required")
    try:
        report = run(args.database_url, output=args.output)
    except Exception as error:
        logger.error("%s", json.dumps({"status": "FAIL", "error_type": type(error).__name__}))
        return 1
    logger.warning(
        "%s",
        json.dumps(
            {
                "status": report["status"],
                "artifact": str(args.output),
                "temporary_database_removed": report["temporary_database_removed"],
            }
        ),
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    raise SystemExit(main())
