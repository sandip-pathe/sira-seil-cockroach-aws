"""Persistence adapter for deterministic parsed evidence and stable spans."""

from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.evidence_pipeline import ParsedEvidence

from .qualification_models import EvidenceSourceVersion, EvidenceSpan
from .repositories import PersistenceConflict


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
