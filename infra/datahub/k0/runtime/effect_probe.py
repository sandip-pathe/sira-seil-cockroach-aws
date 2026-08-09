"""Execute one exact router CAS apply or rollback and verify routed traffic."""

from __future__ import annotations

import hashlib
import json
import socket
import sys
from typing import Any

ROUTER_SOCKET = "/run/proof/router.sock"


def _request(payload: dict[str, Any]) -> dict[str, Any]:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(5.0)
        client.connect(ROUTER_SOCKET)
        client.sendall(json.dumps(payload, sort_keys=True).encode() + b"\n")
        result = json.loads(client.recv(1024 * 1024))
    if not isinstance(result, dict):
        raise RuntimeError("router response was not an object")
    return result


def _hash(value: object) -> str:
    rendered = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
    return f"sha256:{hashlib.sha256(rendered).hexdigest()}"


def main() -> int:
    plan = json.load(sys.stdin)
    if not isinstance(plan, dict):
        raise RuntimeError("effect plan must be an object")
    operation = plan.get("operation")
    if operation not in {"apply", "rollback"}:
        raise RuntimeError("effect operation must be apply or rollback")
    target_adapter_id = str(plan["targetAdapterId"])
    target_digest = str(plan["targetDigest"])
    expected_prior_digest = str(plan["expectedPriorDigest"])
    initial = _request({"operation": "read"})
    if initial.get("state", {}).get("activeDigest") != expected_prior_digest:
        raise RuntimeError("router prior digest does not match the approved effect plan")
    transitioned = _request(
        {
            "operation": "cas_apply" if operation == "apply" else "cas_rollback",
            "expectedVersion": initial["state"]["version"],
            "targetDigest": target_digest,
            "targetSocket": f"/run/proof/{target_adapter_id}.sock",
        }
    )
    if transitioned.get("status") != "applied":
        raise RuntimeError(f"router {operation} failed: {transitioned}")
    probe = _request({"operation": "probe"})
    if probe.get("probe", {}).get("artifactDigest") != target_digest:
        raise RuntimeError("router health did not observe the exact target digest")
    routed = _request(
        {
            "operation": "route_invoke",
            "trial": {
                "protocolVersion": "TrialCase/v0",
                "trialId": str(plan["trialId"]),
                "caseId": "verified-route-effect-v1",
                "nonce": str(plan["nonce"]),
                "allowedExecutionRegions": ["EU"],
                "input": {
                    "ticket_id": "ticket-effect-001",
                    "body": "Synthetic post-activation routed traffic verification.",
                    "customer_email": "effect-marker@example.invalid",
                },
            },
        }
    )
    if (
        routed.get("status") != "routed"
        or routed.get("activeDigest") != target_digest
        or routed.get("result", {}).get("adapterId") != target_adapter_id
    ):
        raise RuntimeError("post-activation routed traffic identity mismatch")
    output = {
        "status": "VERIFIED",
        "operation": operation,
        "priorState": initial["state"],
        "verifiedState": transitioned["state"],
        "health": probe["probe"],
        "routedTraffic": routed,
        "routedTrafficResultHash": _hash(routed),
    }
    print(json.dumps(output, separators=(",", ":"), sort_keys=True))  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
