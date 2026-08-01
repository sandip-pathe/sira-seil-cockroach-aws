"""Canonical JSON and content hashing for immutable artifacts.

This implements the RFC 8785 properties needed by the product's constrained
JSON payloads: Unicode JSON, lexicographically sorted string keys, compact
encoding, canonical integral numbers, and deterministic typed conversions.
Binary floating point is rejected; commerce values must use Decimal/string.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from .errors import DomainValidationError


def _decimal_text(value: Decimal) -> str:
    if not value.is_finite():
        raise DomainValidationError("non-finite decimals are not canonical JSON")
    if value == 0:
        return "0"
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _datetime_text(value: datetime) -> str:
    if value.tzinfo is None:
        raise DomainValidationError("naive datetimes cannot enter canonical artifacts")
    utc_value = value.astimezone(UTC)
    rendered = utc_value.isoformat(timespec="microseconds")
    rendered = rendered.replace("+00:00", "Z")
    return rendered.replace(".000000Z", "Z")


def _normalize(value: Any, *, excluded_fields: frozenset[str]) -> Any:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, Enum):
        return _normalize(value.value, excluded_fields=excluded_fields)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return _datetime_text(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        # Product schemas represent exact decimal values as JSON strings.
        return _decimal_text(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DomainValidationError("non-finite floats are not canonical JSON")
        raise DomainValidationError(
            "binary floating point is prohibited in canonical artifacts; use Decimal"
        )
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        if hasattr(value, "to_hash_payload"):
            return _normalize(value.to_hash_payload(), excluded_fields=excluded_fields)
        return _normalize(
            {field.name: getattr(value, field.name) for field in dataclasses.fields(value)},
            excluded_fields=excluded_fields,
        )
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise DomainValidationError("canonical JSON object keys must be strings")
            if key in excluded_fields:
                continue
            normalized[key] = _normalize(item, excluded_fields=excluded_fields)
        return normalized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize(item, excluded_fields=excluded_fields) for item in value]
    raise DomainValidationError(f"unsupported canonical JSON value: {type(value).__name__}")


def canonical_json(
    value: Any,
    *,
    excluded_fields: Iterable[str] = (),
) -> str:
    """Return deterministic compact JSON for the supported artifact subset."""

    normalized = _normalize(value, excluded_fields=frozenset(excluded_fields))
    return json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def content_hash(
    value: Any,
    *,
    excluded_fields: Iterable[str] = (),
) -> str:
    payload = canonical_json(value, excluded_fields=excluded_fields).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"
