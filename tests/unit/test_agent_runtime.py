from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from sira_agents.guardrails import AgentBoundaryViolation
from sira_agents.runtime import (
    AgentRole,
    AgentRunContext,
    AgentRunRequest,
    OpenAIAgentsRuntime,
)


@dataclass
class FakeSdk:
    calls: list[tuple[str, object]] = field(default_factory=list)

    def create_agent(
        self,
        *,
        name: str,
        instructions: str,
        model: str,
        tools: list[object],
        output_type: type[object] | None,
    ) -> object:
        agent = {
            "name": name,
            "instructions": instructions,
            "model": model,
            "tools": tools,
            "output_type": output_type,
        }
        self.calls.append(("create", agent))
        return agent

    async def run(
        self,
        agent: object,
        input_text: str,
        *,
        context: AgentRunContext | None,
        max_turns: int,
        workflow_name: str,
        api_key: str,
    ) -> object:
        self.calls.append(
            (
                "run",
                {
                    "agent": agent,
                    "input": input_text,
                    "context": context,
                    "max_turns": max_turns,
                    "workflow_name": workflow_name,
                    "api_key_configured": bool(api_key),
                },
            )
        )
        return {"summary": "supported explanation"}


@pytest.mark.asyncio
async def test_runtime_is_advisory_and_uses_only_registered_tools() -> None:
    sdk = FakeSdk()
    runtime = OpenAIAgentsRuntime(
        model="test-model",
        tools={"retrieve_evidence": object()},
        _sdk=sdk,
    )

    result = await runtime.run(
        AgentRunRequest(
            role=AgentRole.SIRA,
            instructions="Extract facts.",
            prompt="Summarize the supported facts.",
            model_context={"purchase_goal": "meeting intelligence"},
            run_context=AgentRunContext(
                organization_id="org_consultco",
                actor_id="actor_buyer",
                permissions=frozenset({"buyer:read"}),
            ),
            allowed_tools=("retrieve_evidence",),
        )
    )

    assert result.output == {"summary": "supported explanation"}
    assert result.advisory_only is True
    assert result.ranking_effect is False
    assert [call[0] for call in sdk.calls] == ["create", "run"]


@pytest.mark.asyncio
async def test_seil_payload_rejects_private_buyer_context() -> None:
    runtime = OpenAIAgentsRuntime(model="test", _sdk=FakeSdk())

    with pytest.raises(AgentBoundaryViolation, match="buyer-private"):
        await runtime.run(
            AgentRunRequest(
                role=AgentRole.SEIL,
                instructions="Explain fit.",
                prompt="Explain.",
                model_context={"buyer_passport": {"hidden_budget": "100.00"}},
            )
        )


@pytest.mark.asyncio
async def test_all_model_payloads_reject_credentials_and_card_like_values() -> None:
    runtime = OpenAIAgentsRuntime(model="test", _sdk=FakeSdk())

    with pytest.raises(AgentBoundaryViolation, match="secret field"):
        await runtime.run(
            AgentRunRequest(
                role=AgentRole.SIRA,
                instructions="Extract.",
                prompt="Extract.",
                model_context={
                    "payment_provider_secret_key": "do-not-send"  # pragma: allowlist secret
                },
            )
        )

    with pytest.raises(AgentBoundaryViolation, match="payment-card-like"):
        await runtime.run(
            AgentRunRequest(
                role=AgentRole.SIRA,
                instructions="Extract.",
                prompt="Extract.",
                model_context={"note": "4111 1111 1111 1111"},
            )
        )


@pytest.mark.asyncio
async def test_unknown_tool_is_rejected_before_sdk_execution() -> None:
    sdk = FakeSdk()
    runtime = OpenAIAgentsRuntime(model="test", _sdk=sdk)

    with pytest.raises(ValueError, match="unregistered tools"):
        await runtime.run(
            AgentRunRequest(
                role=AgentRole.SIRA,
                instructions="Extract.",
                prompt="Extract.",
                model_context={},
                allowed_tools=("checkout",),
            )
        )
    assert sdk.calls == []


@pytest.mark.asyncio
async def test_private_run_context_is_passed_to_tools_but_not_model_input() -> None:
    sdk = FakeSdk()
    runtime = OpenAIAgentsRuntime(model="test", _sdk=sdk)
    private_context = AgentRunContext(
        organization_id="org_private",
        actor_id="actor_private",
        services={"credential_handle": object()},
    )

    await runtime.run(
        AgentRunRequest(
            role=AgentRole.SIRA,
            instructions="Explain.",
            prompt="Explain.",
            model_context={"allowed_fact": "public"},
            run_context=private_context,
        )
    )

    run_call = sdk.calls[1][1]
    assert isinstance(run_call, dict)
    assert run_call["context"] is private_context
    assert "org_private" not in str(run_call["input"])
    assert "actor_private" not in str(run_call["input"])
