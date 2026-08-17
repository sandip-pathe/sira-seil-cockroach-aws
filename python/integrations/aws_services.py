"""Narrow AWS transport adapters; CockroachDB remains the authority."""

from __future__ import annotations

import asyncio
import base64
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from secrets import token_urlsafe
from typing import Any, Protocol, cast

_ORGANIZATION_ID = re.compile(r"[A-Za-z0-9_-]{1,48}\Z")
MAX_EVIDENCE_BYTES = 25 * 1024 * 1024
_MAX_QUEUE_BODY_BYTES = 256 * 1024


class AwsTransportError(RuntimeError):
    """AWS acknowledged a request without the required integrity metadata."""


class S3Client(Protocol):
    def put_object(self, **kwargs: Any) -> Mapping[str, Any]: ...


class SqsClient(Protocol):
    def send_message(self, **kwargs: Any) -> Mapping[str, Any]: ...


class EvidenceStore(Protocol):
    async def put(
        self, *, organization_id: str, body: bytes, content_type: str
    ) -> StoredEvidenceObject: ...


def create_aws_client(
    service: str, *, region: str, profile: str | None = None
) -> S3Client | SqsClient:
    """Create an AWS client from a local profile or an ECS task role."""

    import boto3  # type: ignore[import-untyped]
    from botocore.config import Config  # type: ignore[import-untyped]

    if service not in {"s3", "sqs"}:
        raise ValueError("unsupported AWS service")
    if not region.strip():
        raise ValueError("AWS region is required")
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    return cast(
        S3Client | SqsClient,
        session.client(
            service,
            region_name=region,
            config=Config(
                connect_timeout=5,
                read_timeout=30,
                retries={"mode": "standard", "max_attempts": 3},
            ),
        ),
    )


@dataclass(frozen=True, slots=True)
class StoredEvidenceObject:
    bucket: str
    key: str
    version_id: str
    sha256: str
    size_bytes: int
    content_type: str


@dataclass(slots=True)
class ContentAddressedEvidenceStore:
    """Write immutable evidence bytes; the DB stores and gates the returned identity."""

    client: S3Client = field(repr=False)
    bucket: str
    kms_key_id: str | None = None
    require_version_id: bool = True

    async def put(
        self,
        *,
        organization_id: str,
        body: bytes,
        content_type: str,
    ) -> StoredEvidenceObject:
        _validate_organization_id(organization_id)
        if not body:
            raise ValueError("evidence object must not be empty")
        if len(body) > MAX_EVIDENCE_BYTES:
            raise ValueError("evidence object exceeds the 25 MiB ingestion limit")
        if not content_type.strip() or len(content_type) > 120:
            raise ValueError("evidence content type is invalid")

        digest = sha256(body).hexdigest()
        checksum = base64.b64encode(bytes.fromhex(digest)).decode("ascii")
        key = f"organizations/{organization_id}/evidence/sha256/{digest}"
        request: dict[str, Any] = {
            "Bucket": self.bucket,
            "Key": key,
            "Body": body,
            "ContentType": content_type,
            "ChecksumAlgorithm": "SHA256",
            "ChecksumSHA256": checksum,
            "Metadata": {"content-sha256": digest},
        }
        if self.kms_key_id:
            request.update(
                {
                    "ServerSideEncryption": "aws:kms",
                    "SSEKMSKeyId": self.kms_key_id,
                    "BucketKeyEnabled": True,
                }
            )
        else:
            request["ServerSideEncryption"] = "AES256"
        response = await asyncio.to_thread(self.client.put_object, **request)
        returned_checksum = response.get("ChecksumSHA256")
        if returned_checksum is not None and returned_checksum != checksum:
            raise AwsTransportError("S3 returned a mismatched SHA-256 checksum")
        version_id = str(response.get("VersionId", ""))
        if self.require_version_id and not version_id:
            raise AwsTransportError("S3 bucket versioning is required for evidence")
        return StoredEvidenceObject(
            bucket=self.bucket,
            key=key,
            version_id=version_id,
            sha256="sha256:" + digest,
            size_bytes=len(body),
            content_type=content_type,
        )


