from __future__ import annotations

import json
from pathlib import Path

import yaml

from domain.evidence_pipeline import parse_evidence, retrieve_evidence

ROOT = Path(__file__).resolve().parents[2]


def test_retrieval_fixture_meets_frozen_recall_and_mrr_gates() -> None:
    fixture = json.loads((ROOT / "evaluations/retrieval.v1.json").read_text(encoding="utf-8"))
    thresholds = yaml.safe_load(
        (ROOT / "evaluations/thresholds.v1.yaml").read_text(encoding="utf-8")
    )["retrieval"]
    parsed = {
        item["source_version_id"]: parse_evidence(
            source_version_id=item["source_version_id"],
            body=item["text"].encode(),
            content_type="text/plain",
        )
        for item in fixture["documents"]
    }
    spans = tuple(span for document in parsed.values() for span in document.spans)
    allowed = frozenset(parsed)
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    source_by_span = {
        span.id: source_id for source_id, document in parsed.items() for span in document.spans
    }
    for case in fixture["queries"]:
        ranked_sources = [
            source_by_span[hit.span_id]
            for hit in retrieve_evidence(
                query=case["query"],
                spans=spans,
                allowed_source_version_ids=allowed,
                limit=5,
            )
        ]
        expected = set(case["expected_source_version_ids"])
        recalls.append(len(expected.intersection(ranked_sources)) / len(expected))
        reciprocal_ranks.append(
            next(
                (
                    1 / rank
                    for rank, source in enumerate(ranked_sources, start=1)
                    if source in expected
                ),
                0.0,
            )
        )
    recall_at_5 = sum(recalls) / len(recalls)
    mrr_at_5 = sum(reciprocal_ranks) / len(reciprocal_ranks)
    assert recall_at_5 >= thresholds["recall_at_5"]
    assert mrr_at_5 >= thresholds["mrr_at_5"]
