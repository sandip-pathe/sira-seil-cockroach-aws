from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from domain.evidence_pipeline import deterministic_embedding
from persistence.evidence_repository import search_published_spans


@dataclass
class FakeSession:
    statements: list[str] = field(default_factory=list)
    parameters: list[dict[str, object]] = field(default_factory=list)

    async def execute(self, statement: Any, parameters: dict[str, object]) -> list[object]:
        self.statements.append(str(statement))
        self.parameters.append(parameters)
        return []


async def test_evidence_search_relationally_gates_before_vector_order() -> None:
    session = FakeSession()
    result = await search_published_spans(
        session,  # type: ignore[arg-type]
        product_ids=("product-1", "product-2"),
        source_version_ids=("source-v2",),
        query_vector=deterministic_embedding("EU residency"),
    )
    assert result == ()
    statement = session.statements[0]
    assert "visibility IN ('BUYER_SAFE','PUBLIC')" in statement
    assert "product_id IN (:product_0,:product_1)" in statement
    assert "source_version_id IN (:source_0)" in statement
    assert statement.index("WHERE") < statement.index("ORDER BY")
    assert "<=>" in statement


async def test_evidence_search_fails_closed_on_empty_or_invalid_scope() -> None:
    session = FakeSession()
    assert (
        await search_published_spans(
            session,  # type: ignore[arg-type]
            product_ids=(),
            source_version_ids=("source-v1",),
            query_vector=deterministic_embedding("query"),
        )
        == ()
    )
    with pytest.raises(ValueError, match="invalid identifier"):
        await search_published_spans(
            session,  # type: ignore[arg-type]
            product_ids=("../other-tenant",),
            source_version_ids=("source-v1",),
            query_vector=deterministic_embedding("query"),
        )
