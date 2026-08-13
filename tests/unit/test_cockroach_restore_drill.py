from persistence.restore_drill import RestoreSnapshot, assess_restore


def _snapshot(**overrides: object) -> RestoreSnapshot:
    values = {
        "alembic_heads": ("cdb0010",),
        "table_count": 90,
        "organization_count": 4,
        "outbox_event_count": 12,
        "workspace_setting_version_count": 2,
        **overrides,
    }
    return RestoreSnapshot(**values)  # type: ignore[arg-type]


def test_restore_verdict_passes_only_for_matching_bounded_snapshot() -> None:
    source = _snapshot()
    verdict = assess_restore(source, _snapshot())

    assert verdict.status == "PASS"
    assert verdict.source_digest == verdict.restored_digest
    assert verdict.mismatches == ()


def test_restore_verdict_names_mismatched_proof_without_rows() -> None:
    verdict = assess_restore(_snapshot(), _snapshot(outbox_event_count=11))

    assert verdict.status == "FAIL"
    assert verdict.source_digest != verdict.restored_digest
    assert verdict.mismatches == ("outbox_event_count",)
