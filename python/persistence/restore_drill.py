"""Sanitized snapshot comparison for a disposable CockroachDB restore drill."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from domain import content_hash


@dataclass(frozen=True, slots=True)
class RestoreSnapshot:
    alembic_heads: tuple[str, ...]
    table_count: int
    organization_count: int
    outbox_event_count: int
    workspace_setting_version_count: int

    @property
    def digest(self) -> str:
        return content_hash(asdict(self))


@dataclass(frozen=True, slots=True)
class RestoreVerdict:
    status: str
    source_digest: str
    restored_digest: str
    mismatches: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_restore(source: RestoreSnapshot, restored: RestoreSnapshot) -> RestoreVerdict:
    mismatches = tuple(
        field
        for field in (
            "alembic_heads",
            "table_count",
            "organization_count",
            "outbox_event_count",
            "workspace_setting_version_count",
        )
        if getattr(source, field) != getattr(restored, field)
    )
    return RestoreVerdict(
        status="PASS" if not mismatches else "FAIL",
        source_digest=source.digest,
        restored_digest=restored.digest,
        mismatches=mismatches,
    )
