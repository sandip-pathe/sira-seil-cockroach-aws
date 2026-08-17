from __future__ import annotations

import io
import json
from typing import Any

import pytest
from sira_agents.experiment import ExperimentSpec
from sira_agents.kernel_models import ContextManifest, Party, Principal
from sira_agents.runtime_ticket import RuntimeTicketCodec

from integrations.agentcore_runtime import (
    AgentCoreCognitiveRuntime,
    AgentCoreExperimentRunner,
    AgentCoreRuntimeError,
)


def _spec(*, max_output_bytes: int = 2_000_000) -> ExperimentSpec:
    return ExperimentSpec(
        candidate_id="product_fixture_a",
        fixture_id="qualification_case_v1",
        procedure=["Evaluate the labelled product bundle"],
        environment={"locale": "en-US"},
        success_signals=[
            {
                "name": "grounded",
                "measurement": "Every conclusion cites fixture evidence",
                "success_threshold": "true",
            }
        ],
        replay_command=["evaluate", "qualification_case_v1"],
        max_output_bytes=max_output_bytes,
    )


class FakeAgentCoreClient:
    def __init__(self, document: object) -> None:
        self.document = document
        self.calls: list[dict[str, Any]] = []

    def invoke_agent_runtime(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"response": io.BytesIO(json.dumps(self.document).encode("utf-8"))}


async def test_agentcore_runner_sends_bounded_contract_and_hashes_result() -> None:
    client = FakeAgentCoreClient(
        {
            "status": "COMPLETED",
            "observations": [{"signal": "grounded", "value": True, "source": "fixture:case-v1"}],
            "limitations": ["synthetic fixture"],
            "logs_reference": "cloudwatch:trace-1",
        }
    )
    runner = AgentCoreExperimentRunner(
        client=client,
        runtime_arn="arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/evaluator",
    )

    result = await runner.run(_spec())

    assert result.status == "COMPLETED"
    assert result.artifact_hash.startswith("sha256:")
    request = json.loads(client.calls[0]["payload"])
    assert request["contract"] == "sira.product-experiment.v1"
    assert client.calls[0]["runtimeSessionId"].startswith("sira-experiment-")
    assert "artifact_hash" not in request


async def test_agentcore_runner_rejects_invalid_result_contract() -> None:
    runner = AgentCoreExperimentRunner(
        client=FakeAgentCoreClient({"status": "MAYBE"}),
        runtime_arn="arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/evaluator",
    )

    with pytest.raises(AgentCoreRuntimeError, match="violated"):
        await runner.run(_spec())


async def test_agentcore_runner_enforces_output_budget() -> None:
    runner = AgentCoreExperimentRunner(
        client=FakeAgentCoreClient({"status": "COMPLETED", "limitations": ["x" * 2000]}),
        runtime_arn="arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/evaluator",
    )

    with pytest.raises(AgentCoreRuntimeError, match="output budget"):
        await runner.run(_spec(max_output_bytes=1024))


async def test_agentcore_cognitive_runtime_routes_by_principal_and_sends_signed_scope() -> None:
    client = FakeAgentCoreClient(
        {"decision": {"kind": "respond", "message": "Hello. What do you need?"}}
    )
    runtime = AgentCoreCognitiveRuntime(
        client=client,
        ticket_codec=RuntimeTicketCodec(b"agentcore-test-key-that-is-at-least-32-bytes"),
        runtime_arns={
            Principal.SIRA: "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/sira",
            Principal.SEIL: "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/seil",
        },
    )
    manifest = ContextManifest(
        principal=Principal.SEIL,
        party=Party.SELLER,
        organization_id="org-seller",
        actor_id="seller-1",
        purpose="workspace_turn",
        conversation_id="conversation-1",
        turn_id="turn-1",
        current_message="Hello",
        available_tools=("search_seller_products",),
    ).sealed()
    decision = await runtime.decide(manifest)
    assert decision.kind == "respond"
    call = client.calls[0]
    assert call["agentRuntimeArn"].endswith("/seil")
    request = json.loads(call["payload"])
    assert request["manifest"]["principal"] == "SEIL"
    assert request["ticket"].count(".") == 1
