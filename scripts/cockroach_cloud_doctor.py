"""Write sanitized ccloud cluster/backup evidence without connection material."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from integrations.ccloud_doctor import inspect_cockroach_cloud  # noqa: E402


def _default_ccloud() -> str:
    discovered = shutil.which("ccloud")
    if discovered:
        return discovered
    if os.name == "nt":
        candidate = Path(os.environ.get("APPDATA", "")) / "ccloud" / "ccloud.exe"
        if candidate.is_file():
            return str(candidate)
    return "ccloud"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cluster", required=True)
    parser.add_argument("--ccloud", default=_default_ccloud())
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".artifacts" / "preflight" / "cockroach-cloud.json",
    )
    args = parser.parse_args(argv)
    try:
        report = inspect_cockroach_cloud(args.ccloud, args.cluster)
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        sys.stderr.write(f"ccloud doctor unavailable: {type(exc).__name__}\n")
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    sys.stdout.write(
        json.dumps(
            {
                "status": report.status,
                "artifact": str(args.output),
                "backup_count": report.backup_count,
            },
            sort_keys=True,
        )
        + "\n"
    )
    return 0 if report.status == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
