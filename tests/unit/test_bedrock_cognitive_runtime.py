from __future__ import annotations

from dataclasses import dataclass, field

from sira_agents.cognitive_runtime import BedrockCognitiveRuntime
from sira_agents.kernel_models import Clarify, ContextManifest
from sira_agents.runtime import AgentRunRequest, AgentRunResult


@dataclass
class StructuredRuntimeDouble:
    requests: list[AgentRunRequest] = field(default_factory=list)

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        self.requests.append(request)
        return AgentRunResult(
            output={
                "decision": {
                    "kind": "clarify",
                    "question": "Must recordings stay in the EU?",
                    "reason": "Residency can change eligibility.",
                }
            },
            runtime="aws-bedrock-converse",
        )


async def test_bedrock_cognitive_adapter_preserves_kernel_authority_boundary() -> None:
    provider = StructuredRuntimeDouble()
    runtime = BedrockCognitiveRuntime(provider)
    manifest = ContextManifest(
        principal="SIRA",
        party="BUYER",
        organization_id="org-private",
        actor_id="actor-private",
        purpose="software_selection",
        conversation_id="conversation-1",
        turn_id="turn-1",
        current_message="Help us choose.",
        available_tools=("read_evidence",),
    ).sealed()

    decision = await runtime.decide(manifest)

    assert decision == Clarify(
        kind="clarify",
        question="Must recordings stay in the EU?",
        reason="Residency can change eligibility.",
    )
    request = provider.requests[0]
    assert request.allowed_tools == ()
    assert request.output_type is not None
    assert request.model_context["context_hash"] == manifest.manifest_hash
    assert "organization_id" not in request.model_context
    assert "actor_id" not in request.model_context
