from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

import pytest

from integrations.aws_services import (
    AwsTransportError,
    ContentAddressedEvidenceStore,
    OutboxEnvelope,
    SqsFifoPublisher,
)


@dataclass
class FakeS3:
    response: dict[str, Any]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.response


@dataclass
class FakeSqs:
    response: dict[str, Any]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def send_message(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.response


async def test_s3_evidence_is_content_addressed_checksummed_versioned_and_encrypted() -> None:
    content = b"signed seller evidence"
    digest = sha256(content).hexdigest()
    checksum = base64.b64encode(bytes.fromhex(digest)).decode("ascii")
    client = FakeS3(response={"VersionId": "version-7", "ChecksumSHA256": checksum})
    store = ContentAddressedEvidenceStore(
        client=client,
        bucket="sira-evidence",
        kms_key_id="alias/sira-evidence",
    )

    result = await store.put(
        organization_id="org_seller_a",
        body=content,
        content_type="application/pdf",
    )

    assert result.key == f"organizations/org_seller_a/evidence/sha256/{digest}"
    assert result.version_id == "version-7"
    assert result.sha256 == f"sha256:{digest}"
    request = client.calls[0]
    assert request["ChecksumAlgorithm"] == "SHA256"
    assert request["ChecksumSHA256"] == checksum
    assert request["ServerSideEncryption"] == "aws:kms"
    assert request["SSEKMSKeyId"] == "alias/sira-evidence"
    assert request["BucketKeyEnabled"] is True
    assert "org_seller_a" not in request["Metadata"]


async def test_s3_evidence_fails_closed_without_version_or_matching_checksum() -> None:
    store = ContentAddressedEvidenceStore(client=FakeS3(response={}), bucket="evidence")
    with pytest.raises(AwsTransportError, match="versioning"):
        await store.put(organization_id="org_a", body=b"evidence", content_type="text/plain")

    store = ContentAddressedEvidenceStore(
        client=FakeS3(response={"VersionId": "v1", "ChecksumSHA256": "wrong"}),
        bucket="evidence",
    )
    with pytest.raises(AwsTransportError, match="mismatched"):
        await store.put(organization_id="org_a", body=b"evidence", content_type="text/plain")


async def test_sqs_fifo_message_uses_tenant_ordering_and_stable_deduplication() -> None:
    client = FakeSqs(response={"MessageId": "message-1", "SequenceNumber": "42"})
    publisher = SqsFifoPublisher(client=client, queue_url="https://sqs/qualification.fifo")
    envelope = OutboxEnvelope(
        id="outbox-1",
        organization_id="org_buyer",
        aggregate_type="QUALIFICATION_ATTEMPT",
        aggregate_id="attempt-1",
        event_type="QUALIFICATION_ATTEMPT_READY",
        event_key="attempt-ready:attempt-1:1",
        payload={"attempt_id": "attempt-1"},
        occurred_at="2026-08-13T00:00:00+00:00",
    )

    first = await publisher.publish(envelope)
    second = await publisher.publish(envelope)

    assert first.body_sha256 == second.body_sha256
    assert client.calls[0]["MessageGroupId"] == "org_buyer"
    assert client.calls[0]["MessageDeduplicationId"] == client.calls[1][
        "MessageDeduplicationId"
    ]
    body = json.loads(client.calls[0]["MessageBody"])
    assert body["schema_version"] == 1
    assert body["message_id"] == "outbox-1"
    assert body["payload"] == {"attempt_id": "attempt-1"}


async def test_sqs_fifo_requires_delivery_identity_and_valid_tenant() -> None:
    with pytest.raises(ValueError, match="organization_id"):
        OutboxEnvelope(
            id="outbox-1",
            organization_id="../other",
            aggregate_type="ATTEMPT",
            aggregate_id="attempt-1",
            event_type="READY",
            event_key="ready-1",
            payload={},
            occurred_at="now",
        )
    publisher = SqsFifoPublisher(client=FakeSqs(response={}), queue_url="queue")
    with pytest.raises(AwsTransportError, match="delivery identity"):
        await publisher.publish(
            OutboxEnvelope(
                id="outbox-1",
                organization_id="org_a",
                aggregate_type="ATTEMPT",
                aggregate_id="attempt-1",
                event_type="READY",
                event_key="ready-1",
                payload={},
                occurred_at="2026-08-13T00:00:00+00:00",
            )
        )
