"""Run the live K3 verified effect, receipt writeback, and rollback proof."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from proof.deployment_demo import run_deployment_proof


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".artifacts/k3/deployment-proof.json"))
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--simulate-writeback-failure", action="store_true")
    args = parser.parse_args()
    try:
        result = asyncio.run(
            run_deployment_proof(simulate_writeback_failure=args.simulate_writeback_failure)
        )
    except Exception as exc:
        result = {"status": "NO-GO", "errorType": type(exc).__name__, "error": str(exc)}
    rendered = json.dumps(result, indent=2, sort_keys=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered + "\n", encoding="utf-8")
    if not args.quiet:
        print(rendered)  # noqa: T201
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
