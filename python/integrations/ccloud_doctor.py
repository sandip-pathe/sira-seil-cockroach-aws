"""Credential-safe evidence collection through the CockroachDB ccloud CLI."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any

_BACKUP_ID = re.compile(r"(?im)^([0-9a-f]{8}-[0-9a-f-]{27,})\s+")


@dataclass(frozen=True, slots=True)
class CcloudCommandEvidence:
    name: str
    success: bool
    output_sha256: str


@dataclass(frozen=True, slots=True)
class CcloudDoctorReport:
    status: str
    cluster_name_sha256: str
    cli_version: str | None
    cluster_created: bool
    aws_cluster: bool
    backup_commands_supported: bool
    backups_enabled: bool
    backup_count: int
    restore_history_accessible: bool
    commands: tuple[CcloudCommandEvidence, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def inspect_cockroach_cloud(
    ccloud: str,
    cluster_name: str,
    *,
    runner: Runner | None = None,
) -> CcloudDoctorReport:
    if not cluster_name.strip() or len(cluster_name) > 100:
        raise ValueError("cluster name must contain 1-100 non-whitespace characters")
    invoke = runner or _run
    required_calls = (
        ("version", (ccloud, "version")),
        ("cluster_help", (ccloud, "cluster", "--help")),
        ("cluster_info", (ccloud, "cluster", "info", cluster_name)),
    )
    outputs: dict[str, str] = {}
    evidence: list[CcloudCommandEvidence] = []
    for name, command in required_calls:
        completed = invoke(command)
        output = (completed.stdout or "") + (completed.stderr or "")
        outputs[name] = output
        evidence.append(
            CcloudCommandEvidence(
                name=name,
                success=completed.returncode == 0,
                output_sha256="sha256:" + sha256(output.encode("utf-8")).hexdigest(),
            )
        )

    cluster_help = outputs["cluster_help"].casefold()
    backup_commands_supported = bool(
        re.search(r"(?m)^\s*backup\s+", cluster_help)
        and re.search(r"(?m)^\s*restore\s+", cluster_help)
    )
    if backup_commands_supported:
        backup_calls = (
            ("backup_list", (ccloud, "cluster", "backup", "list", cluster_name)),
            (
                "backup_config",
                (ccloud, "cluster", "backup", "config", "get", cluster_name),
            ),
            ("restore_list", (ccloud, "cluster", "restore", "list", cluster_name)),
        )
        for name, backup_command in backup_calls:
            completed = invoke(backup_command)
            output = (completed.stdout or "") + (completed.stderr or "")
            outputs[name] = output
            evidence.append(
                CcloudCommandEvidence(
                    name=name,
                    success=completed.returncode == 0,
                    output_sha256="sha256:" + sha256(output.encode("utf-8")).hexdigest(),
                )
            )

    info = outputs["cluster_info"].casefold()
    backup_config = outputs.get("backup_config", "").casefold()
    backup_count = len(_BACKUP_ID.findall(outputs.get("backup_list", "")))
    cluster_created = "cluster_state_created" in info
    aws_cluster = "cloud_provider_aws" in info
    backups_enabled = bool(re.search(r"backups enabled:\s*(yes|true)", backup_config))
    restore_history_accessible = bool(
        backup_commands_supported
        and next(
            (item.success for item in evidence if item.name == "restore_list"),
            False,
        )
    )
    required_commands = all(item.success for item in evidence)
    status = (
        "READY"
        if required_commands
        and cluster_created
        and aws_cluster
        and backup_commands_supported
        and backups_enabled
        and backup_count > 0
        and restore_history_accessible
        else "NOT_READY"
    )
    version_match = re.search(r"(?im)^ccloud\s+([^\s]+)", outputs["version"])
    return CcloudDoctorReport(
        status=status,
        cluster_name_sha256="sha256:" + sha256(cluster_name.strip().encode("utf-8")).hexdigest(),
        cli_version=version_match.group(1) if version_match else None,
        cluster_created=cluster_created,
        aws_cluster=aws_cluster,
        backup_commands_supported=backup_commands_supported,
        backups_enabled=backups_enabled,
        backup_count=backup_count,
        restore_history_accessible=restore_history_accessible,
        commands=tuple(evidence),
    )


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - exact argv, no shell
        list(command),
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
