"""Evaluate CockroachDB grants, forced RLS, and immutable-version boundaries."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any


@dataclass(frozen=True, slots=True)
class TableSecurity:
    table: str
    forced_rls: bool
    policies: int
    runtime_privileges: frozenset[str]
    owner: str


@dataclass(frozen=True, slots=True)
class SecurityAuditReport:
    status: str
    tenant_table_count: int
    immutable_table_count: int
    schema_sha256: str
    violations: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_security(
    tables: tuple[TableSecurity, ...],
    *,
    immutable_tables: frozenset[str],
    runtime_role: str = "sira_runtime",
) -> SecurityAuditReport:
    by_name = {table.table: table for table in tables}
    violations: list[str] = []
    for table in tables:
        if not table.forced_rls:
            violations.append(f"{table.table}:forced_rls_missing")
        if table.policies < 1:
            violations.append(f"{table.table}:policy_missing")
        if table.owner == runtime_role:
            violations.append(f"{table.table}:runtime_role_is_owner")
    for table_name in sorted(immutable_tables):
        immutable = by_name.get(table_name)
        if immutable is None:
            violations.append(f"{table_name}:immutable_table_missing")
            continue
        forbidden = immutable.runtime_privileges & {"UPDATE", "DELETE", "TRUNCATE"}
        if forbidden:
            violations.append(f"{table_name}:immutable_write_granted:{','.join(sorted(forbidden))}")
        if not {"SELECT", "INSERT"} <= immutable.runtime_privileges:
            violations.append(f"{table_name}:immutable_required_grants_missing")
    fingerprint = "\n".join(
        f"{table.table}|{int(table.forced_rls)}|{table.policies}|"
        f"{','.join(sorted(table.runtime_privileges))}|{table.owner}"
        for table in sorted(tables, key=lambda item: item.table)
    )
    return SecurityAuditReport(
        status="PASS" if not violations else "FAIL",
        tenant_table_count=len(tables),
        immutable_table_count=len(immutable_tables),
        schema_sha256="sha256:" + sha256(fingerprint.encode("utf-8")).hexdigest(),
        violations=tuple(violations),
    )
