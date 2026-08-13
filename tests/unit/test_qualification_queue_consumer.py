from __future__ import annotations

import json
from hashlib import sha256
from types import SimpleNamespace
from typing import Any, cast

import pytest
from sira_worker.qualification import QualificationRunResult, QualificationWorker
from sira_worker.queue_consumer import QualificationQueueConsumer

from domain import content_hash
from persistence.database import Database, DatabaseSettings
from persistence.models import Base
from persistence.qualification_models import QualificationDecision, QualificationMission


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

    async def run_mission(self, *, organization_id: str, mission_id: str) -> QualificationRunResult:
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
    assert worker.calls == [("org_buyer", "qmission_0123456789abcdef0123456789abcdef")]
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


@pytest.mark.asyncio
async def test_completed_mission_is_receipted_and_replayed_without_worker() -> None:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    message = _message()
    mission_id = "qmission_0123456789abcdef0123456789abcdef"
    decision_id = "qdecision_completed"
    digest = content_hash({"mission": mission_id})
    async with database.transaction("org_buyer") as session:
        session.add(
            QualificationMission(
                id=mission_id,
                buyer_context_version_id="context-v1",
                buyer_context_hash=digest,
                buyer_context_payload={"company": "Buyer"},
                requirement_brief_version_id="brief-v1",
                requirement_brief_hash=digest,
                requirement_brief_payload={"category": "meeting-intelligence"},
                procurement_policy_version="policy-v1",
                procurement_policy_hash=digest,
                procurement_policy_payload={"human_approval": True},
                trace_id="trace-1",
                state="COMPLETED",
                version=1,
                organization_id="org_buyer",
            )
        )
        session.add(
            QualificationDecision(
                id=decision_id,
                mission_id=mission_id,
                attempt_id="attempt-completed",
                input_digest=digest,
                decision_digest=content_hash({"decision": decision_id}),
                recommended_product_id="product-completed",
                payload={"summary": "complete"},
                approval_state="APPROVED",
                current=True,
                organization_id="org_buyer",
            )
        )
    worker = FakeWorker()
    consumer = QualificationQueueConsumer(
        client=FakeSqs(),
        queue_url="https://sqs.example/qualification.fifo",
        database=database,
        worker=cast(QualificationWorker, worker),
        wait_time_seconds=1,
    )
    try:
        first = await consumer.process(message)
        second = await consumer.process(message)
        assert first.result_ref == second.result_ref == decision_id
        assert first.replayed is False
        assert second.replayed is True
        assert worker.calls == []
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_poll_rejects_malformed_sqs_responses() -> None:
    consumer = _consumer(FakeSqs(), FakeWorker())
    consumer.client = cast(Any, SimpleNamespace(receive_message=lambda **_kwargs: {"Messages": {}}))
    with pytest.raises(RuntimeError, match="message collection"):
        await consumer.poll_once()

    consumer.client = cast(
        Any, SimpleNamespace(receive_message=lambda **_kwargs: {"Messages": ["invalid"]})
    )
    with pytest.raises(RuntimeError, match="invalid message"):
        await consumer.poll_once()

    consumer.client = cast(
        Any, SimpleNamespace(receive_message=lambda **_kwargs: {"Messages": [{}]})
    )
    with pytest.raises(RuntimeError, match="receipt handle"):
        await consumer.poll_once()
