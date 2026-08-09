"""Exercise router CAS, probes, induced failure, rollback, and restoration."""

from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path
from typing import Any

ROUTER_SOCKET = "/run/proof/router.sock"


def _request(payload: dict[str, Any]) -> dict[str, Any]:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(3.0)
        client.connect(ROUTER_SOCKET)
        client.sendall(json.dumps(payload, sort_keys=True).encode() + b"\n")
        response = client.recv(64 * 1024)
    result = json.loads(response)
    if not isinstance(result, dict):
        raise RuntimeError("router response was not an object")
    return result


def _wait_for_router() -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if Path(ROUTER_SOCKET).exists():
            try:
                if _request({"operation": "read"}).get("status") == "ok":
                    return
            except OSError:
                pass
        time.sleep(0.25)
    raise RuntimeError("router did not become ready")


def main() -> int:
    _wait_for_router()
    digest_a = os.environ["ADAPTER_A_DIGEST"]
    digest_b = os.environ["ADAPTER_B_DIGEST"]
    initial = _request({"operation": "read"})
    if initial["state"]["activeDigest"] != digest_b:
        raise RuntimeError("router did not begin on adapter B")
    applied = _request(
        {
            "operation": "cas_apply",
            "expectedVersion": initial["state"]["version"],
            "targetDigest": digest_a,
            "targetSocket": "/run/proof/adapter-a.sock",
        }
    )
    if applied.get("status") != "applied":
        raise RuntimeError("adapter A activation failed")
    active_probe = _request({"operation": "probe"})
    if active_probe["probe"].get("artifactDigest") != digest_a:
        raise RuntimeError("routed health probe did not observe adapter A")
    routed = _request(
        {
            "operation": "route_invoke",
            "trial": {
                "protocolVersion": "TrialCase/v0",
                "trialId": "router-effect-trial-v1",
                "caseId": "router-effect-canary-v1",
                "nonce": "router-effect-nonce-v1",
                "allowedExecutionRegions": ["EU"],
                "input": {
                    "ticket_id": "ticket-router-001",
                    "body": "Synthetic routed traffic probe.",
                    "customer_email": "route-marker@example.invalid",
                },
            },
        }
    )
    if (
        routed.get("status") != "routed"
        or routed.get("activeDigest") != digest_a
        or routed.get("result", {}).get("adapterId") != "adapter-a"
    ):
        raise RuntimeError("routed traffic did not execute through active adapter A")
    induced_failure = _request(
        {
            "operation": "cas_apply",
            "expectedVersion": applied["state"]["version"],
            "targetDigest": "sha256:missing",
            "targetSocket": "/run/proof/missing.sock",
        }
    )
    if induced_failure.get("code") != "TARGET_UNHEALTHY":
        raise RuntimeError("induced unhealthy target was not rejected")
    unchanged = _request({"operation": "read"})
    if unchanged["state"] != applied["state"]:
        raise RuntimeError("failed activation changed router state")
    rollback = _request(
        {
            "operation": "cas_rollback",
            "expectedVersion": unchanged["state"]["version"],
            "targetDigest": digest_b,
            "targetSocket": "/run/proof/adapter-b.sock",
        }
    )
    if rollback.get("status") != "applied":
        raise RuntimeError("rollback to adapter B failed")
    restored_probe = _request({"operation": "probe"})
    if restored_probe["probe"].get("artifactDigest") != digest_b:
        raise RuntimeError("restored route did not serve adapter B")
    print(  # noqa: T201 - container probe emits the machine-readable artifact
        json.dumps(
            {
                "status": "PASS",
                "initial": initial,
                "applied": applied,
                "activeProbe": active_probe,
                "routedTraffic": routed,
                "inducedFailure": induced_failure,
                "unchangedAfterFailure": unchanged,
                "rollback": rollback,
                "restoredProbe": restored_probe,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
