"""Measure local API latency without storing credentials or response bodies."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from statistics import fmean
from time import perf_counter
from typing import Any

import httpx


def percentile(values: Sequence[float], quantile: float) -> float:
    """Return a nearest-rank percentile suitable for small gate samples."""

    if not values:
        raise ValueError("at least one latency sample is required")
    if not 0 < quantile <= 1:
        raise ValueError("quantile must be greater than zero and at most one")
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * quantile) - 1)]


def summarize(values: Sequence[float]) -> dict[str, float | int]:
    if not values:
        raise ValueError("at least one latency sample is required")
    return {
        "samples": len(values),
        "min_ms": round(min(values), 2),
        "mean_ms": round(fmean(values), 2),
        "p50_ms": round(percentile(values, 0.50), 2),
        "p95_ms": round(percentile(values, 0.95), 2),
        "max_ms": round(max(values), 2),
    }


async def timed(call: Callable[[], Awaitable[httpx.Response]]) -> float:
    started = perf_counter()
    response = await call()
    elapsed_ms = (perf_counter() - started) * 1_000
    response.raise_for_status()
    return elapsed_ms


async def measure(base_url: str, read_samples: int, chat_samples: int) -> dict[str, Any]:
    limits = {
        "health_p95_ms": 500.0,
        "ready_p95_ms": 500.0,
        "catalog_p95_ms": 1_000.0,
        "lightweight_turn_p95_ms": 8_000.0,
    }
    timeout = httpx.Timeout(15.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        # The first protected request creates one isolated guest session. It is
        # deliberately excluded so bootstrap/fixture creation does not pollute
        # the steady-state catalogue measurement.
        bootstrap = await client.get("/v1/workspace/catalog")
        bootstrap.raise_for_status()

        health = [await timed(lambda: client.get("/health")) for _ in range(read_samples)]
        ready = [await timed(lambda: client.get("/ready")) for _ in range(read_samples)]
        catalog = [
            await timed(lambda: client.get("/v1/workspace/catalog")) for _ in range(read_samples)
        ]
        lightweight_turn = [
            await timed(
                lambda: client.post(
                    "/v1/workspace/chat",
                    json={"mode": "sira", "message": "Hello", "history": []},
                )
            )
            for _ in range(chat_samples)
        ]

    metrics = {
        "health": summarize(health),
        "ready": summarize(ready),
        "catalog": summarize(catalog),
        "lightweight_turn": summarize(lightweight_turn),
    }
    checks = {
        "health_p95": metrics["health"]["p95_ms"] <= limits["health_p95_ms"],
        "ready_p95": metrics["ready"]["p95_ms"] <= limits["ready_p95_ms"],
        "catalog_p95": metrics["catalog"]["p95_ms"] <= limits["catalog_p95_ms"],
        "lightweight_turn_p95": (
            metrics["lightweight_turn"]["p95_ms"] <= limits["lightweight_turn_p95_ms"]
        ),
    }
    return {
        "schema_version": "sira.local-performance.v1",
        "environment": "local-development",
        "base_url": base_url,
        "limits": limits,
        "metrics": metrics,
        "checks": checks,
        "passed": all(checks.values()),
        "notes": [
            "Measurements exclude response bodies, cookies, credentials, prompts, and tenant IDs.",
            "This is a same-machine development gate, not hosted performance evidence.",
        ],
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--base-url", default="http://127.0.0.1:8000")
    result.add_argument("--read-samples", type=int, default=20)
    result.add_argument("--chat-samples", type=int, default=5)
    result.add_argument("--output", type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    if args.read_samples < 1:
        raise SystemExit("--read-samples must be at least one")
    if not 1 <= args.chat_samples <= 6:
        raise SystemExit("--chat-samples must be between one and six")
    report = asyncio.run(measure(args.base_url.rstrip("/"), args.read_samples, args.chat_samples))
    rendered = f"{json.dumps(report, indent=2, sort_keys=True)}\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
