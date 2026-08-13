"""Authenticated CockroachDB webhook to SQS FIFO bridge.

Cockroach changefeeds are at-least-once and only ordered per key. The Lambda does
not infer business state from CDC payloads; it emits deterministic hints and the
qualification worker must re-read the current CockroachDB version before acting.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from collections.abc import Mapping
from typing import Any, Protocol, cast

_MAX_BODY_BYTES = 1024 * 1024
_MAX_EVENTS = 100
_TOPICS = frozenset({"product_bundle_versions", "qualification_product_bundles"})


class QueueClient(Protocol):
    def send_message(self, **kwargs: Any) -> Mapping[str, Any]: ...


def lambda_handler(event: Mapping[str, Any], _context: object) -> dict[str, object]:
    secret = _webhook_token()
    queue_url = os.environ.get("REEVALUATION_QUEUE_URL", "")
    if len(secret.encode("utf-8")) < 32 or not queue_url:
        return _response(503, "bridge_not_configured")
    if not _authorized(event.get("headers"), secret):
        return _response(401, "unauthorized")
    try:
        raw = _body(event)
        document = json.loads(raw)
        hints = _hints(document)
    except (TypeError, ValueError, json.JSONDecodeError):
        return _response(400, "invalid_changefeed_payload")

    client = _queue_client()
    for hint in hints:
        body = json.dumps(hint, sort_keys=True, separators=(",", ":"))
        client.send_message(
            QueueUrl=queue_url,
            MessageBody=body,
            MessageGroupId=hint["aggregate_id"],
            MessageDeduplicationId=hint["source_event_id"],
            MessageAttributes={
                "event_type": {
                    "DataType": "String",
                    "StringValue": "PRODUCT_BUNDLE_CHANGED_HINT",
                }
            },
        )
    return _response(202, "accepted", accepted=len(hints))


def _hints(document: object) -> tuple[dict[str, str], ...]:
    if not isinstance(document, Mapping) or set(document).difference({"payload", "resolved"}):
        raise ValueError("unexpected envelope")
    payload = document.get("payload", [])
    if payload is None and "resolved" in document:
        return ()
    if not isinstance(payload, list) or len(payload) > _MAX_EVENTS:
        raise ValueError("invalid batch")
    hints: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, Mapping):
            raise ValueError("invalid event")
        topic = item.get("topic")
        key = item.get("key")
        after = item.get("after")
        updated = item.get("updated")
        if topic not in _TOPICS or not isinstance(key, list) or not key:
            raise ValueError("unsupported event")
        if after is not None and not isinstance(after, Mapping):
            raise ValueError("invalid row")
        aggregate_id = str(key[-1])
        if not aggregate_id or len(aggregate_id) > 128 or not isinstance(updated, str):
            raise ValueError("invalid identity")
        canonical = json.dumps(
            {"topic": topic, "key": key, "updated": updated},
            sort_keys=True,
            separators=(",", ":"),
        )
        hints.append(
            {
                "schema_version": "1",
                "event_type": "PRODUCT_BUNDLE_CHANGED_HINT",
                "aggregate_id": aggregate_id,
                "source_updated_at": updated,
                "source_event_id": hashlib.sha256(canonical.encode()).hexdigest(),
                "authority": "HINT_ONLY_REREAD_COCKROACH",
            }
        )
    return tuple(hints)


def _authorized(headers: object, secret: str) -> bool:
    if not isinstance(headers, Mapping):
        return False
    normalized = {str(key).lower(): str(value) for key, value in headers.items()}
    supplied = normalized.get("authorization", "")
    return hmac.compare_digest(supplied, f"Basic {secret}")


def _body(event: Mapping[str, Any]) -> str:
    body = event.get("body")
    if not isinstance(body, str):
        raise ValueError("body required")
    raw = (
        base64.b64decode(body, validate=True)
        if event.get("isBase64Encoded") is True
        else body.encode()
    )
    if not raw or len(raw) > _MAX_BODY_BYTES:
        raise ValueError("body size")
    return raw.decode("utf-8")


def _queue_client() -> QueueClient:
    import boto3  # type: ignore[import-untyped]

    return cast(QueueClient, boto3.client("sqs", region_name=os.environ.get("AWS_REGION")))


def _webhook_token() -> str:
    direct = os.environ.get("CHANGEFEED_WEBHOOK_TOKEN", "")
    if direct:
        return direct
    secret_arn = os.environ.get("CHANGEFEED_WEBHOOK_TOKEN_SECRET_ARN", "")
    if not secret_arn:
        return ""
    import boto3

    response = boto3.client(
        "secretsmanager", region_name=os.environ.get("AWS_REGION")
    ).get_secret_value(SecretId=secret_arn)
    value = response.get("SecretString", "")
    return str(value) if value else ""


def _response(status: int, result: str, *, accepted: int = 0) -> dict[str, object]:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps({"result": result, "accepted": accepted}, separators=(",", ":")),
    }
