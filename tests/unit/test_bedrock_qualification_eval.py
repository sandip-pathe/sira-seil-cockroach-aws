from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from sira_worker.bedrock_qualification_eval import (
    BedrockQualificationEvalCase,
    build_bedrock_qualification_report,
    evaluate_bedrock_qualification,
)


@dataclass
class FakeBedrock:
    product: str = "product-a"
    calls: list[dict[str, Any]] = field(default_factory=list)
    turn: int = 0

    def converse(self, **kwargs: Any) -> Mapping[str, Any]:
        self.calls.append(deepcopy(kwargs))
        candidates = ("product-a", "product-b")
        if self.turn == 0:
            self.turn += 1
            return {
                "stopReason": "tool_use",
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "toolUse": {
                                    "toolUseId": f"tool-{index}",
                                    "name": "retrieve_product_evidence",
                                    "input": {"product_id": product},
                                }
                            }
                            for index, product in enumerate(candidates)
                        ],
                    }
                },
                "usage": {"inputTokens": 20, "outputTokens": 5},
            }
        self.turn += 1
        decision = {
            "recommended_product_id": self.product,
            "summary": "The selected product satisfies the mandatory requirement.",
            "cited_dependency_ids": ["evidence-a", "evidence-b"],
            "criteria": [
                {
                    "criterion": "Mandatory requirement",
                    "result": "PASS",
                    "rationale": "The pinned evidence supports the selected product.",
                    "cited_dependency_ids": ["evidence-a"],
                }
            ],
            "confidence": "0.9000",
        }
        return {
            "stopReason": "end_turn",
            "output": {
                "message": {"role": "assistant", "content": [{"text": json.dumps(decision)}]}
            },
            "usage": {"inputTokens": 100, "outputTokens": 40, "totalTokens": 140},
        }

    def invoke_model(self, **_kwargs: Any) -> Mapping[str, Any]:
        raise AssertionError("qualification evaluation must not invoke embeddings")


def _case() -> BedrockQualificationEvalCase:
    return BedrockQualificationEvalCase.model_validate(
        {
            "id": "mandatory-gate",
            "requirement": "Choose a product with EU hosting.",
            "policy": "EU hosting is mandatory.",
            "expected_product_id": "product-a",
            "evidence_by_product": {
                "product-a": [
                    {"dependency_id": "evidence-a", "claim": "EU hosting is available."}
                ],
                "product-b": [
                    {"dependency_id": "evidence-b", "claim": "US hosting only."}
                ],
            },
        }
    )


async def test_live_eval_runs_production_style_tool_and_grounding_gates() -> None:
    client = FakeBedrock()
    results = await evaluate_bedrock_qualification(
        client=client,
        model_id="test-model",
        cases=(_case(),),
    )

    result = results[0]
    assert result.structured_output_valid is True
    assert result.inspected_every_candidate is True
    assert result.grounded is True
    assert result.expected_product_match is True
    assert result.input_tokens == 100
    assert result.output_tokens == 40
    assert result.input_sha256.startswith("sha256:")
    assert result.output_sha256 is not None
    assert len(client.calls) == 2
    assert client.calls[0]["inferenceConfig"]["temperature"] == 0


async def test_live_eval_scores_a_grounded_but_incorrect_choice_separately() -> None:
    client = FakeBedrock(product="product-b")
    results = await evaluate_bedrock_qualification(
        client=client,
        model_id="test-model",
        cases=(_case(),),
    )

    result = results[0]
    assert result.structured_output_valid is True
    assert result.grounded is True
    assert result.expected_product_match is False
    assert result.failure_category is None


async def test_report_persists_only_metrics_ids_and_hashes() -> None:
    results = await evaluate_bedrock_qualification(
        client=FakeBedrock(),
        model_id="test-model",
        cases=(_case(),),
    )
    report = build_bedrock_qualification_report(
        model_id="test-model",
        region="test-region",
        results=results,
    )
    serialized = json.dumps(report)

    assert report["status"] == "PASS"
    assert report["metrics"] == {
        "structured_output_rate": 1.0,
        "all_candidates_inspected_rate": 1.0,
        "grounded_output_rate": 1.0,
        "expected_product_accuracy": 1.0,
    }
    assert "Choose a product" not in serialized
    assert "EU hosting is available" not in serialized
    assert "selected product satisfies" not in serialized
    assert report["data_handling"]["raw_model_output_persisted"] is False
