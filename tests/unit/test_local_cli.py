from __future__ import annotations

import pytest

from sira_cli import dev


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


def test_windows_listener_discovery_is_bounded_and_parses_only_listeners(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(dev.os, "name", "nt")
    monkeypatch.setattr(
        dev,
        "_run",
        lambda *_args, **_kwargs: dev.subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=(
                "  TCP    127.0.0.1:8000    0.0.0.0:0    LISTENING    4242\n"
                "  TCP    127.0.0.1:3000    127.0.0.1:5000    ESTABLISHED    9999\n"
            ),
            stderr="",
        ),
    )
    monkeypatch.setattr(dev, "_process_alive", lambda pid: pid == 4242)

    assert dev._windows_listener_pid(8000) == 4242
    assert dev._windows_listener_pid(3000) is None


def test_windows_process_check_uses_exact_tasklist_pid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dev.os, "name", "nt")
    monkeypatch.setattr(
        dev,
        "_run",
        lambda *_args, **_kwargs: dev.subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='"python.exe","4242","Console","1","1,000 K"\n',
            stderr="",
        ),
    )

    assert dev._process_alive(4242) is True
    assert dev._process_alive(42) is False


def test_command_parsers_match_documented_surface() -> None:
    assert dev.parser().parse_args(["doctor", "--profile", "local"]).command == "doctor"
    assert dev.parser().parse_args(["logs", "--follow"]).follow is True


def test_local_environment_enables_isolated_development_mode() -> None:
    environment = dev._local_environment("127.0.0.1")

    assert environment["APP_ENV"] == "development"
    assert environment["COGNITIVE_KERNEL_ENABLED"] == "true"
    assert environment["PRINCIPAL_ISOLATION_ENABLED"] == "true"
