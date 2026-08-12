"""Payload guardrails for all model-bound SIRA/SEIL data."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


class AgentBoundaryViolation(ValueError):
    """Raised before data that violates an agent boundary reaches a model."""


_SECRET_KEY_PARTS = frozenset(
    {
        "api_key",
        "authorization",
        "card_number",
        "client_secret",
        "credential",
        "cvv",
        "cvc",
        "one_time_password",
        "pan",
        "password",
        "private_key",
        "secret",
        "security_code",
        "token",
    }
)

_SELLER_DENIED_KEY_PARTS = frozenset(
    {
        "buyer_passport",
        "buyer_private",
        "company_private",
        "hidden_budget",
        "identity_graph",
        "internal_budget",
        "private_context",
        "private_notes",
    }
)

_SECRET_VALUE_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bprava_[A-Za-z0-9_-]{16,}\b", re.IGNORECASE),
    re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
)


def _normalized_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def _key_is_denied(key: object, denied_parts: frozenset[str]) -> bool:
    normalized = _normalized_key(key)
    return any(part in normalized for part in denied_parts)


def _walk(value: object, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], object]]:
    items: list[tuple[tuple[str, ...], object]] = [(path, value)]
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = (*path, str(key))
            items.extend(_walk(child, child_path))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            items.extend(_walk(child, (*path, str(index))))
    return items


def validate_agent_payload(payload: Mapping[str, Any], *, seller_visible: bool) -> None:
    """Reject credentials/card data and buyer-private fields at the model boundary."""

    for path, value in _walk(payload):
        if path:
            key = path[-1]
            if _key_is_denied(key, _SECRET_KEY_PARTS):
                raise AgentBoundaryViolation(
                    f"model payload contains forbidden secret field at {'.'.join(path)}"
                )
            if seller_visible and _key_is_denied(key, _SELLER_DENIED_KEY_PARTS):
                raise AgentBoundaryViolation(
                    f"seller-visible payload contains buyer-private field at {'.'.join(path)}"
                )
        if isinstance(value, str) and any(
            pattern.search(value) for pattern in _SECRET_VALUE_PATTERNS
        ):
            location = ".".join(path) or "<root>"
            raise AgentBoundaryViolation(
                f"model payload contains a credential or payment-card-like value at {location}"
            )
