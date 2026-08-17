from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sira_agentcore import app as agentcore_app
from sira_agents.experiment import ExperimentResult
from sira_agents.kernel_models import (
    ContextManifest,
    Party,
    Principal,
    Respond,
    TurnDecisionEnvelope,
)
from sira_agents.runtime_ticket import RuntimeTicketCodec
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
    monkeypatch.setenv("AGENT_PRINCIPAL", "SIRA")
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

    assert isinstance(result, ExperimentResult)
    assert result.status == "COMPLETED"
    assert all(observation.value is True for observation in result.observations)
    assert result.artifact_hash.startswith("sha256:")


async def test_agentcore_evaluator_rejects_unknown_contract() -> None:
    with pytest.raises(ValidationError, match="unsupported"):
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


async def test_agentcore_cognitive_turn_is_principal_locked_and_replay_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = "agentcore-test-signing-key-32-bytes-minimum"
    monkeypatch.setenv("AGENT_PRINCIPAL", "SIRA")
    monkeypatch.setenv("AGENT_RUNTIME_AUDIENCE", "agentcore://sira")
    monkeypatch.setenv("RUNTIME_TICKET_SIGNING_KEY", key)
    agentcore_app._ticket_signing_key.cache_clear()
    manifest = ContextManifest(
        principal=Principal.SIRA,
        party=Party.BUYER,
        organization_id="org-buyer",
        actor_id="buyer-1",
        purpose="workspace_turn",
        conversation_id="conversation-1",
        turn_id="turn-1",
        current_message="Hello",
        available_tools=("search_products",),
    ).sealed()
    ticket = RuntimeTicketCodec(key.encode()).issue(
        principal=Principal.SIRA,
        party=Party.BUYER,
        organization_id="org-buyer",
        actor_id="buyer-1",
        purpose="workspace_turn",
        audience="agentcore://sira",
        allowed_tools=("search_products",),
    )

    class FakeRuntime:
        async def decide(self, supplied: ContextManifest) -> Respond:
            assert supplied == manifest
            return Respond(kind="respond", message="Hello. What outcome are you working toward?")

    monkeypatch.setattr(agentcore_app, "BedrockCognitiveRuntime", lambda _: FakeRuntime())
    request = agentcore_app.AgentCoreInvocationRequest(
        contract="sira.cognitive-turn.v1", ticket=ticket, manifest=manifest
    )
    response = await agentcore_app.invoke(request)
    assert isinstance(response, TurnDecisionEnvelope)
    assert response.decision.kind == "respond"
    with pytest.raises(HTTPException, match="RUNTIME_TICKET_REPLAYED"):
        await agentcore_app.invoke(request)
