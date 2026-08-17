"""Deterministic local scenario runner backed by real CockroachDB tests."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from typing import Any

from .dev import ROOT, bootstrap_database, local_database_urls

RESULT_DIR = ROOT / ".artifacts" / "scenarios" / "evidence-race"
RESULT_FILE = RESULT_DIR / "latest.json"
EVIDENCE_RACE_TESTS = (
    "tests/cockroach_integration/test_qualification_kernel.py::"
    "test_v2_activation_rejects_v1_finalization_and_creates_one_replacement",
    "tests/cockroach_integration/test_qualification_kernel.py::"
    "test_worker_replaces_stale_attempt_and_completes_against_v2",
)


def _scenario_environment() -> dict[str, str]:
    urls = local_database_urls("sira_test")
    return {
        **os.environ,
        "SIRA_TEST_DATABASE_ADMIN_URL": urls["DATABASE_ADMIN_URL"],
        "SIRA_TEST_DATABASE_URL": urls["DATABASE_URL"],
        "SIRA_TEST_WORKER_DATABASE_URL": urls["SIRA_WORKER_DATABASE_URL"],
        "SIRA_TEST_CATALOG_DATABASE_URL": urls["SIRA_CATALOG_DATABASE_URL"],
    }


def reset(scenario: str) -> int:
    if scenario != "evidence-race":
        raise ValueError("unsupported scenario")
    bootstrap_database(database_name="sira_test", reset=True)
    RESULT_FILE.unlink(missing_ok=True)
    print("Reset isolated CockroachDB scenario database: sira_test")
    return 0


def run(scenario: str) -> int:
    if scenario != "evidence-race":
        raise ValueError("unsupported scenario")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *EVIDENCE_RACE_TESTS],
        cwd=ROOT,
        env=_scenario_environment(),
        check=False,
        text=True,
        capture_output=True,
        timeout=600,
    )
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {
        "schema_version": "1.0.0",
        "scenario": scenario,
        "completed_at": datetime.now(UTC).isoformat(),
        "passed": result.returncode == 0,
        "tests": list(EVIDENCE_RACE_TESTS),
        "summary": (result.stdout + result.stderr).strip().splitlines()[-8:],
    }
    RESULT_FILE.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("\n".join(record["summary"]))
    return result.returncode


def verify(*, latest: bool) -> int:
    if not latest:
        raise ValueError("verification requires --latest")
    if not RESULT_FILE.exists():
        print("No evidence-race result exists. Run the scenario first.", file=sys.stderr)
        return 1
    record = json.loads(RESULT_FILE.read_text(encoding="utf-8"))
    if record.get("scenario") != "evidence-race" or record.get("passed") is not True:
        print("Latest evidence-race result did not pass.", file=sys.stderr)
        return 1
    print(f"PASS evidence-race ({record['completed_at']})")
    for test in record["tests"]:
        print(f"  {test}")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="sira-scenario")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("reset", "run"):
        command = commands.add_parser(name)
        command.add_argument("--scenario", choices=("evidence-race",), required=True)
    verify_command = commands.add_parser("verify")
    verify_command.add_argument("--latest", action="store_true")
    return root


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        if arguments.command == "reset":
            return reset(arguments.scenario)
        if arguments.command == "run":
            return run(arguments.scenario)
        return verify(latest=arguments.latest)
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"sira-scenario: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
