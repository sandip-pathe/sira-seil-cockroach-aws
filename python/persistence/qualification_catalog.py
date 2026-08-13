"""Published marketplace vector retrieval with relational current-version gates."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_CATEGORY = re.compile(r"[a-z0-9][a-z0-9_-]{1,78}[a-z0-9]\Z")
_VISIBILITIES = frozenset({"BUYER_SAFE", "PUBLIC"})


@dataclass(frozen=True, slots=True)
class VectorCandidate:
    organization_id: str
    product_id: str
    bundle_id: str
    bundle_digest: str
    embedding_id: str
    content_hash: str
    model_id: str
    cosine_distance: float


async def search_published_candidates(
    session: AsyncSession,
    *,
    category: str,
    visibility: str,
    query_vector: tuple[float, ...],
    limit: int = 10,
) -> tuple[VectorCandidate, ...]:
    """DVI proposes candidates; active bundle joins decide which rows are eligible."""

    vector_literal = _vector_literal(query_vector)
    if not _CATEGORY.fullmatch(category):
        raise ValueError("catalog category is invalid")
    if visibility not in _VISIBILITIES:
        raise ValueError("catalog visibility is invalid")
    if limit < 1 or limit > 50:
        raise ValueError("catalog result limit must be between 1 and 50")
    distance = f"e.embedding <=> '{vector_literal}'::VECTOR"
    result = await session.execute(
        text(
            "SELECT e.organization_id, e.product_id, e.bundle_id, "
            "a.bundle_digest, e.id AS embedding_id, e.content_hash, e.model_id, "
            f"{distance} AS cosine_distance "
            "FROM qualification_product_embeddings AS e "
            "JOIN qualification_active_product_bundles AS a "
            "ON a.organization_id = e.organization_id "
            "AND a.product_id = e.product_id AND a.bundle_id = e.bundle_id "
            "WHERE e.category = :category AND e.visibility = :visibility "
            f"ORDER BY {distance} LIMIT :limit"
        ),
        {
            "category": category,
            "visibility": visibility,
            "limit": limit,
        },
    )
    return tuple(
        VectorCandidate(
            organization_id=str(row.organization_id),
            product_id=str(row.product_id),
            bundle_id=str(row.bundle_id),
            bundle_digest=str(row.bundle_digest),
            embedding_id=str(row.embedding_id),
            content_hash=str(row.content_hash),
            model_id=str(row.model_id),
            cosine_distance=float(row.cosine_distance),
        )
        for row in result
    )


async def explain_published_candidate_search(
    session: AsyncSession,
    *,
    category: str,
    visibility: str,
    query_vector: tuple[float, ...],
    limit: int = 10,
) -> tuple[str, ...]:
    """Return a credential-free plan proving the DVI path used by the application."""

    vector_literal = _vector_literal(query_vector)
    if not _CATEGORY.fullmatch(category) or visibility not in _VISIBILITIES:
        raise ValueError("catalog search scope is invalid")
    if limit < 1 or limit > 50:
        raise ValueError("catalog result limit must be between 1 and 50")
    distance = f"e.embedding <=> '{vector_literal}'::VECTOR"
    rows = await session.execute(
        text(
            "EXPLAIN SELECT e.id FROM qualification_product_embeddings AS e "
            "WHERE e.category = :category AND e.visibility = :visibility "
            f"ORDER BY {distance} LIMIT :limit"
        ),
        {
            "category": category,
            "visibility": visibility,
            "limit": limit,
        },
    )
    return tuple(str(row[0]) for row in rows)


def _vector_literal(vector: tuple[float, ...]) -> str:
    if len(vector) != 1024:
        raise ValueError("catalog query vector must have 1024 dimensions")
    if not all(math.isfinite(value) for value in vector):
        raise ValueError("catalog query vector contains a non-finite value")
    return "[" + ",".join(format(value, ".9g") for value in vector) + "]"
