from __future__ import annotations

import subprocess
from collections.abc import Sequence

from integrations.ccloud_doctor import inspect_cockroach_cloud


def _runner(outputs: dict[tuple[str, ...], tuple[int, str]]):
    def run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        returncode, output = outputs[tuple(command)]
        return subprocess.CompletedProcess(command, returncode, output, "")

    return run


def test_ccloud_doctor_requires_aws_created_cluster_and_enabled_backups() -> None:
    ccloud = "ccloud"
    cluster = "sira-hackathon"
    outputs = {
        (ccloud, "version"): (0, "ccloud 0.6.12\n"),
        (ccloud, "cluster", "--help"): (
            0,
            "  backup  Manage backups\n  restore  Manage restores\n",
        ),
        (ccloud, "cluster", "info", cluster): (
            0,
            "state: CLUSTER_STATE_CREATED\ncloud: CLOUD_PROVIDER_AWS\n",
        ),
        (ccloud, "cluster", "backup", "list", cluster): (
            0,
            "BACKUP ID AS OF TIME\n12345678-1234-1234-1234-123456789abc 2026-08-13T00:00:00Z\n",
        ),
        (ccloud, "cluster", "backup", "config", "get", cluster): (
            0,
            "Backups Enabled: Yes\nRetention: 30 days\n",
        ),
        (ccloud, "cluster", "restore", "list", cluster): (0, "No restores found\n"),
    }
    report = inspect_cockroach_cloud(ccloud, cluster, runner=_runner(outputs))
    assert report.status == "READY"
    assert report.cli_version == "0.6.12"
    assert report.backup_count == 1
    assert report.backup_commands_supported
    assert cluster not in str(report.as_dict())
    assert all(item.output_sha256.startswith("sha256:") for item in report.commands)

    outputs[(ccloud, "cluster", "backup", "config", "get", cluster)] = (
        0,
        "Backups Enabled: No\n",
    )
    assert inspect_cockroach_cloud(ccloud, cluster, runner=_runner(outputs)).status == "NOT_READY"


def test_ccloud_doctor_fails_closed_on_command_errors_and_invalid_names() -> None:
    ccloud = "ccloud"
    cluster = "sira"
    outputs = {
        (ccloud, "version"): (0, "ccloud 0.6.12\n"),
        (ccloud, "cluster", "--help"): (0, "  list  List clusters\n"),
        (ccloud, "cluster", "info", cluster): (1, "not logged in\n"),
    }
    report = inspect_cockroach_cloud(ccloud, cluster, runner=_runner(outputs))
    assert report.status == "NOT_READY"
    assert not report.cluster_created
    assert report.backup_count == 0
    assert not report.backup_commands_supported

    for invalid in ("", " ", "x" * 101):
        try:
            inspect_cockroach_cloud(ccloud, invalid, runner=_runner(outputs))
        except ValueError:
            continue
        raise AssertionError("invalid cluster name accepted")
