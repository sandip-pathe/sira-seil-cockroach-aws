"""Back up CockroachDB, verify a disposable restore, and emit sanitized evidence."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import secrets
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
load_dotenv(ROOT / ".env", override=False)

from domain import content_hash  # noqa: E402
from persistence.restore_drill import RestoreSnapshot, assess_restore  # noqa: E402

logger = logging.getLogger(__name__)

_SAFE_DATABASE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_SYSTEM_DATABASES = frozenset({"defaultdb", "postgres", "system"})


def _sync_url(raw: str, database: str | None = None) -> URL:
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


def _snapshot(url: URL) -> RestoreSnapshot:
    engine = create_engine(url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            count_statements = {
                "organizations": text("SELECT count(*) FROM organizations"),
                "outbox_events": text("SELECT count(*) FROM outbox_events"),
                "qualification_workspace_setting_versions": text(
                    "SELECT count(*) FROM qualification_workspace_setting_versions"
                ),
            }

            def count(table: str) -> int:
                exists = connection.scalar(
                    text(
                        "SELECT count(*) FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_name = :table"
                    ),
                    {"table": table},
                )
                return int(connection.scalar(count_statements[table]) or 0) if exists else 0

            heads = tuple(
                sorted(
                    str(value)
                    for value in connection.scalars(text("SELECT version_num FROM alembic_version"))
                )
            )
            table_count = int(
                connection.scalar(
                    text(
                        "SELECT count(*) FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
                    )
                )
                or 0
            )
            return RestoreSnapshot(
                alembic_heads=heads,
                table_count=table_count,
                organization_count=count("organizations"),
                outbox_event_count=count("outbox_events"),
                workspace_setting_version_count=count("qualification_workspace_setting_versions"),
            )
    finally:
        engine.dispose()


def run(database_url: str, *, output: Path) -> dict[str, object]:
    source_url = _sync_url(database_url)
    source_database = source_url.database or ""
    if not _SAFE_DATABASE.fullmatch(source_database) or source_database in _SYSTEM_DATABASES:
        raise ValueError("Refusing restore drill for a missing, system, or unsafe database name")
    suffix = secrets.token_hex(6)
    restored_database = f"sira_restore_drill_{suffix}"
    destination = f"nodelocal://1/sira_restore_drill_{suffix}"
    source = _snapshot(source_url)
    admin = create_engine(source_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    restored_created = False
    try:
        with admin.connect() as connection:
            exists = connection.scalar(
                text("SELECT count(*) FROM [SHOW DATABASES] WHERE database_name = :name"),
                {"name": restored_database},
            )
            if exists:
                raise RuntimeError("Generated restore target already exists")
            connection.execute(
                text(f'BACKUP DATABASE "{source_database}" INTO :destination'),
                {"destination": destination},
            )
            connection.execute(
                text(
                    f'RESTORE DATABASE "{source_database}" FROM LATEST IN :destination '
                    f"WITH new_db_name = {restored_database}"
                ),
                {"destination": destination},
            )
            restored_created = True
        restored = _snapshot(_sync_url(database_url, restored_database))
        verdict = assess_restore(source, restored)
        report: dict[str, object] = {
            **verdict.as_dict(),
            "source_database_hash": content_hash(source_database),
            "backup_destination_hash": content_hash(destination),
            "temporary_database_removed": False,
        }
    finally:
        if restored_created:
            with admin.connect() as connection:
                connection.execute(text(f"DROP DATABASE IF EXISTS {restored_database} CASCADE"))
        admin.dispose()
    report["temporary_database_removed"] = restored_created
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_ADMIN_URL", ""))
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".artifacts" / "preflight" / "cockroach-restore.json",
    )
    args = parser.parse_args(argv)
    if not args.database_url.strip():
        parser.error("DATABASE_ADMIN_URL or --database-url is required")
    try:
        report = run(args.database_url, output=args.output)
    except Exception as error:
        logger.error(
            "%s",
            json.dumps({"status": "FAIL", "error_type": type(error).__name__}),
        )
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
