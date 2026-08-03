"""One-time owner approval for hosted SIRA when Prava permits loopback OAuth clients."""

# ruff: noqa: S310,T201 -- URLs are operator-supplied HTTPS API endpoints; stdout returns OAuth URL.

from __future__ import annotations

import argparse
import json
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _request(url: str, *, headers: dict[str, str], body: dict[str, object]) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise RuntimeError("SIRA returned an invalid response")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="https://sira-seil.vercel.app")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--organization", default="org_consultco")
    parser.add_argument("--actor", default="usr_demo_requester")
    args = parser.parse_args()
    headers = {
        "X-Organization-Id": args.organization,
        "X-Actor-Id": args.actor,
        "X-Actor-Party": "BUYER",
        "X-Actor-Roles": "can_view_context,can_execute_purchase",
        "X-Step-Up-Verified": "true",
        "X-Identity-Kind": "HUMAN",
    }
    completed = threading.Event()
    outcome: dict[str, object] = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            state = query.get("state", [""])[0]
            code = query.get("code", [""])[0]
            try:
                result = _request(
                    f"{args.api.rstrip('/')}/v1/connectors/prava/callback",
                    headers=headers,
                    body={"state": state, "code": code},
                )
                outcome.update(result)
                status = 200
                message = "Prava is connected to SIRA. You can close this tab."
            except Exception:
                outcome["status"] = "failed"
                status = 502
                message = "Prava connection failed. Return to SIRA and retry."
            payload = message.encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            completed.set()

        def log_message(self, format: str, *values: object) -> None:
            del format, values

    server = ThreadingHTTPServer(("127.0.0.1", args.port), CallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = _request(
        f"{args.api.rstrip('/')}/v1/connectors/prava/connect",
        headers=headers,
        body={"loopback_port": args.port},
    )
    authorization_url = connection.get("authorization_url")
    if not isinstance(authorization_url, str):
        raise RuntimeError("SIRA did not return a Prava authorization URL")
    print(authorization_url, flush=True)
    if not completed.wait(timeout=600):
        raise RuntimeError("Prava approval timed out")
    server.shutdown()
    return 0 if outcome.get("status") == "connected" else 1


if __name__ == "__main__":
    raise SystemExit(main())
