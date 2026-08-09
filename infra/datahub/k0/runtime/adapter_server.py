"""Minimal deterministic proof adapter over a Unix domain socket."""

from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from typing import Any

MAX_REQUEST_BYTES = 64 * 1024


def _response(request: dict[str, Any]) -> dict[str, Any]:
    adapter_id = os.environ["COMPONENT_ID"]
    artifact_digest = os.environ["ADAPTER_ARTIFACT_DIGEST"]
    operation = request.get("operation")
    if operation == "health":
        return {
            "status": "healthy",
            "adapterId": adapter_id,
            "artifactDigest": artifact_digest,
            "protocol": "sira-proof-adapter/v1",
        }
    if operation == "evaluate":
        canary = request.get("canary")
        if not isinstance(canary, dict):
            return {"status": "error", "code": "INVALID_CANARY"}
        marker = canary.get("marker")
        return {
            "status": "pass" if marker == "SIRA_K0_CANARY" else "fail",
            "adapterId": adapter_id,
            "artifactDigest": artifact_digest,
            "observedMarker": marker,
        }
    if operation == "invoke":
        trial_id = request.get("trialId")
        case_id = request.get("caseId")
        nonce = request.get("nonce")
        trial_input = request.get("input")
        allowed_regions = request.get("allowedExecutionRegions")
        if not all(isinstance(value, str) and value for value in (trial_id, case_id, nonce)):
            return {"status": "error", "code": "INVALID_TRIAL_IDENTITY"}
        if not isinstance(trial_input, dict) or set(trial_input) != {
            "ticket_id",
            "body",
            "customer_email",
        }:
            return {"status": "error", "code": "INVALID_INPUT_SCHEMA"}
        if not isinstance(allowed_regions, list) or "EU" not in allowed_regions:
            return {"status": "error", "code": "REGION_NOT_ALLOWED"}
        customer_email = trial_input.get("customer_email")
        if not isinstance(customer_email, str):
            return {"status": "error", "code": "INVALID_CUSTOMER_EMAIL"}
        output_email = customer_email if adapter_id == "adapter-a" else "[REDACTED]"
        return {
            "status": "completed",
            "protocolVersion": "TrialResult/v0",
            "trialId": trial_id,
            "caseId": case_id,
            "nonce": nonce,
            "adapterId": adapter_id,
            "artifactDigest": artifact_digest,
            "declaredExecutionRegion": "EU",
            "redactedFields": [] if adapter_id == "adapter-a" else ["customer_email"],
            "output": {
                "ticket_id": trial_input["ticket_id"],
                "summary": "Synthetic support response",
                "customer_email": output_email,
            },
        }
    return {"status": "error", "code": "UNKNOWN_OPERATION"}


def main() -> None:
    socket_path = Path(os.environ["ADAPTER_SOCKET"])
    socket_path.unlink(missing_ok=True)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(socket_path))
        socket_path.chmod(0o660)
        server.listen(16)
        while True:
            connection, _ = server.accept()
            with connection:
                request_bytes = b""
                while not request_bytes.endswith(b"\n"):
                    chunk = connection.recv(4096)
                    if not chunk:
                        break
                    request_bytes += chunk
                    if len(request_bytes) > MAX_REQUEST_BYTES:
                        request_bytes = b""
                        break
                try:
                    request = json.loads(request_bytes)
                    response = _response(request) if isinstance(request, dict) else {}
                except (UnicodeDecodeError, json.JSONDecodeError):
                    response = {"status": "error", "code": "INVALID_JSON"}
                connection.sendall(json.dumps(response, sort_keys=True).encode() + b"\n")


if __name__ == "__main__":
    main()
