"""Content-addressed evidence storage used by the API."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from secrets import token_urlsafe
from typing import Protocol

_ORGANIZATION_ID = re.compile(r"[A-Za-z0-9_-]{1,48}\Z")
MAX_EVIDENCE_BYTES = 25 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class StoredEvidenceObject:
    bucket: str
    key: str
    version_id: str
    sha256: str
    size_bytes: int
    content_type: str


class EvidenceStore(Protocol):
    async def put(
        self, *, organization_id: str, body: bytes, content_type: str
    ) -> StoredEvidenceObject: ...


@dataclass(slots=True)
class LocalContentAddressedEvidenceStore:
    """Store immutable evidence locally with an integrity-checked identity."""

    root: Path

    async def put(
        self, *, organization_id: str, body: bytes, content_type: str
    ) -> StoredEvidenceObject:
        if not _ORGANIZATION_ID.fullmatch(organization_id):
            raise ValueError("organization_id is invalid")
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
