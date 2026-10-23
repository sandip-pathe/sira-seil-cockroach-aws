"""Validated durable outbox event processing for qualification work."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from hashlib import sha256

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.database import Database
from persistence.qualification_models import (
    ConsumerReceipt,
    QualificationDecision,
    QualificationMission,
)
from sira_worker.qualification import QualificationWorker

logger = logging.getLogger(__name__)


class QualificationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission_id: str = Field(pattern=r"^qmission_[a-f0-9]{32}$")
    trace_id: str = Field(min_length=1, max_length=128)
    organization_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,48}$")
    reason: str | None = Field(default=None, pattern=r"^ACTIVE_PRODUCT_BUNDLE_CHANGED$")
    product_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")
    replacement_attempt_id: str | None = Field(default=None, pattern=r"^qattempt_[a-f0-9]{32}$")

    @model_validator(mode="after")
    def replacement_metadata_is_complete(self) -> QualificationPayload:
        values = (self.reason, self.product_id, self.replacement_attempt_id)
        if any(value is not None for value in values) and not all(
            value is not None for value in values
        ):
            raise ValueError("bundle replacement metadata must be complete")
        return self


class QualificationEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(ge=1, le=1)
    message_id: str = Field(min_length=1, max_length=64)
    organization_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,48}$")
    aggregate_type: str = Field(pattern=r"^QUALIFICATION_MISSION$")
    aggregate_id: str = Field(pattern=r"^qmission_[a-f0-9]{32}$")
    event_type: str = Field(pattern=r"^QUALIFICATION_MISSION_READY$")
    event_key: str = Field(min_length=1, max_length=255)
    payload: QualificationPayload
    occurred_at: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def consistent_scope(self) -> QualificationEnvelope:
        if self.organization_id != self.payload.organization_id:
            raise ValueError("event organization scope is inconsistent")
        if self.aggregate_id != self.payload.mission_id:
            raise ValueError("event mission identity is inconsistent")
        base_key = f"qualification-mission-ready:{self.aggregate_id}"
        if self.event_key != base_key and not self.event_key.startswith(f"{base_key}:bundle:"):
            raise ValueError("event key is inconsistent")
        return self


@dataclass(frozen=True, slots=True)
class ConsumedQualification:
    message_id: str
    mission_id: str
    result_ref: str
    replayed: bool


@dataclass(slots=True)
class QualificationEventProcessor:
    """Validate a qualification event and record Cockroach-backed deduplication."""

    database: Database = field(repr=False)
    worker: QualificationWorker = field(repr=False)

    async def process_body(
        self, body: str, *, expected_digest: str | None = None
    ) -> ConsumedQualification:
        """Process a durable outbox body independently of its transport."""

        body_digest = sha256(body.encode("utf-8")).hexdigest()
        if expected_digest is not None and expected_digest != body_digest:
            raise ValueError("qualification body digest does not match its envelope")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as error:
            raise ValueError("qualification event body is not valid JSON") from error
        envelope = QualificationEnvelope.model_validate(parsed)

        existing = await self._receipt(envelope)
        if existing is not None:
            if existing.payload_hash != f"sha256:{body_digest}":
                raise ValueError("replayed message identity has a different payload hash")
            return ConsumedQualification(
                envelope.message_id,
                envelope.aggregate_id,
                existing.result_ref,
                True,
            )

        terminal_ref = await self._completed_result(envelope)
        if terminal_ref is None:
            result = await self.worker.run_mission(
                organization_id=envelope.organization_id,
                mission_id=envelope.aggregate_id,
            )
            if result.state != "COMPLETED" or result.decision_id is None:
                raise RuntimeError("qualification worker returned no durable decision")
            terminal_ref = result.decision_id

        await self._record_receipt(envelope, body_digest, terminal_ref)
        return ConsumedQualification(
            envelope.message_id,
            envelope.aggregate_id,
            terminal_ref,
            False,
        )

    async def _receipt(self, envelope: QualificationEnvelope) -> ConsumerReceipt | None:
        async with self.database.transaction(envelope.organization_id) as session:
            receipt: ConsumerReceipt | None = await session.scalar(
                select(ConsumerReceipt).where(
                    ConsumerReceipt.organization_id == envelope.organization_id,
                    ConsumerReceipt.consumer_name == "qualification-worker-v1",
                    ConsumerReceipt.message_id == envelope.message_id,
                )
            )
            return receipt

    async def _completed_result(self, envelope: QualificationEnvelope) -> str | None:
        async with self.database.transaction(envelope.organization_id) as session:
            mission = await session.scalar(
                select(QualificationMission).where(
                    QualificationMission.organization_id == envelope.organization_id,
                    QualificationMission.id == envelope.aggregate_id,
                )
            )
            if mission is None:
                raise ValueError("qualification mission does not exist")
            if mission.state != "COMPLETED":
                return None
            decision_ref: str | None = await session.scalar(
                select(QualificationDecision.id).where(
                    QualificationDecision.organization_id == envelope.organization_id,
                    QualificationDecision.mission_id == envelope.aggregate_id,
                    QualificationDecision.current.is_(True),
                )
            )
            return decision_ref

    async def _record_receipt(
        self,
        envelope: QualificationEnvelope,
        body_digest: str,
        result_ref: str,
    ) -> None:
        async def write(session: AsyncSession) -> None:
            existing = await session.scalar(
                select(ConsumerReceipt).where(
                    ConsumerReceipt.organization_id == envelope.organization_id,
                    ConsumerReceipt.consumer_name == "qualification-worker-v1",
                    ConsumerReceipt.message_id == envelope.message_id,
                )
            )
            if existing is not None:
                if existing.payload_hash != f"sha256:{body_digest}":
                    raise ValueError("replayed message identity has a different payload hash")
                return
            session.add(
                ConsumerReceipt(
                    id=f"qreceipt_{sha256(envelope.message_id.encode()).hexdigest()[:32]}",
                    consumer_name="qualification-worker-v1",
                    message_id=envelope.message_id,
                    payload_hash=f"sha256:{body_digest}",
                    result_ref=result_ref,
                    organization_id=envelope.organization_id,
                )
            )

        await self.database.run_retryable(envelope.organization_id, write)
