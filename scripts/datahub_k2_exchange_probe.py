"""Run the K2 exchange-bound DataHub proof and write a redacted artifact."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from proof.exchange_demo import run_exchange_proof


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".artifacts/k2/exchange-proof.json"))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    try:
        result = asyncio.run(run_exchange_proof())
    except Exception as exc:
        result = {"status": "NO-GO", "errorType": type(exc).__name__, "error": str(exc)}
    rendered = json.dumps(result, indent=2, sort_keys=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered + "\n", encoding="utf-8")
    if not args.quiet:
        print(rendered)  # noqa: T201 - operator-facing CLI
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
