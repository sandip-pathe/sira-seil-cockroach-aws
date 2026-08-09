"""Compare-and-set proof router with health probes and atomic local state."""

from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from typing import Any

MAX_REQUEST_BYTES = 64 * 1024
STATE_PATH = Path("/state/route.json")


def _read_state() -> dict[str, Any]:
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def _write_state(state: dict[str, Any]) -> None:
    temporary = STATE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, STATE_PATH)


def _adapter_health(socket_path: str) -> dict[str, Any]:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(2.0)
            client.connect(socket_path)
            client.sendall(b'{"operation":"health"}\n')
            response = client.recv(MAX_REQUEST_BYTES)
        payload = json.loads(response)
        if not isinstance(payload, dict):
            raise ValueError("adapter health response was not an object")
        return payload
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"status": "unhealthy", "error": type(exc).__name__}


def _transition(request: dict[str, Any], event: str) -> dict[str, Any]:
    state = _read_state()
    expected_version = request.get("expectedVersion")
    if expected_version != state["version"]:
        return {"status": "conflict", "code": "VERSION_MISMATCH", "state": state}
    target_digest = request.get("targetDigest")
    target_socket = request.get("targetSocket")
    if not isinstance(target_digest, str) or not isinstance(target_socket, str):
        return {"status": "rejected", "code": "INVALID_TARGET", "state": state}
    health = _adapter_health(target_socket)
    if health.get("status") != "healthy" or health.get("artifactDigest") != target_digest:
        return {"status": "rejected", "code": "TARGET_UNHEALTHY", "health": health, "state": state}
    next_state = {
        "version": state["version"] + 1,
        "activeDigest": target_digest,
        "activeSocket": target_socket,
        "lastEvent": event,
    }
    _write_state(next_state)
    observed = _adapter_health(target_socket)
    if observed.get("artifactDigest") != target_digest:
        _write_state(state)
        return {"status": "reverted", "code": "POST_APPLY_PROBE_FAILED", "state": state}
    return {"status": "applied", "state": next_state, "probe": observed}


def _handle(request: dict[str, Any]) -> dict[str, Any]:
    operation = request.get("operation")
    if operation == "read":
        return {"status": "ok", "state": _read_state()}
    if operation == "probe":
        state = _read_state()
        return {"status": "ok", "state": state, "probe": _adapter_health(state["activeSocket"])}
    if operation == "cas_apply":
        return _transition(request, "apply")
    if operation == "cas_rollback":
        return _transition(request, "rollback")
    return {"status": "error", "code": "UNKNOWN_OPERATION"}


def main() -> None:
    _write_state(
        {
            "version": 1,
            "activeDigest": os.environ["INITIAL_ADAPTER_DIGEST"],
            "activeSocket": os.environ["INITIAL_ADAPTER_SOCKET"],
            "lastEvent": "initialize",
        }
    )
    socket_path = Path(os.environ["ROUTER_SOCKET"])
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
                    response = _handle(request) if isinstance(request, dict) else {}
                except (UnicodeDecodeError, json.JSONDecodeError):
                    response = {"status": "error", "code": "INVALID_JSON"}
                connection.sendall(json.dumps(response, sort_keys=True).encode() + b"\n")


if __name__ == "__main__":
    main()
