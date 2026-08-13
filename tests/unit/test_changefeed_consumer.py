from __future__ import annotations

import json
from typing import Any, cast

import pytest
from sira_worker.changefeed_consumer import ChangefeedHintConsumer

from persistence.database import Database
from persistence.qualification_repository import BundleInvalidationResult


class FakeQueue:
    def __init__(self, messages: list[dict[str, Any]]) -> None:
        self.messages = messages
        self.deleted: list[dict[str, Any]] = []

    def receive_message(self, **_kwargs: Any) -> dict[str, object]:
        return {"Messages": self.messages}

    def delete_message(self, **kwargs: Any) -> dict[str, object]:
        self.deleted.append(kwargs)
        return {}


class FakeDatabase:
    def __init__(self) -> None:
        self.organizations: list[str] = []

    async def run_retryable(self, organization_id: str, work: Any) -> Any:
        self.organizations.append(organization_id)
        return await work(object())

    async def organization_ids(self) -> tuple[str, ...]:
        return ("org_dynamic",)


def _message() -> dict[str, str]:
    return {
        "ReceiptHandle": "receipt-1",
        "Body": json.dumps(
            {
                "schema_version": "1",
                "event_type": "PRODUCT_BUNDLE_CHANGED_HINT",
                "aggregate_id": "product_alpha",
                "source_updated_at": "1755040000.0000000000",
                "source_event_id": "a" * 64,
                "authority": "HINT_ONLY_REREAD_COCKROACH",
            }
        ),
    }


@pytest.mark.asyncio
async def test_hint_rechecks_each_configured_buyer_and_deletes_after_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue = FakeQueue([_message()])
    database = FakeDatabase()
    calls: list[tuple[str, str]] = []

    async def invalidate(_self: Any, *, product_id: str) -> BundleInvalidationResult:
        calls.append((_self.organization_id, product_id))
        return BundleInvalidationResult(product_id, (f"decision-{_self.organization_id}",), ())

    monkeypatch.setattr(
        "sira_worker.changefeed_consumer.QualificationRepository.invalidate_decisions_for_active_bundle",
        invalidate,
    )
    consumer = ChangefeedHintConsumer(
        client=queue,
        queue_url="https://sqs.example/changefeed.fifo",
        database=cast(Database, database),
        organization_ids=("org_a", "org_b"),
        wait_time_seconds=1,
    )

    assert await consumer.poll_once() == 1
    assert calls == [
        ("org_a", "product_alpha"),
        ("org_b", "product_alpha"),
        ("org_dynamic", "product_alpha"),
    ]
    assert database.organizations == ["org_a", "org_b", "org_dynamic"]
    assert queue.deleted[0]["ReceiptHandle"] == "receipt-1"


@pytest.mark.asyncio
async def test_hint_validation_fails_closed_without_deleting() -> None:
    queue = FakeQueue([{"ReceiptHandle": "receipt-1", "Body": "{}"}])
    consumer = ChangefeedHintConsumer(
        client=queue,
        queue_url="https://sqs.example/changefeed.fifo",
        database=cast(Database, FakeDatabase()),
        organization_ids=("org_a",),
        wait_time_seconds=1,
    )

    with pytest.raises(ValueError):
        await consumer.poll_once()
    assert queue.deleted == []
