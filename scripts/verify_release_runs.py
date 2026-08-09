"""Verify three clean, semantically identical proof releases and assemble submission."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"artifact is not an object: {path}")
    return payload


def verify_runs(run_paths: list[Path]) -> dict[str, Any]:
    if len(run_paths) != 3:
        raise ValueError("exactly three release runs are required")
    records: list[dict[str, Any]] = []
    for index, path in enumerate(run_paths, start=1):
        manifest = _load(path / "manifest.json")
        gates = _load(path / "gates.json")
        timings = _load(path / "timings.json")
        recovery = _load(path / "recovery.json")
        if not manifest.get("workingTreeClean"):
            raise ValueError(f"run {index} was not produced from a clean working tree")
        if not gates or not all(value is True for value in gates.values()):
            raise ValueError(f"run {index} contains a failed release gate")
        if timings["warmDemoSeconds"] >= timings["warmBudgetSeconds"]:
            raise ValueError(f"run {index} exceeded the warm demo budget")
        if recovery.get("status") != "RESTORED":
            raise ValueError(f"run {index} did not restore proof state")
        records.append(
            {
                "run": index,
                "path": str(path.resolve()),
                "applicationCommit": manifest["applicationCommit"],
                "semanticResultHash": manifest["semanticResultHash"],
                "warmDemoSeconds": timings["warmDemoSeconds"],
                "totalSeconds": timings["totalSeconds"],
            }
        )
    commits = {record["applicationCommit"] for record in records}
    semantic_hashes = {record["semanticResultHash"] for record in records}
    if len(commits) != 1:
        raise ValueError("release runs do not share one application commit")
    if len(semantic_hashes) != 1:
        raise ValueError("release runs do not share one semantic result")
    warm_seconds = [float(record["warmDemoSeconds"]) for record in records]
    return {
        "schemaVersion": "ProofReleaseSummary/v0",
        "status": "PASS",
        "consecutiveRuns": "3/3",
        "applicationCommit": records[0]["applicationCommit"],
        "semanticResultHash": records[0]["semanticResultHash"],
        "warmDemoSeconds": {
            "runs": warm_seconds,
            "minimum": min(warm_seconds),
            "maximum": max(warm_seconds),
            "average": round(sum(warm_seconds) / len(warm_seconds), 3),
            "budget": 180,
        },
        "runs": records,
    }


def assemble_submission(run_paths: list[Path], output: Path) -> dict[str, Any]:
    summary = verify_runs(run_paths)
    output.mkdir(parents=True, exist_ok=True)
    final_run = run_paths[-1]
    for name in (
        "summary.md",
        "manifest.json",
        "timeline.jsonl",
        "gates.json",
        "receipt-core.json",
        "recovery.json",
        "timings.json",
        "workspace.json",
    ):
        shutil.copy2(final_run / name, output / name)
    evidence = output / "evidence"
    if evidence.exists():
        shutil.rmtree(evidence)
    shutil.copytree(final_run / "evidence", evidence)
    source_screenshots = final_run / "screenshots"
    if source_screenshots.exists():
        target_screenshots = output / "screenshots"
        if target_screenshots.exists():
            shutil.rmtree(target_screenshots)
        shutil.copytree(source_screenshots, target_screenshots)
    (output / "release-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, nargs=3, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = assemble_submission(args.runs, args.output)
    print(json.dumps(summary, sort_keys=True))  # noqa: T201 - bounded release record
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
