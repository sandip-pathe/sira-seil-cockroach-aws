"""Write a sanitized grant, FORCE RLS, and immutable-table audit artifact."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
load_dotenv(ROOT / ".env", override=False)

from persistence.security_audit import TableSecurity, assess_security  # noqa: E402

IMMUTABLE_TABLES = frozenset(
    {
        "marketplace_buyer_projections",
        "marketplace_seller_projections",
        "marketplace_seller_responses",
        "qualification_attempt_checkpoints",
        "qualification_attempt_dependencies",
        "qualification_catalog_projection_versions",
        "qualification_company_context_embeddings",
        "qualification_company_context_versions",
        "qualification_consumer_receipts",
        "qualification_decision_dependencies",
        "qualification_evidence_versions",
        "qualification_mission_bundles",
        "qualification_product_bundle_members",
        "qualification_product_embeddings",
        "qualification_product_twin_versions",
        "qualification_workspace_setting_versions",
    }
)

_TABLES = text(
    """
    SELECT relation.relname AS table_name,
           relation.relrowsecurity AS row_security,
           relation.relforcerowsecurity AS force_row_security,
           pg_get_userbyid(relation.relowner) AS owner
    FROM pg_catalog.pg_class AS relation
    JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = relation.relnamespace
    WHERE namespace.nspname = 'public'
      AND relation.relkind = 'r'
      AND EXISTS (
          SELECT 1 FROM information_schema.columns AS columns
          WHERE columns.table_schema = namespace.nspname
            AND columns.table_name = relation.relname
            AND columns.column_name = 'organization_id'
      )
    ORDER BY relation.relname
    """
)
_POLICIES = text(
    """
    SELECT tablename, count(*) AS policy_count
    FROM pg_catalog.pg_policies
    WHERE schemaname = 'public'
    GROUP BY tablename
    """
)
_GRANTS = text(
    """
    SELECT table_name, privilege_type
    FROM information_schema.role_table_grants
    WHERE table_schema = 'public' AND grantee = 'sira_runtime'
    """
)


def _admin_url(raw: str) -> str:
    if not raw.strip():
        raise ValueError("DATABASE_ADMIN_URL is required")
    parsed = make_url(raw.strip())
    query = dict(parsed.query)
    query.setdefault("connect_timeout", "10")
    return parsed.set(drivername="cockroachdb+psycopg", query=query).render_as_string(
        hide_password=False
    )


def collect(database_url: str) -> tuple[TableSecurity, ...]:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            rows = connection.execute(_TABLES).mappings().all()
            policy_counts = {
                str(row["tablename"]): int(row["policy_count"])
                for row in connection.execute(_POLICIES).mappings()
            }
            privileges: defaultdict[str, set[str]] = defaultdict(set)
            for row in connection.execute(_GRANTS).mappings():
                privileges[str(row["table_name"])].add(str(row["privilege_type"]).upper())
        return tuple(
            TableSecurity(
                table=str(row["table_name"]),
                forced_rls=bool(row["row_security"] and row["force_row_security"]),
                policies=policy_counts.get(str(row["table_name"]), 0),
                runtime_privileges=frozenset(privileges[str(row["table_name"])]),
                owner=str(row["owner"]),
            )
            for row in rows
        )
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".artifacts" / "preflight" / "cockroach-security.json",
    )
    parser.add_argument(
        "--database-url",
        help="Administrative CockroachDB URL; defaults to DATABASE_ADMIN_URL.",
    )
    args = parser.parse_args(argv)
    report = assess_security(
        collect(_admin_url(args.database_url or os.getenv("DATABASE_ADMIN_URL", ""))),
        immutable_tables=IMMUTABLE_TABLES,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    sys.stdout.write(
        json.dumps(
            {
                "status": report.status,
                "artifact": str(args.output),
                "tenant_table_count": report.tenant_table_count,
                "violation_count": len(report.violations),
            },
            sort_keys=True,
        )
        + "\n"
    )
    return 0 if report.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
