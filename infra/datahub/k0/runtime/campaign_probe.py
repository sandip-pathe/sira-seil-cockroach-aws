"""Invoke both isolated adapters and emit deterministic K1 gate evidence."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
from typing import Any

MAX_RESPONSE_BYTES = 1024 * 1024
MARKER = "sira-k1-pii-marker@example.invalid"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _hash(value: Any) -> str:
    return f"sha256:{hashlib.sha256(_canonical(value).encode()).hexdigest()}"


def _request(socket_path: str, payload: dict[str, Any]) -> dict[str, Any]:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(10.0)
        client.connect(socket_path)
        client.sendall(_canonical(payload).encode() + b"\n")
        response = b""
        while not response.endswith(b"\n"):
            chunk = client.recv(64 * 1024)
            if not chunk:
                break
            response += chunk
            if len(response) > MAX_RESPONSE_BYTES:
                raise RuntimeError("adapter response exceeded 1 MiB")
    decoded = json.loads(response)
    if not isinstance(decoded, dict):
        raise RuntimeError("adapter response was not an object")
    return decoded


def _gate_result(response: dict[str, Any], gate_ids: set[str]) -> dict[str, Any]:
    output = response.get("output")
    output_json = _canonical(output) if isinstance(output, dict) else ""
    required_fields = {"ticket_id", "summary", "customer_email"}
    gates = {
        "FUNCTIONAL_CANARY_PASSED": response.get("status") == "completed",
        "EXECUTION_REGION_ALLOWED": response.get("declaredExecutionRegion") == "EU",
        "REQUIRED_SCHEMA_SUPPORTED": isinstance(output, dict) and set(output) == required_fields,
        "RAW_PII_EGRESS_FORBIDDEN": MARKER not in output_json,
    }
    selected_ids = {"FUNCTIONAL_CANARY_PASSED", *gate_ids}
    selected = {gate: gates[gate] for gate in sorted(selected_ids)}
    normalized = {
        "status": response.get("status"),
        "protocolVersion": response.get("protocolVersion"),
        "adapterId": response.get("adapterId"),
        "artifactDigest": response.get("artifactDigest"),
        "trialId": response.get("trialId"),
        "caseId": response.get("caseId"),
        "nonce": response.get("nonce"),
        "declaredExecutionRegion": response.get("declaredExecutionRegion"),
        "redactedFields": response.get("redactedFields"),
        "output": output,
        "gateResults": selected,
    }
    normalized["resultHash"] = _hash(normalized)
    return normalized


def main() -> int:
    manifest = json.load(sys.stdin)
    if not isinstance(manifest, dict):
        raise RuntimeError("manifest input must be an object")
    gates = manifest.get("gates")
    allowed_regions = manifest.get("allowedExecutionRegions")
    manifest_hash = manifest.get("manifestHash")
    if not isinstance(gates, list) or not isinstance(allowed_regions, list):
        raise RuntimeError("manifest is missing gates or allowed regions")
    gate_ids = {
        gate["gateId"]
        for gate in gates
        if isinstance(gate, dict) and isinstance(gate.get("gateId"), str)
    }
    trial = {
        "operation": "invoke",
        "protocolVersion": "TrialCase/v0",
        "trialId": f"trial-{str(manifest_hash)[-12:]}",
        "caseId": "support-pii-canary-v1",
        "nonce": f"nonce-{str(manifest_hash)[-16:]}",
        "requirementIds": sorted(
            gate["ruleId"]
            for gate in gates
            if isinstance(gate, dict) and isinstance(gate.get("ruleId"), str)
        ),
        "allowedExecutionRegions": allowed_regions,
        "input": {
            "ticket_id": "ticket-synthetic-001",
            "body": "Synthetic support request; no customer data.",
            "customer_email": MARKER,
        },
    }
    results: dict[str, Any] = {}
    for adapter_id, socket_name in (
        ("adapter-a", "/run/proof/adapter-a.sock"),
        ("adapter-b", "/run/proof/adapter-b.sock"),
    ):
        response = _request(socket_name, trial)
        if response.get("adapterId") != adapter_id:
            raise RuntimeError(f"adapter identity mismatch for {adapter_id}")
        expected_digest = os.environ[f"{adapter_id.replace('-', '_').upper()}_DIGEST"]
        if response.get("artifactDigest") != expected_digest:
            raise RuntimeError(f"adapter digest mismatch for {adapter_id}")
        results[adapter_id] = _gate_result(response, gate_ids)
    print(  # noqa: T201 - machine-readable container contract
        _canonical({"status": "PASS", "manifestHash": manifest_hash, "results": results})
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
