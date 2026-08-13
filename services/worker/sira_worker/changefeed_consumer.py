"""Consume isolated changefeed hints by re-reading authoritative Cockroach state."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from persistence.database import Database
from persistence.qualification_repository import (
    BundleInvalidationResult,
    QualificationRepository,
)


class SqsHintClient(Protocol):
    def receive_message(self, **kwargs: Any) -> Mapping[str, Any]: ...

    def delete_message(self, **kwargs: Any) -> Mapping[str, Any]: ...


class ProductBundleChangedHint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1$")
    event_type: str = Field(pattern=r"^PRODUCT_BUNDLE_CHANGED_HINT$")
    aggregate_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    source_updated_at: str = Field(min_length=1, max_length=64)
    source_event_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    authority: str = Field(pattern=r"^HINT_ONLY_REREAD_COCKROACH$")


@dataclass(frozen=True, slots=True)
class ConsumedBundleHint:
    product_id: str
    organizations_checked: int
    invalidated_decision_ids: tuple[str, ...]
    replacement_attempt_ids: tuple[str, ...]


@dataclass(slots=True)
class ChangefeedHintConsumer:
    client: SqsHintClient = field(repr=False)
    queue_url: str
    database: Database = field(repr=False)
    organization_ids: Sequence[str]
    wait_time_seconds: int = 20
    visibility_timeout_seconds: int = 300

    async def poll_once(self) -> int:
        response = await asyncio.to_thread(
            self.client.receive_message,
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=self.wait_time_seconds,
            VisibilityTimeout=self.visibility_timeout_seconds,
            MessageAttributeNames=["All"],
            AttributeNames=["All"],
        )
        messages = response.get("Messages", [])
        if not isinstance(messages, list):
            raise RuntimeError("SQS receive response contained an invalid message collection")
        processed = 0
        for raw_message in messages:
            if not isinstance(raw_message, Mapping):
                raise RuntimeError("SQS returned an invalid message")
            receipt_handle = str(raw_message.get("ReceiptHandle", ""))
            if not receipt_handle:
                raise RuntimeError("SQS message omitted its receipt handle")
            await self.process(raw_message)
            await asyncio.to_thread(
                self.client.delete_message,
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle,
            )
            processed += 1
        return processed

    async def process(self, raw_message: Mapping[str, Any]) -> ConsumedBundleHint:
        try:
            document = json.loads(str(raw_message.get("Body", "")))
        except json.JSONDecodeError as error:
            raise ValueError("changefeed hint body is not valid JSON") from error
        hint = ProductBundleChangedHint.model_validate(document)
        organization_ids = tuple(
            sorted(set(self.organization_ids) | set(await self.database.organization_ids()))
        )
        invalidated: list[str] = []
        replacements: list[str] = []
        for organization_id in organization_ids:

            async def apply(
                session: Any, scoped_organization_id: str = organization_id
            ) -> BundleInvalidationResult:
                return await QualificationRepository(
                    session, scoped_organization_id
                ).invalidate_decisions_for_active_bundle(product_id=hint.aggregate_id)

            result = await self.database.run_retryable(organization_id, apply)
            invalidated.extend(result.invalidated_decision_ids)
            replacements.extend(result.replacement_attempt_ids)
        return ConsumedBundleHint(
            product_id=hint.aggregate_id,
            organizations_checked=len(organization_ids),
            invalidated_decision_ids=tuple(invalidated),
            replacement_attempt_ids=tuple(replacements),
        )
