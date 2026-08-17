from __future__ import annotations

import json
from pathlib import Path

import pytest

from sira_cli import dev, scenario


def test_local_database_urls_are_loopback_and_role_separated() -> None:
    urls = dev.local_database_urls("sira_test")

    assert set(urls) == {
        "DATABASE_ADMIN_URL",
        "DATABASE_URL",
        "SIRA_WORKER_DATABASE_URL",
        "SIRA_CATALOG_DATABASE_URL",
    }
    assert all("127.0.0.1:26257/sira_test" in value for value in urls.values())
    assert "root@" in urls["DATABASE_ADMIN_URL"]
    assert "sira_app@" in urls["DATABASE_URL"]
    assert "sira_worker_app@" in urls["SIRA_WORKER_DATABASE_URL"]
    assert "sira_catalog_app@" in urls["SIRA_CATALOG_DATABASE_URL"]


def test_bootstrap_rejects_an_unscoped_database_name() -> None:
    with pytest.raises(ValueError, match="sira or sira_test"):
        dev.bootstrap_database(database_name="production", reset=True)


def test_version_and_process_checks_fail_closed() -> None:
    assert dev._minimum_major((True, "v22.1.0"), 22) == (True, "v22.1.0")
    assert dev._minimum_major((True, "10.9.0"), 11) == (False, "10.9.0")
    assert dev._process_alive(-1) is False


def test_command_parsers_match_documented_surface() -> None:
    assert dev.parser().parse_args(["doctor", "--profile", "local"]).command == "doctor"
    assert dev.parser().parse_args(["logs", "--follow"]).follow is True
    assert (
        scenario.parser().parse_args(["run", "--scenario", "evidence-race"]).scenario
        == "evidence-race"
    )
    assert scenario.parser().parse_args(["verify", "--latest"]).latest is True


def test_local_environment_forces_the_deterministic_isolated_kernel() -> None:
    environment = dev._local_environment("127.0.0.1")

    assert environment["AGENT_RUNTIME_PROVIDER"] == "openai"
    assert environment["COGNITIVE_KERNEL_ENABLED"] == "true"
    assert environment["PRINCIPAL_ISOLATION_ENABLED"] == "true"


def test_verify_requires_a_passing_latest_record(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result_file = tmp_path / "latest.json"
    monkeypatch.setattr(scenario, "RESULT_FILE", result_file)
    assert scenario.verify(latest=True) == 1

    result_file.write_text(
        json.dumps(
            {
                "scenario": "evidence-race",
                "passed": True,
                "completed_at": "2026-08-18T00:00:00+00:00",
                "tests": ["race", "replacement"],
            }
        ),
        encoding="utf-8",
    )
    assert scenario.verify(latest=True) == 0