@dataclass(slots=True)
class LocalContentAddressedEvidenceStore:
    """Credential-free local adapter with the same immutable checksum contract as S3."""

    root: Path

    async def put(
        self,
        *,
        organization_id: str,
        body: bytes,
        content_type: str,
    ) -> StoredEvidenceObject:
        _validate_organization_id(organization_id)
        if not body:
            raise ValueError("evidence object must not be empty")
        if len(body) > MAX_EVIDENCE_BYTES:
            raise ValueError("evidence object exceeds the 25 MiB ingestion limit")
        if not content_type.strip() or len(content_type) > 120:
            raise ValueError("evidence content type is invalid")
        digest = sha256(body).hexdigest()
        root = self.root.resolve()
        destination = (root / organization_id / "evidence" / "sha256" / digest).resolve()
        if root not in destination.parents:
            raise ValueError("local evidence path escaped its configured root")

        def store() -> None:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                if sha256(destination.read_bytes()).hexdigest() != digest:
                    raise OSError("local evidence object checksum mismatch")
                return
            temporary = destination.with_suffix(f".{token_urlsafe(8)}.tmp")
            temporary.write_bytes(body)
            temporary.replace(destination)

        await asyncio.to_thread(store)
        relative_key = destination.relative_to(root).as_posix()
        return StoredEvidenceObject(
            bucket="local-evidence",
            key=relative_key,
            version_id=f"sha256-{digest}",
            sha256=f"sha256:{digest}",
            size_bytes=len(body),
            content_type=content_type,
        )


@dataclass(frozen=True, slots=True)
class OutboxEnvelope:
    id: str
    organization_id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    event_key: str
    payload: Mapping[str, Any]
    occurred_at: str

    def __post_init__(self) -> None:
        _validate_organization_id(self.organization_id)
        required = (
            self.id,
            self.aggregate_type,
            self.aggregate_id,
            self.event_type,
            self.event_key,
            self.occurred_at,
        )
        if any(not value.strip() for value in required):
            raise ValueError("outbox envelope fields must not be empty")

    def body(self) -> bytes:
        return json.dumps(
            {
                "schema_version": 1,
                "message_id": self.id,
                "organization_id": self.organization_id,
                "aggregate_type": self.aggregate_type,
                "aggregate_id": self.aggregate_id,
                "event_type": self.event_type,
                "event_key": self.event_key,
                "payload": self.payload,
                "occurred_at": self.occurred_at,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class PublishedMessage:
    message_id: str
    sequence_number: str
    body_sha256: str


@dataclass(slots=True)
class SqsFifoPublisher:
    """Publish an outbox envelope; durable consumer receipts still deduplicate work."""

    client: SqsClient = field(repr=False)
    queue_url: str

    async def publish(self, envelope: OutboxEnvelope) -> PublishedMessage:
        body = envelope.body()
        if len(body) > _MAX_QUEUE_BODY_BYTES:
            raise ValueError("outbox envelope exceeds the conservative 256 KiB queue limit")
        body_digest = sha256(body).hexdigest()
        deduplication_id = sha256(envelope.event_key.encode("utf-8")).hexdigest()
        response = await asyncio.to_thread(
            self.client.send_message,
            QueueUrl=self.queue_url,
            MessageBody=body.decode("utf-8"),
            MessageGroupId=envelope.organization_id,
            MessageDeduplicationId=deduplication_id,
            MessageAttributes={
                "event_type": {"DataType": "String", "StringValue": envelope.event_type},
                "body_sha256": {"DataType": "String", "StringValue": body_digest},
            },
        )
        message_id = str(response.get("MessageId", ""))
        sequence_number = str(response.get("SequenceNumber", ""))
        if not message_id or not sequence_number:
            raise AwsTransportError("SQS FIFO response omitted delivery identity")
        return PublishedMessage(message_id, sequence_number, "sha256:" + body_digest)


def _validate_organization_id(value: str) -> None:
    if not _ORGANIZATION_ID.fullmatch(value):
        raise ValueError("organization_id is invalid")
