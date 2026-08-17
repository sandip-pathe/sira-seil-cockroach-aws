"""Cross-platform local lifecycle commands for SIRA + SEIL."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / ".artifacts" / "local"
PROCESS_FILE = ARTIFACTS / "processes.json"
LOCAL_URLS = {
    "api": "http://127.0.0.1:8000/health",
    "ready": "http://127.0.0.1:8000/ready",
    "web": "http://127.0.0.1:3000/sira",
}


def _run(
    arguments: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(arguments),
        cwd=ROOT,
        env=dict(env) if env is not None else None,
        check=False,
        text=True,
        capture_output=capture,
        timeout=300,
    )


def _require_success(result: subprocess.CompletedProcess[str], label: str) -> None:
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"{label} failed" + (f": {detail}" if detail else ""))


def local_database_urls(database_name: str = "sira") -> dict[str, str]:
    return {
        "DATABASE_ADMIN_URL": (
            f"cockroachdb+psycopg://root@127.0.0.1:26257/{database_name}?sslmode=disable"
        ),
        "DATABASE_URL": (
            f"cockroachdb+asyncpg://sira_app@127.0.0.1:26257/{database_name}?ssl=disable"
        ),
        "SIRA_WORKER_DATABASE_URL": (
            f"cockroachdb+asyncpg://sira_worker_app@127.0.0.1:26257/{database_name}?ssl=disable"
        ),
        "SIRA_CATALOG_DATABASE_URL": (
            f"cockroachdb+asyncpg://sira_catalog_app@127.0.0.1:26257/{database_name}?ssl=disable"
        ),
    }


def bootstrap_database(*, database_name: str = "sira", reset: bool = False) -> None:
    if database_name not in {"sira", "sira_test"}:
        raise ValueError("local database must be sira or sira_test")
    _require_success(
        _run(["docker", "compose", "up", "-d", "--wait", "cockroach"], capture=True),
        "CockroachDB startup",
    )
    setup = [
        "SET CLUSTER SETTING feature.vector_index.enabled = true",
        f"{'DROP DATABASE IF EXISTS ' + database_name + ' CASCADE; ' if reset else ''}"
        f"CREATE DATABASE IF NOT EXISTS {database_name}",
        "CREATE USER IF NOT EXISTS sira_app",
        "CREATE USER IF NOT EXISTS sira_worker_app",
        "CREATE USER IF NOT EXISTS sira_catalog_app",
    ]
    _require_success(
        _run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "cockroach",
                "cockroach",
                "sql",
                "--insecure",
                "--host=localhost:26257",
                f"--execute={'; '.join(setup)};",
            ],
            capture=True,
        ),
        "CockroachDB initialization",
    )
    migration_env = {**os.environ, **local_database_urls(database_name)}
    _require_success(
        _run([sys.executable, "-m", "alembic", "upgrade", "head"], env=migration_env),
        "database migration",
    )
    grants = (
        f"GRANT CONNECT ON DATABASE {database_name} TO "
        "sira_app, sira_worker_app, sira_catalog_app; "
        "GRANT sira_runtime, sira_api_tenant_bootstrap TO sira_app; "
        "GRANT sira_runtime, sira_worker_directory_reader TO sira_worker_app; "
        "GRANT sira_catalog_reader TO sira_catalog_app; "
        "UPSERT INTO organizations (id, name, version) VALUES "
        "('org_demo', 'SIRA Demo Buyer', 1), "
        "('org_consultco', 'ConsultCo Demo Buyer', 1), "
        "('org_seller_a', 'Atlas Seller', 1), "
        "('org_seller_b', 'Beacon Seller', 1)"
    )
    _require_success(
        _run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "cockroach",
                "cockroach",
                "sql",
                "--insecure",
                "--host=localhost:26257",
                f"--database={database_name}",
                f"--execute={grants};",
            ],
            capture=True,
        ),
        "runtime role grants",
    )


def _command_version(command: str, *arguments: str) -> tuple[bool, str]:
    executable = shutil.which(command)
    if not executable:
        return False, "missing"
    result = _run([executable, *arguments], capture=True)
    output = (result.stdout or result.stderr or "").strip().splitlines()
    detail = output[0] if output else ("available" if result.returncode == 0 else "unavailable")
    return result.returncode == 0, detail


def _minimum_major(check: tuple[bool, str], minimum: int) -> tuple[bool, str]:
    passed, detail = check
    match = re.search(r"(?:^|\s|v)(\d+)(?:\.|$)", detail)
    return passed and match is not None and int(match.group(1)) >= minimum, detail


def doctor(profile: str) -> int:
    checks: dict[str, tuple[bool, str]] = {
        "python": (
            (3, 12) <= sys.version_info[:2] < (3, 14),
            ".".join(str(part) for part in sys.version_info[:3]),
        ),
        "docker": _command_version("docker", "--version"),
        "node": _minimum_major(_command_version("node", "--version"), 22),
        "pnpm": _minimum_major(_command_version("pnpm", "--version"), 11),
        "docker_compose": _command_version("docker", "compose", "version"),
        "compose_file": ((ROOT / "compose.yaml").exists(), "compose.yaml"),
        "environment": ((ROOT / ".env").exists(), ".env"),
    }
    if profile == "local" and checks["docker"][0]:
        checks["docker_daemon"] = _command_version(
            "docker", "info", "--format", "{{.ServerVersion}}"
        )
    for name, (passed, detail) in checks.items():
        print(f"{'PASS' if passed else 'FAIL'}  {name}: {detail}")
    return 0 if all(passed for passed, _detail in checks.values()) else 1


def _local_environment() -> dict[str, str]:
    python_paths = [
        ROOT / "python",
        ROOT / "python" / "agents",
        ROOT / "services" / "api",
        ROOT / "services" / "worker",
    ]
    existing = os.environ.get("PYTHONPATH")
    if existing:
        python_paths.append(Path(existing))
    return {
        **os.environ,
        **local_database_urls(),
        "PYTHONPATH": os.pathsep.join(str(path) for path in python_paths),
        "APP_ENV": "development",
        "DEVELOPMENT_FIXTURE_MODE": "true",
        "DEMO_RESET_ENABLED": "true",
        "GUEST_SESSION_ENABLED": "true",
        "NEXT_PUBLIC_GUEST_SESSION_ENABLED": "true",
        "NEXT_PUBLIC_WEB_DATA_MODE": "api",
        "SIRA_API_BASE_URL": "http://127.0.0.1:8000",
    }


def _spawn(name: str, arguments: Sequence[str], env: Mapping[str, str]) -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    log_path = ARTIFACTS / f"{name}.log"
    creationflags = 0
    start_new_session = os.name != "nt"
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    with log_path.open("a", encoding="utf-8") as log:
        process = subprocess.Popen(
            list(arguments),
            cwd=ROOT,
            env=dict(env),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
            start_new_session=start_new_session,
        )
    return process.pid


def _load_processes() -> dict[str, int]:
    if not PROCESS_FILE.exists():
        return {}
    try:
        value = json.loads(PROCESS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {str(name): int(pid) for name, pid in value.items()}


def _process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _probe(url: str) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:  # noqa: S310
            return 200 <= response.status < 400, f"HTTP {response.status}"
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return False, type(error).__name__


def up(profile: str) -> int:
    if profile != "local":
        raise RuntimeError("provider and hosted lifecycle use deployment tooling, not sira-dev up")
    bootstrap_database()
    processes = _load_processes()
    environment = _local_environment()
    if not _process_alive(processes.get("api", -1)):
        processes["api"] = _spawn(
            "api",
            [
                sys.executable,
                "-m",
                "uvicorn",
                "sira_api.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            environment,
        )
    pnpm = shutil.which("pnpm")
    if not pnpm:
        raise RuntimeError("pnpm is required to start the web application")
    if not _process_alive(processes.get("web", -1)):
        processes["web"] = _spawn("web", [pnpm, "dev:web"], environment)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    PROCESS_FILE.write_text(
        json.dumps(processes, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if _probe(LOCAL_URLS["api"])[0] and _probe(LOCAL_URLS["web"])[0]:
            print("SIRA + SEIL is ready: http://127.0.0.1:3000/sira")
            return 0
        time.sleep(1)
    print(f"Startup did not become healthy. Inspect logs in {ARTIFACTS}", file=sys.stderr)
    return 1


def status(_profile: str) -> int:
    processes = _load_processes()
    healthy = True
    for name in ("api", "web"):
        pid = processes.get(name)
        alive = pid is not None and _process_alive(pid)
        print(f"{'UP' if alive else 'DOWN'}  {name} process" + (f" (pid {pid})" if pid else ""))
        healthy = healthy and alive
    for name, url in LOCAL_URLS.items():
        passed, detail = _probe(url)
        print(f"{'PASS' if passed else 'FAIL'}  {name}: {detail}")
        healthy = healthy and passed
    database = _run(["docker", "compose", "ps", "--status", "running", "cockroach"], capture=True)
    database_up = database.returncode == 0 and "cockroach" in database.stdout
    print(f"{'UP' if database_up else 'DOWN'}  cockroach")
    return 0 if healthy and database_up else 1


def logs(_profile: str, *, follow: bool) -> int:
    for name in ("api", "web"):
        path = ARTIFACTS / f"{name}.log"
        print(f"--- {name} ({path})")
        if path.exists():
            print("\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-100:]))
    if follow:
        return _run(
            ["docker", "compose", "logs", "--follow", "--tail", "100", "cockroach"]
        ).returncode
    return _run(["docker", "compose", "logs", "--tail", "100", "cockroach"]).returncode


def down(_profile: str) -> int:
    for _name, pid in _load_processes().items():
        if not _process_alive(pid):
            continue
        if os.name == "nt":
            _run(["taskkill", "/PID", str(pid), "/T"], capture=True)
        else:
            os.killpg(pid, signal.SIGTERM)  # type: ignore[attr-defined]
    PROCESS_FILE.unlink(missing_ok=True)
    return _run(["docker", "compose", "stop", "cockroach"]).returncode


def check(_profile: str) -> int:
    commands = [
        [sys.executable, "-m", "ruff", "check", "python", "services", "tests", "scripts"],
        [
            sys.executable,
            "-m",
            "ruff",
            "format",
            "--check",
            "python",
            "services",
            "tests",
            "scripts",
        ],
        [sys.executable, "-m", "mypy", "python", "services"],
        [sys.executable, "-m", "pytest", "-m", "not cockroach and not provider"],
        [sys.executable, "scripts/generate_openapi.py", "--check"],
        ["pnpm", "check:web"],
        [sys.executable, "scripts/credential_scan.py", "--current-tree-only"],
    ]
    for command in commands:
        result = _run(command)
        if result.returncode != 0:
            return result.returncode
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="sira-dev")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("doctor", "up", "status", "check", "down"):
        command = commands.add_parser(name)
        command.add_argument("--profile", choices=("local", "provider", "hosted"), default="local")
    logs_command = commands.add_parser("logs")
    logs_command.add_argument("--profile", choices=("local", "provider", "hosted"), default="local")
    logs_command.add_argument("--follow", action="store_true")
    return root


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        if arguments.command == "doctor":
            return doctor(arguments.profile)
        if arguments.command == "up":
            return up(arguments.profile)
        if arguments.command == "status":
            return status(arguments.profile)
        if arguments.command == "logs":
            return logs(arguments.profile, follow=arguments.follow)
        if arguments.command == "check":
            return check(arguments.profile)
        return down(arguments.profile)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"sira-dev: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
