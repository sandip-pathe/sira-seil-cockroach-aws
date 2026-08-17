"""Persistence adapter for deterministic parsed evidence and stable spans."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import cast

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from domain.evidence_pipeline import ParsedEvidence

from .qualification_models import EvidenceSourceVersion, EvidenceSpan
from .repositories import PersistenceConflict

_IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


@dataclass(frozen=True, slots=True)
class EvidenceSearchHit:
    span_id: str
    source_version_id: str
    product_id: str
    text: str
    content_hash: str
    cosine_distance: float


def _vector_literal(vector: tuple[float, ...]) -> str:
    if len(vector) != 1024 or not all(math.isfinite(value) for value in vector):
        raise ValueError("evidence vector must contain 1024 finite values")
    return "[" + ",".join(format(value, ".9g") for value in vector) + "]"


class EvidenceRepository:
    def __init__(self, session: AsyncSession, organization_id: str) -> None:
        self.session = session
        self.organization_id = organization_id

    async def store_parsed(
        self,
        *,
        product_id: str,
        object_bucket: str,
        object_key: str,
        object_version_id: str,
        size_bytes: int,
        parsed: ParsedEvidence,
        visibility: str = "PRIVATE",
        parser_version: str = "stable-text-v1",
        embedding_model_id: str = "local-deterministic-v1",
    ) -> EvidenceSourceVersion:
        existing = await self.session.scalar(
            select(EvidenceSourceVersion).where(
                EvidenceSourceVersion.organization_id == self.organization_id,
                EvidenceSourceVersion.product_id == product_id,
                EvidenceSourceVersion.object_checksum == parsed.object_checksum,
            )
        )
        if existing is not None:
            if existing.text_hash != parsed.text_hash:
                raise PersistenceConflict("evidence checksum is bound to another parsed text")
            return existing
        source = EvidenceSourceVersion(
            id=parsed.source_version_id,
            organization_id=self.organization_id,
            product_id=product_id,
            object_bucket=object_bucket,
            object_key=object_key,
            object_version_id=object_version_id,
            object_checksum=parsed.object_checksum,
            content_type=parsed.content_type,
            size_bytes=size_bytes,
            parser_version=parser_version,
            status="PARSED",
            text_hash=parsed.text_hash,
        )
        self.session.add(source)
        await self.session.flush()
        for span in parsed.spans:
            self.session.add(
                EvidenceSpan(
                    id=span.id,
                    organization_id=self.organization_id,
                    source_version_id=source.id,
                    product_id=product_id,
                    visibility=visibility,
                    sequence=span.sequence,
                    start_offset=span.start,
                    end_offset=span.end,
                    text_content=span.text,
                    content_hash=span.content_hash,
                    instruction_markers=list(span.untrusted_instruction_markers),
                    embedding_model_id=embedding_model_id,
                    embedding=_vector_literal(span.embedding),
                )
            )
            # Cockroach recommends individual VECTOR inserts instead of large batches.
            await self.session.flush()
        return source

    async def get_source_by_checksum(self, object_checksum: str) -> EvidenceSourceVersion | None:
        return cast(
            EvidenceSourceVersion | None,
            await self.session.scalar(
                select(EvidenceSourceVersion).where(
                    EvidenceSourceVersion.organization_id == self.organization_id,
                    EvidenceSourceVersion.object_checksum == object_checksum,
                )
            )
        )

    async def publish(self, source: EvidenceSourceVersion) -> None:
        if source.status not in {"PARSED", "VALIDATED", "PUBLISHED"}:
            raise PersistenceConflict("rejected evidence cannot be published")
        source.status = "PUBLISHED"
        spans = tuple(
            (
                await self.session.execute(
                    select(EvidenceSpan).where(
                        EvidenceSpan.organization_id == self.organization_id,
                        EvidenceSpan.source_version_id == source.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        for span in spans:
            span.visibility = "BUYER_SAFE"


async def search_published_spans(
    session: AsyncSession,
    *,
    product_ids: tuple[str, ...],
    source_version_ids: tuple[str, ...],
    query_vector: tuple[float, ...],
    limit: int = 5,
) -> tuple[EvidenceSearchHit, ...]:
    """Apply exact relational authorization gates before DVI nearest-neighbor order."""

    if not product_ids or not source_version_ids:
        return ()
    if len(product_ids) > 50 or len(source_version_ids) > 100:
        raise ValueError("evidence retrieval scope is too large")
    if any(not _IDENTIFIER.fullmatch(value) for value in (*product_ids, *source_version_ids)):
        raise ValueError("evidence retrieval scope contains an invalid identifier")
    if limit < 1 or limit > 20:
        raise ValueError("evidence retrieval limit must be between 1 and 20")
    vector = _vector_literal(query_vector)
    product_names = [f"product_{index}" for index in range(len(product_ids))]
    source_names = [f"source_{index}" for index in range(len(source_version_ids))]
    parameters: dict[str, object] = {"limit": limit}
    parameters.update(dict(zip(product_names, product_ids, strict=True)))
    parameters.update(dict(zip(source_names, source_version_ids, strict=True)))
    products_sql = ",".join(f":{name}" for name in product_names)
    sources_sql = ",".join(f":{name}" for name in source_names)
    distance = f"embedding <=> '{vector}'::VECTOR"
    rows = await session.execute(
        text(
            "SELECT id, source_version_id, product_id, text_content, content_hash, "
            f"{distance} AS cosine_distance FROM evidence_spans "
            "WHERE visibility IN ('BUYER_SAFE','PUBLIC') "
            f"AND product_id IN ({products_sql}) "
            f"AND source_version_id IN ({sources_sql}) "
            f"ORDER BY {distance}, source_version_id, sequence LIMIT :limit"
        ),
        parameters,
    )
    return tuple(
        EvidenceSearchHit(
            span_id=str(row.id),
            source_version_id=str(row.source_version_id),
            product_id=str(row.product_id),
            text=str(row.text_content),
            content_hash=str(row.content_hash),
            cosine_distance=float(row.cosine_distance),
        )
        for row in rows
    )
