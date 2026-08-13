from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException
from sira_agentcore import app as agentcore_app
from sira_worker.bedrock_qualification_eval import BedrockQualificationCaseResult


async def test_agentcore_evaluator_runs_committed_fixture_without_memory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    corpus = tmp_path / "cases.json"
    corpus.write_text(
        '{"cases":[{"id":"case-1","requirement":"EU",'
        '"policy":"grounded","expected_product_id":"product-a",'
        '"evidence_by_product":{"product-a":[{"dependency_id":"dep-a",'
        '"claim":"EU"}],"product-b":[{"dependency_id":"dep-b","claim":"US"}]}}]}',
        encoding="utf-8",
    )
    monkeypatch.setenv("SIRA_EXPERIMENT_CORPUS", str(corpus))
    monkeypatch.setattr(agentcore_app, "create_bedrock_client", lambda **_: object())

    async def evaluate(**_: Any) -> tuple[BedrockQualificationCaseResult, ...]:
        return (
            BedrockQualificationCaseResult(
                case_id="case-1",
                expected_product_id="product-a",
                actual_product_id="product-a",
                structured_output_valid=True,
                inspected_every_candidate=True,
                grounded=True,
                expected_product_match=True,
                output_sha256="sha256:out",
                input_sha256="sha256:in",
                failure_category=None,
                input_tokens=10,
                output_tokens=5,
            ),
        )

    monkeypatch.setattr(agentcore_app, "evaluate_bedrock_qualification", evaluate)
    result = await agentcore_app.invoke(
        agentcore_app.AgentCoreExperimentRequest.model_validate(
            {
                "contract": "sira.product-experiment.v1",
                "experiment": {
                    "candidate_id": "product-a",
                    "fixture_id": "case-1",
                    "procedure": ["run labelled evaluation"],
                    "environment": {},
                    "success_signals": [
                        {
                            "name": "grounded",
                            "measurement": "citations",
                            "success_threshold": "true",
                        }
                    ],
                    "replay_command": ["evaluate", "case-1"],
                },
            }
        )
    )

    assert result.status == "COMPLETED"
    assert all(observation.value is True for observation in result.observations)
    assert result.artifact_hash.startswith("sha256:")


async def test_agentcore_evaluator_rejects_unknown_contract() -> None:
    with pytest.raises(HTTPException, match="unsupported"):
        await agentcore_app.invoke(
            agentcore_app.AgentCoreExperimentRequest.model_validate(
                {
                    "contract": "other",
                    "experiment": {
                        "candidate_id": "product-a",
                        "fixture_id": "case-1",
                        "procedure": ["run"],
                        "environment": {},
                        "success_signals": [
                            {"name": "ok", "measurement": "observe", "success_threshold": "true"}
                        ],
                        "replay_command": ["evaluate", "case-1"],
                    },
                }
            )
        )
