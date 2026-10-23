"""Transport-independent durable outbox envelope."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


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
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", self.organization_id):
            raise ValueError("outbox organization identity is invalid")
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
