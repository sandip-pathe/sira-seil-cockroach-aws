"""Opaque, signed browser-return state with no embedded business data."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets


class BrowserReturnStateSigner:
    """Issue and verify process-local opaque values; persist only their hashes."""

    _VERSION = "br1"

    def __init__(self, signing_key: str) -> None:
        key = signing_key.encode("utf-8")
        if len(key) < 32:
            raise ValueError("browser-return signing key must contain at least 32 bytes")
        self._key = key

    def issue(self) -> str:
        nonce = secrets.token_urlsafe(32)
        signed = f"{self._VERSION}.{nonce}"
        signature = hmac.new(self._key, signed.encode("ascii"), hashlib.sha256).digest()
        encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
        return f"{signed}.{encoded_signature}"

    def verify(self, state: str) -> bool:
        if len(state) > 256:
            return False
        parts = state.split(".")
        if len(parts) != 3 or parts[0] != self._VERSION or not parts[1] or not parts[2]:
            return False
        signed = f"{parts[0]}.{parts[1]}"
        expected = hmac.new(self._key, signed.encode("ascii"), hashlib.sha256).digest()
        expected_signature = base64.urlsafe_b64encode(expected).rstrip(b"=")
        try:
            supplied_signature = parts[2].encode("ascii")
        except UnicodeEncodeError:
            return False
        # Compare the canonical encoded representation. Permissive base64 decoders
        # otherwise accept multiple final characters for the same digest bits.
        return hmac.compare_digest(supplied_signature, expected_signature)

    @staticmethod
    def digest(value: str) -> str:
        return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"
