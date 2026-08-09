"""Local proof runner and artifact reader for the operator workspace."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Any

from .errors import ApiProblem
from .proof_schemas import ProofWorkspaceView


class ProofWorkspaceRuntime:
    def __init__(self, root: Path) -> None:
        self.root = root
        configured = os.getenv("SIRA_PROOF_WORKSPACE_ARTIFACT", "").strip()
        self.artifact_path = (
            Path(configured).expanduser().resolve()
            if configured
            else root / ".artifacts" / "proof" / "workspace.json"
        )
        self._task: asyncio.Task[None] | None = None
        self._status = "IDLE"
        self._run_id: str | None = None
        self._safe_error_code: str | None = None

    def workspace(self) -> ProofWorkspaceView:
        try:
            payload: Any = json.loads(self.artifact_path.read_text(encoding="utf-8-sig"))
            workspace = ProofWorkspaceView.model_validate(payload)
        except FileNotFoundError as exc:
            raise ApiProblem(
                code="PROOF_RUN_NOT_FOUND",
                message="No verified proof run is available yet.",
                status_code=404,
                next_action="run_proof_demo",
                details={"next_command": "scripts\\proof.cmd demo -Assert"},
            ) from exc
        except (OSError, ValueError) as exc:
            raise ApiProblem(
                code="PROOF_ARTIFACT_INVALID",
                message="The latest proof artifact could not be verified.",
                status_code=409,
                next_action="rerun_proof_demo",
                details={"next_command": "scripts\\proof.cmd demo -Assert"},
            ) from exc
        self._run_id = workspace.run_id
        if self._status != "RUNNING":
            self._status = "COMPLETE"
            self._safe_error_code = None
        return workspace

    def runner(self) -> dict[str, str | None]:
        return {
            "status": self._status,
            "run_id": self._run_id,
            "safe_error_code": self._safe_error_code,
            "artifact_path": str(self.artifact_path.relative_to(self.root)),
            "next_command": (
                "scripts\\proof.cmd demo -Assert" if self._status == "FAILED" else None
            ),
        }

    async def start(self) -> dict[str, str | None]:
        if self._task is not None and not self._task.done():
            return self.runner()
        shell = shutil.which("powershell.exe") or shutil.which("pwsh")
        if shell is None:
            raise ApiProblem(
                code="PROOF_RUNNER_UNAVAILABLE",
                message="The local proof runner is unavailable in this API process.",
                status_code=503,
                next_action="run_proof_demo",
                details={"next_command": "scripts\\proof.cmd demo -Assert"},
            )
        self._status = "RUNNING"
        self._safe_error_code = None
        self._task = asyncio.create_task(self._execute(shell))
        return self.runner()

    async def _execute(self, shell: str) -> None:
        try:
            process = await asyncio.create_subprocess_exec(
                shell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.root / "scripts" / "proof.ps1"),
                "demo",
                "-Assert",
                "-Artifacts",
                ".artifacts/proof",
                cwd=self.root,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            return_code = await process.wait()
            if return_code != 0:
                self._status = "FAILED"
                self._safe_error_code = "PROOF_DEMO_FAILED"
                return
            workspace = self.workspace()
            self._run_id = workspace.run_id
            self._status = "COMPLETE"
        except Exception:
            self._status = "FAILED"
            self._safe_error_code = "PROOF_DEMO_FAILED"

    async def close(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
