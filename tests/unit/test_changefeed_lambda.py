from __future__ import annotations

import json
from typing import Any

from sira_changefeed import handler


class Queue:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def send_message(self, **kwargs: Any) -> dict[str, str]:
        self.calls.append(kwargs)
        return {"MessageId": "message"}


def _event(payload: object, token: str = "t" * 40) -> dict[str, object]:
    return {
        "headers": {"Authorization": f"Basic {token}"},
        "body": json.dumps(payload),
        "isBase64Encoded": False,
    }


def test_duplicate_changefeed_delivery_has_stable_fifo_identity(monkeypatch: Any) -> None:
    queue = Queue()
    monkeypatch.setenv("CHANGEFEED_WEBHOOK_TOKEN", "t" * 40)
    monkeypatch.setenv("REEVALUATION_QUEUE_URL", "https://queue.example.test/reevaluation.fifo")
    monkeypatch.setattr(handler, "_queue_client", lambda: queue)
    payload = {
        "payload": [
            {
                "topic": "product_bundle_versions",
                "key": ["org_seller", "bundle_v2"],
                "after": {"id": "bundle_v2", "state": "ACTIVE"},
                "updated": "1755040000.0000000000",
            }
        ]
    }

    first = handler.lambda_handler(_event(payload), None)
    second = handler.lambda_handler(_event(payload), None)

    assert first["statusCode"] == second["statusCode"] == 202
    assert queue.calls[0]["MessageDeduplicationId"] == queue.calls[1]["MessageDeduplicationId"]
    assert queue.calls[0]["MessageGroupId"] == "bundle_v2"
    body = json.loads(queue.calls[0]["MessageBody"])
    assert body["authority"] == "HINT_ONLY_REREAD_COCKROACH"
    assert "after" not in body


def test_auth_malformed_and_unknown_topics_fail_closed(monkeypatch: Any) -> None:
    monkeypatch.setenv("CHANGEFEED_WEBHOOK_TOKEN", "t" * 40)
    monkeypatch.setenv("REEVALUATION_QUEUE_URL", "https://queue.example.test/reevaluation.fifo")
    assert handler.lambda_handler(_event({"payload": []}, "wrong" * 10), None)["statusCode"] == 401
    assert handler.lambda_handler(_event({"payload": "wrong"}), None)["statusCode"] == 400
    unknown = {
        "payload": [{"topic": "private_context", "key": ["id"], "after": {}, "updated": "1"}]
    }
    assert handler.lambda_handler(_event(unknown), None)["statusCode"] == 400


def test_resolved_watermark_is_acknowledged_without_queue_message(monkeypatch: Any) -> None:
    queue = Queue()
    monkeypatch.setenv("CHANGEFEED_WEBHOOK_TOKEN", "t" * 40)
    monkeypatch.setenv("REEVALUATION_QUEUE_URL", "https://queue.example.test/reevaluation.fifo")
    monkeypatch.setattr(handler, "_queue_client", lambda: queue)
    response = handler.lambda_handler(_event({"resolved": "1755040000.0000000000"}), None)
    assert response["statusCode"] == 202
    assert queue.calls == []
