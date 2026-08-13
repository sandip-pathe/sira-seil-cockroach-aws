from persistence.security_audit import TableSecurity, assess_security


def _table(
    name: str,
    *,
    privileges: frozenset[str] = frozenset({"SELECT", "INSERT"}),
    forced_rls: bool = True,
    policies: int = 1,
    owner: str = "root",
) -> TableSecurity:
    return TableSecurity(name, forced_rls, policies, privileges, owner)


def test_security_audit_accepts_forced_rls_and_insert_only_versions() -> None:
    report = assess_security(
        (
            _table("immutable_versions"),
            _table("mutable_heads", privileges=frozenset({"SELECT", "INSERT", "UPDATE"})),
        ),
        immutable_tables=frozenset({"immutable_versions"}),
    )
    assert report.status == "PASS"
    assert report.tenant_table_count == 2
    assert report.schema_sha256.startswith("sha256:")


def test_security_audit_reports_each_privilege_and_rls_boundary_failure() -> None:
    report = assess_security(
        (
            _table(
                "immutable_versions",
                privileges=frozenset({"SELECT", "INSERT", "UPDATE", "DELETE"}),
                forced_rls=False,
                policies=0,
                owner="sira_runtime",
            ),
        ),
        immutable_tables=frozenset({"immutable_versions", "missing_versions"}),
    )
    assert report.status == "FAIL"
    assert "immutable_versions:forced_rls_missing" in report.violations
    assert "immutable_versions:policy_missing" in report.violations
    assert "immutable_versions:runtime_role_is_owner" in report.violations
    assert "immutable_versions:immutable_write_granted:DELETE,UPDATE" in report.violations
    assert "missing_versions:immutable_table_missing" in report.violations
