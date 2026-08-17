from __future__ import annotations

import pytest
from scripts.local_performance_check import percentile, summarize


def test_percentile_uses_nearest_rank_for_small_gate_samples() -> None:
    samples = [1.0, 2.0, 3.0, 4.0, 100.0]

    assert percentile(samples, 0.50) == 3.0
    assert percentile(samples, 0.95) == 100.0


def test_latency_summary_is_sanitized_and_stable() -> None:
    assert summarize([2.0, 1.0, 3.0]) == {
        "samples": 3,
        "min_ms": 1.0,
        "mean_ms": 2.0,
        "p50_ms": 2.0,
        "p95_ms": 3.0,
        "max_ms": 3.0,
    }


@pytest.mark.parametrize("quantile", [0.0, -0.1, 1.1])
def test_percentile_rejects_invalid_quantiles(quantile: float) -> None:
    with pytest.raises(ValueError, match="quantile"):
        percentile([1.0], quantile)
