from __future__ import annotations

import json
from hashlib import sha256
from types import SimpleNamespace
from typing import Any, cast

import pytest
from sira_worker.qualification import QualificationRunResult, QualificationWorker
from sira_worker.queue_consumer import QualificationQueueConsumer

from persistence.database import Database


class FakeSqs:
    def __init__(self, messages: list[dict[str, Any]] | None = None) -> None:
        self.messages = messages or []
        self.deleted: list[dict[str, Any]] = []

    def receive_message(self, **kwargs: Any) -> dict[str, Any]:
        return {"Messages": self.messages}

    def delete_message(self, **kwargs: Any) -> dict[str, Any]:
        self.deleted.append(kwargs)
        return {}


class FakeWorker:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def run_mission(
        self, *, organization_id: str, mission_id: str
    ) -> QualificationRunResult:
        self.calls.append((organization_id, mission_id))
        return QualificationRunResult(mission_id, "COMPLETED", ("attempt-1",), "decision-1")


def _message() -> dict[str, Any]:
    mission_id = "qmission_0123456789abcdef0123456789abcdef"
    envelope = {
        "schema_version": 1,
        "message_id": "outbox-1",
        "organization_id": "org_buyer",
        "aggregate_type": "QUALIFICATION_MISSION",
        "aggregate_id": mission_id,
        "event_type": "QUALIFICATION_MISSION_READY",
        "event_key": f"qualification-mission-ready:{mission_id}",
        "payload": {
            "mission_id": mission_id,
            "trace_id": "trace-1",
            "organization_id": "org_buyer",
        },
        "occurred_at": "2026-08-13T00:00:00+00:00",
    }
    body = json.dumps(envelope, sort_keys=True, separators=(",", ":"))
    return {
        "MessageId": "sqs-1",
        "ReceiptHandle": "receipt-1",
        "Body": body,
        "MessageAttributes": {
            "body_sha256": {
                "DataType": "String",
                "StringValue": sha256(body.encode()).hexdigest(),
            }
        },
    }


def _consumer(client: FakeSqs, worker: FakeWorker) -> QualificationQueueConsumer:
    return QualificationQueueConsumer(
        client=client,
        queue_url="https://sqs.example/qualification.fifo",
        database=cast(Database, object()),
        worker=cast(QualificationWorker, worker),
        wait_time_seconds=1,
    )


@pytest.mark.asyncio
async def test_process_executes_once_and_records_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    worker = FakeWorker()
    consumer = _consumer(FakeSqs(), worker)
    recorded: list[tuple[str, str]] = []

    async def no_receipt(*args: Any, **kwargs: Any) -> None:
        return None

    async def record(*args: Any, **kwargs: Any) -> None:
        recorded.append((args[1].message_id, args[3]))

    monkeypatch.setattr(QualificationQueueConsumer, "_receipt", no_receipt)
    monkeypatch.setattr(QualificationQueueConsumer, "_completed_result", no_receipt)
    monkeypatch.setattr(QualificationQueueConsumer, "_record_receipt", record)

    result = await consumer.process(_message())

    assert result.result_ref == "decision-1"
    assert result.replayed is False
    assert worker.calls == [
        ("org_buyer", "qmission_0123456789abcdef0123456789abcdef")
    ]
    assert recorded == [("outbox-1", "decision-1")]


@pytest.mark.asyncio
async def test_process_replays_durable_receipt_without_model_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = FakeWorker()
    consumer = _consumer(FakeSqs(), worker)

    async def receipt(*args: Any, **kwargs: Any) -> SimpleNamespace:
        body = str(_message()["Body"])
        return SimpleNamespace(
            result_ref="decision-existing",
            payload_hash=f"sha256:{sha256(body.encode()).hexdigest()}",
        )

    monkeypatch.setattr(QualificationQueueConsumer, "_receipt", receipt)

    result = await consumer.process(_message())

    assert result.result_ref == "decision-existing"
    assert result.replayed is True
    assert worker.calls == []


@pytest.mark.asyncio
async def test_poll_deletes_only_after_success(monkeypatch: pytest.MonkeyPatch) -> None:
    message = _message()
    client = FakeSqs([message])
    consumer = _consumer(client, FakeWorker())

    async def success(*args: Any, **kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(result_ref="decision-1")

    monkeypatch.setattr(QualificationQueueConsumer, "process", success)

    assert await consumer.poll_once() == 1
    assert client.deleted == [
        {
            "QueueUrl": "https://sqs.example/qualification.fifo",
            "ReceiptHandle": "receipt-1",
        }
    ]


@pytest.mark.asyncio
async def test_process_rejects_tampered_body_hash() -> None:
    message = _message()
    message["MessageAttributes"]["body_sha256"]["StringValue"] = "0" * 64
    consumer = _consumer(FakeSqs(), FakeWorker())

    with pytest.raises(ValueError, match="body hash"):
        await consumer.process(message)
