"""Fail when likely committed credentials appear in source or demo fixtures.

This supplements detect-secrets with project-specific names. Immutable product
documents and dependency/cache output are excluded, but frozen demo fixtures are
intentionally scanned because they are shipped and may be served by development APIs.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from detect_secrets.core.scan import scan_line
from detect_secrets.settings import default_settings

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {
    ".git",
    ".gstack",
    ".hypothesis",
    ".mypy_cache",
    ".venv",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "docs",
}
EXCLUDED_NAMES = {"PRD.md", "pnpm-lock.yaml", "uv.lock", ".env", ".env.example"}
TEXT_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".md",
    ".ndjson",
    ".log",
    ".ps1",
    ".txt",
}
PATTERNS = [
    re.compile(
        r"(?i)(prava_secret_key|senso_[a-z_]*api_key|controlled_merchant_api_key)"
        r"\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{12,}"
    ),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]

DETECT_SECRETS_EXCLUDES = (
    r"(^|[\\/])(?:\.git|\.gstack|\.hypothesis|\.mypy_cache|\.venv|\.next|"
    r"\.pytest_cache|\.ruff_cache|node_modules|docs)(?:[\\/]|$)"
    r"|(^|[\\/])services[\\/]api[\\/]alembic[\\/]versions(?:[\\/]|$)"
    r"|(^|[\\/])(?:\.env(?:\.[^\\/]*)?|PRD\.md|pnpm-lock\.yaml|uv\.lock)$"
    r"|\.tsbuildinfo$"
)


def files_to_scan() -> list[Path]:
    result: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.name in EXCLUDED_NAMES:
            continue
        if any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix in TEXT_SUFFIXES:
            result.append(path)
    return result


def _excluded_history_path(relative_path: str) -> bool:
    path = Path(relative_path.replace("\\", "/"))
    if path.name in EXCLUDED_NAMES:
        return True
    if any(part in EXCLUDED_PARTS for part in path.parts):
        return True
    return path.suffix not in TEXT_SUFFIXES


def scan_reachable_git_history() -> list[str]:
    """Scan lines removed from reachable history without printing their contents.

    The current tree is scanned separately. Any secret that is no longer in the
    current tree must occur on a removed diff line in a later reachable commit.
    """

    git_executable = shutil.which("git")
    if git_executable is None:
        return ["git-history:git-unavailable"]
    history = subprocess.run(  # noqa: S603
        [
            git_executable,
            "log",
            "--all",
            "--format=commit:%H",
            "--no-color",
            "--no-renames",
            "--unified=0",
            "--patch",
            "--",
            ".",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=60,
    )
    if history.returncode != 0:
        return ["git-history:unreadable"]

    findings: list[str] = []
    commit = "unknown"
    relative_path = "unknown"
    with default_settings():
        for line in history.stdout.splitlines():
            if line.startswith("commit:"):
                commit = line.removeprefix("commit:")[:12]
                continue
            if line.startswith("--- "):
                old_path = line.removeprefix("--- ").strip()
                relative_path = old_path.removeprefix("a/")
                continue
            if (
                not line.startswith("-")
                or line.startswith("---")
                or relative_path == "/dev/null"
                or _excluded_history_path(relative_path)
            ):
                continue
            removed_line = line[1:]
            if any(pattern.search(removed_line) for pattern in PATTERNS) or any(
                scan_line(removed_line)
            ):
                findings.append(f"git-history:{commit}:{relative_path}")
    return findings


def main() -> int:
    findings: list[str] = []
    for path in files_to_scan():
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            if any(pattern.search(line) for pattern in PATTERNS):
                findings.append(f"{path.relative_to(ROOT)}:{line_number}")

    scanner = shutil.which("detect-secrets")
    if scanner is None:
        local_scanner = ROOT / ".venv" / "Scripts" / "detect-secrets.exe"
        if local_scanner.is_file():
            scanner = str(local_scanner)
    if scanner is None:
        sys.stdout.write(
            "detect-secrets is unavailable; run the frozen development dependency setup.\n"
        )
        return 1

    # Scanner JSON is kept in memory only and findings report locations, never values.
    completed = subprocess.run(  # noqa: S603
        [
            scanner,
            "scan",
            "--all-files",
            "--exclude-files",
            DETECT_SECRETS_EXCLUDES,
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if completed.returncode != 0:
        sys.stdout.write("detect-secrets could not complete safely.\n")
        return 1
    try:
        standard_results = json.loads(completed.stdout).get("results", {})
    except (json.JSONDecodeError, AttributeError):
        sys.stdout.write("detect-secrets returned an unreadable report.\n")
        return 1
    for relative_path, detections in standard_results.items():
        for detection in detections:
            line_number = int(detection.get("line_number", 0))
            findings.append(f"{relative_path}:{line_number}")
    findings.extend(scan_reachable_git_history())
    if findings:
        sys.stdout.write("Credential scan failed at: " + ", ".join(sorted(set(findings))) + "\n")
        return 1
    sys.stdout.write(
        "Credential scan passed; source and demo fixtures contain no detected credentials.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
