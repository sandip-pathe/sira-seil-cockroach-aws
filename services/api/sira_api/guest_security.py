"""Signed guest sessions and bounded in-process API abuse controls."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass
from secrets import token_hex


_SESSION_ID = re.compile(r"^[0-9a-f]{32}$")


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


@dataclass(frozen=True, slots=True)
class GuestSession:
    session_id: str
    issued_at: int
    expires_at: int

    @property
    def organization_id(self) -> str:
        digest = hashlib.sha256(f"organization:{self.session_id}".encode()).hexdigest()
        return f"org_guest_{digest[:24]}"

    def actor_id(self, mode: str) -> str:
        digest = hashlib.sha256(f"actor:{mode}:{self.session_id}".encode()).hexdigest()
        return f"gst_{mode}_{digest[:24]}"


class GuestSessionSigner:
    def __init__(self, secret: str, *, ttl_seconds: int) -> None:
        if len(secret.encode("utf-8")) < 32:
            raise ValueError("guest session signing key must contain at least 32 bytes")
        self._secret = secret.encode("utf-8")
        self.ttl_seconds = ttl_seconds

    def issue(self, *, now: int | None = None) -> tuple[GuestSession, str]:
        issued_at = int(time.time() if now is None else now)
        session = GuestSession(
            session_id=token_hex(16),
            issued_at=issued_at,
            expires_at=issued_at + self.ttl_seconds,
        )
        return session, self._serialize(session)

    def verify(self, token: str, *, now: int | None = None) -> GuestSession | None:
        try:
            payload_part, signature_part = token.split(".", 1)
            expected = hmac.new(
                self._secret, payload_part.encode("ascii"), hashlib.sha256
            ).digest()
            supplied = _decode(signature_part)
            if not hmac.compare_digest(expected, supplied):
                return None
            payload = json.loads(_decode(payload_part))
            if set(payload) != {"sid", "iat", "exp", "v"} or payload["v"] != 1:
                return None
            session = GuestSession(
                session_id=str(payload["sid"]),
                issued_at=int(payload["iat"]),
                expires_at=int(payload["exp"]),
            )
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            return None
        current = int(time.time() if now is None else now)
        if not _SESSION_ID.fullmatch(session.session_id):
            return None
        if session.issued_at > current + 60 or session.expires_at <= current:
            return None
        if session.expires_at - session.issued_at != self.ttl_seconds:
            return None
        return session

    def _serialize(self, session: GuestSession) -> str:
        payload = _encode(
            json.dumps(
                {
                    "sid": session.session_id,
                    "iat": session.issued_at,
                    "exp": session.expires_at,
                    "v": 1,
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        )
        signature = hmac.new(self._secret, payload.encode("ascii"), hashlib.sha256).digest()
        return f"{payload}.{_encode(signature)}"


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    reset_at: int


class FixedWindowLimiter:
    """Small, lock-safe limiter for one API process.

    The key is a digest of the guest session or network address, so raw identifiers
    never enter logs or the limiter map.
    """

    def __init__(self) -> None:
        self._buckets: dict[tuple[str, str, int], int] = {}
        self._active: set[tuple[str, str]] = set()
        self._lock = asyncio.Lock()
        self._last_cleanup = 0

    async def check(
        self, *, subject: str, scope: str, limit: int, window_seconds: int
    ) -> RateLimitDecision:
        now = int(time.time())
        window = now // window_seconds
        key = (hashlib.sha256(subject.encode()).hexdigest(), scope, window)
        async with self._lock:
            if now - self._last_cleanup >= 60:
                self._buckets = {
                    item: count
                    for item, count in self._buckets.items()
                    if item[2] * self._window_for_scope(item[1]) > now - 86_400
                }
                self._last_cleanup = now
            count = self._buckets.get(key, 0)
            reset_at = (window + 1) * window_seconds
            if count >= limit:
                return RateLimitDecision(False, limit, 0, reset_at)
            count += 1
            self._buckets[key] = count
            return RateLimitDecision(True, limit, max(0, limit - count), reset_at)

    async def acquire(self, *, subject: str, scope: str) -> bool:
        key = (hashlib.sha256(subject.encode()).hexdigest(), scope)
        async with self._lock:
            if key in self._active:
                return False
            self._active.add(key)
            return True

    async def release(self, *, subject: str, scope: str) -> None:
        key = (hashlib.sha256(subject.encode()).hexdigest(), scope)
        async with self._lock:
            self._active.discard(key)

    @staticmethod
    def _window_for_scope(scope: str) -> int:
        if scope.endswith(":day"):
            return 86_400
        if scope.endswith(":hour") or scope == "guest-bootstrap":
            return 3_600
        return 60
