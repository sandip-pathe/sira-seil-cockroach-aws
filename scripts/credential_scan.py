"""Fail when likely committed credentials appear in source or demo fixtures.

This supplements detect-secrets with project-specific names. Documentation and
dependency/cache output are excluded, but frozen demo fixtures are scanned because
they are shipped and may be served by development APIs.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from detect_secrets.core.scan import scan_file, scan_line
from detect_secrets.settings import default_settings

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {
    ".artifacts",
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
EXCLUDED_NAMES = {"pnpm-lock.yaml", "uv.lock", ".env", ".env.example"}
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
        r"(?i)(prava_secret_key|controlled_merchant_api_key)"
        r"\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{12,}"
    ),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]
HISTORY_ENTROPY_TYPES = {"Base64 High Entropy String", "Hex High Entropy String"}


def files_to_scan() -> list[Path]:
    result: list[Path] = []
    for directory, subdirectories, filenames in os.walk(ROOT, topdown=True):
        subdirectories[:] = sorted(name for name in subdirectories if name not in EXCLUDED_PARTS)
        for filename in sorted(filenames):
            path = Path(directory) / filename
            if filename not in EXCLUDED_NAMES and path.suffix in TEXT_SUFFIXES:
                result.append(path)
    return sorted(result)


def _generic_scanner_excluded(path: Path) -> bool:
    """Avoid entropy false positives on immutable Alembic revision identifiers."""

    return path.parts[:4] == ("services", "api", "alembic", "versions")


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
            custom_finding = any(pattern.search(removed_line) for pattern in PATTERNS)
            generic_finding = not _generic_scanner_excluded(Path(relative_path)) and any(
                detection.type not in HISTORY_ENTROPY_TYPES for detection in scan_line(removed_line)
            )
            if custom_finding or generic_finding:
                findings.append(f"git-history:{commit}:{relative_path}")
    return findings


def main(*, current_tree_only: bool = False) -> int:
    findings: list[str] = []
    scanned_files = files_to_scan()
    for path in scanned_files:
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            if any(pattern.search(line) for pattern in PATTERNS):
                findings.append(f"{path.relative_to(ROOT)}:{line_number}")
    with default_settings():
        for path in scanned_files:
            relative_path = path.relative_to(ROOT)
            if _generic_scanner_excluded(relative_path):
                continue
            for detection in scan_file(str(path)):
                findings.append(f"{relative_path}:{detection.line_number}")
    if not current_tree_only:
        findings.extend(scan_reachable_git_history())
    if findings:
        sys.stdout.write("Credential scan failed at: " + ", ".join(sorted(set(findings))) + "\n")
        return 1
    scope = "current source and demo fixtures" if current_tree_only else "source and history"
    sys.stdout.write(f"Credential scan passed for {scope}; no credentials detected.\n")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--current-tree-only",
        action="store_true",
        help="skip reachable-history scanning for a fast CI/current-tree gate",
    )
    arguments = parser.parse_args()
    raise SystemExit(main(current_tree_only=arguments.current_tree_only))
