"""Deterministic evidence parsing, stable spans, validation, and local retrieval."""

from __future__ import annotations

import math
import re
from hashlib import sha256
from typing import Any

import rfc8785
from pydantic import BaseModel, ConfigDict, Field, model_validator

_ALLOWED_CONTENT_TYPES = frozenset({"text/plain", "text/markdown", "application/json", "text/csv"})
_INSTRUCTION_MARKERS = (
    "ignore previous",
    "system prompt",
    "call this tool",
    "reveal secret",
    "change your role",
)


class EvidenceValidationError(ValueError):
    """Evidence bytes or a proposed claim failed deterministic validation."""


class EvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class StableSpan(EvidenceModel):
    id: str
    source_version_id: str
    sequence: int = Field(ge=1)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=2_000)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    untrusted_instruction_markers: tuple[str, ...] = ()
    embedding: tuple[float, ...] = Field(min_length=1024, max_length=1024)

    @model_validator(mode="after")
    def validate_offsets(self) -> StableSpan:
        if self.end <= self.start:
            raise ValueError("span end must follow its start")
        return self


class ParsedEvidence(EvidenceModel):
    source_version_id: str
    object_checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    content_type: str
    text: str
    text_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    spans: tuple[StableSpan, ...]


class ClaimProposal(EvidenceModel):
    field: str = Field(min_length=1, max_length=120)
    operator: str = Field(min_length=1, max_length=24)
    value: Any
    span_id: str = Field(min_length=1, max_length=100)
    supporting_text: str = Field(min_length=1, max_length=2_000)


class ValidatedClaim(EvidenceModel):
    field: str
    operator: str
    value: Any
    source_version_id: str
    span_id: str
    supporting_text: str
    provenance_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class RetrievalHit(EvidenceModel):
    span_id: str
    score: float
    text: str
    content_hash: str


def deterministic_embedding(text: str, *, dimensions: int = 1024) -> tuple[float, ...]:
    if dimensions != 1024:
        raise ValueError("local evidence embeddings are pinned to 1024 dimensions")
    seed = text.strip().casefold().encode("utf-8")
    if not seed:
        raise ValueError("embedding text must not be empty")
    values: list[float] = []
    counter = 0
    while len(values) < dimensions:
        block = sha256(seed + counter.to_bytes(4, "big")).digest()
        values.extend((byte - 127.5) / 127.5 for byte in block)
        counter += 1
    vector = values[:dimensions]
    norm = math.sqrt(sum(value * value for value in vector))
    return tuple(value / norm for value in vector)


def parse_evidence(
    *, source_version_id: str, body: bytes, content_type: str, max_span_chars: int = 800
) -> ParsedEvidence:
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise EvidenceValidationError("evidence content type requires a configured parser")
    if not body:
        raise EvidenceValidationError("evidence object must not be empty")
    if len(body) > 25 * 1024 * 1024:
        raise EvidenceValidationError("evidence object exceeds the ingestion limit")
    try:
        text = body.decode("utf-8", errors="strict").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeDecodeError as error:
        raise EvidenceValidationError("text evidence must be valid UTF-8") from error
    if "\x00" in text:
        raise EvidenceValidationError("evidence contains a NUL byte")
    checksum = f"sha256:{sha256(body).hexdigest()}"
    text_hash = f"sha256:{sha256(text.encode()).hexdigest()}"
    spans: list[StableSpan] = []
    for match in re.finditer(r"\S(?:.*?\S)?(?=\n\s*\n|\s*\Z)", text, flags=re.DOTALL):
        paragraph = match.group(0)
        paragraph_start = match.start()
        offset = 0
        while offset < len(paragraph):
            end = min(len(paragraph), offset + max_span_chars)
            if end < len(paragraph):
                boundary = paragraph.rfind(" ", offset, end)
                if boundary > offset:
                    end = boundary
            chunk = paragraph[offset:end].strip()
            if chunk:
                local_start = paragraph.find(chunk, offset, end + 1)
                start = paragraph_start + local_start
                absolute_end = start + len(chunk)
                digest = sha256(
                    f"{source_version_id}:{start}:{absolute_end}:{chunk}".encode()
                ).hexdigest()
                markers = tuple(
                    marker for marker in _INSTRUCTION_MARKERS if marker in chunk.casefold()
                )
                spans.append(
                    StableSpan(
                        id=f"span_{digest[:24]}",
                        source_version_id=source_version_id,
                        sequence=len(spans) + 1,
                        start=start,
                        end=absolute_end,
                        text=chunk,
                        content_hash=f"sha256:{sha256(chunk.encode()).hexdigest()}",
                        untrusted_instruction_markers=markers,
                        embedding=deterministic_embedding(chunk),
                    )
                )
            offset = max(end, offset + 1)
    if not spans:
        raise EvidenceValidationError("evidence contains no parseable text")
    return ParsedEvidence(
        source_version_id=source_version_id,
        object_checksum=checksum,
        content_type=content_type,
        text=text,
        text_hash=text_hash,
        spans=tuple(spans),
    )


def validate_claim_proposals(
    evidence: ParsedEvidence, proposals: tuple[ClaimProposal, ...]
) -> tuple[ValidatedClaim, ...]:
    spans = {span.id: span for span in evidence.spans}
    validated: list[ValidatedClaim] = []
    for proposal in proposals:
        span = spans.get(proposal.span_id)
        if span is None or proposal.supporting_text not in span.text:
            raise EvidenceValidationError("claim support does not resolve to its pinned span")
        payload = {
            "field": proposal.field,
            "operator": proposal.operator,
            "value": proposal.value,
            "source_version_id": evidence.source_version_id,
            "span_id": span.id,
            "supporting_text": proposal.supporting_text,
            "span_hash": span.content_hash,
        }
        validated.append(
            ValidatedClaim(
                **{key: value for key, value in payload.items() if key != "span_hash"},
                provenance_hash=f"sha256:{sha256(rfc8785.dumps(payload)).hexdigest()}",
            )
        )
    return tuple(validated)


def retrieve_evidence(
    *,
    query: str,
    spans: tuple[StableSpan, ...],
    allowed_source_version_ids: frozenset[str],
    limit: int = 5,
) -> tuple[RetrievalHit, ...]:
    if limit < 1 or limit > 20:
        raise ValueError("retrieval limit must be between 1 and 20")
    query_terms = frozenset(re.findall(r"[a-z0-9]+", query.casefold()))
    query_vector = deterministic_embedding(query)
    candidates = [span for span in spans if span.source_version_id in allowed_source_version_ids]
    scored: list[tuple[float, StableSpan]] = []
    for span in candidates:
        span_terms = frozenset(re.findall(r"[a-z0-9]+", span.text.casefold()))
        lexical = len(query_terms.intersection(span_terms)) / max(1, len(query_terms))
        semantic = sum(a * b for a, b in zip(query_vector, span.embedding, strict=True))
        score = 0.7 * lexical + 0.3 * max(0.0, semantic)
        scored.append((score, span))
    scored.sort(key=lambda item: (-item[0], item[1].source_version_id, item[1].sequence))
    return tuple(
        RetrievalHit(
            span_id=span.id,
            score=round(score, 8),
            text=span.text,
            content_hash=span.content_hash,
        )
        for score, span in scored[:limit]
    )
