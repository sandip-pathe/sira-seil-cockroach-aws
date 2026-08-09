from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest


def _load_release_module() -> Any:
    path = Path(__file__).parents[2] / "scripts" / "verify_release_runs.py"
    spec = importlib.util.spec_from_file_location("verify_release_runs", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify_runs = _load_release_module().verify_runs


def _write_run(
    root: Path,
    index: int,
    *,
    commit: str = "abc123",
    semantic_hash: str = "sha256:semantic",
    clean: bool = True,
) -> Path:
    run = root / f"run-{index}"
    run.mkdir()
    payloads = {
        "manifest.json": {
            "applicationCommit": commit,
            "semanticResultHash": semantic_hash,
            "workingTreeClean": clean,
        },
        "gates.json": {"G1": True, "G7": True},
        "timings.json": {
            "warmDemoSeconds": 170 + index,
            "warmBudgetSeconds": 180,
            "totalSeconds": 190 + index,
        },
        "recovery.json": {"status": "RESTORED"},
    }
    for name, payload in payloads.items():
        (run / name).write_text(json.dumps(payload), encoding="utf-8")
    return run


def test_verify_release_runs_requires_three_identical_clean_passes(tmp_path: Path) -> None:
    runs = [_write_run(tmp_path, index) for index in range(1, 4)]

    summary = verify_runs(runs)

    assert summary["status"] == "PASS"
    assert summary["consecutiveRuns"] == "3/3"
    assert summary["warmDemoSeconds"]["maximum"] == 173


def test_verify_release_runs_rejects_semantic_drift(tmp_path: Path) -> None:
    runs = [_write_run(tmp_path, index) for index in range(1, 3)]
    runs.append(_write_run(tmp_path, 3, semantic_hash="sha256:different"))

    with pytest.raises(ValueError, match="semantic result"):
        verify_runs(runs)


def test_verify_release_runs_rejects_dirty_tree(tmp_path: Path) -> None:
    runs = [_write_run(tmp_path, index) for index in range(1, 3)]
    runs.append(_write_run(tmp_path, 3, clean=False))

    with pytest.raises(ValueError, match="clean working tree"):
        verify_runs(runs)
