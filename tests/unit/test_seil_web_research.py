from __future__ import annotations

import pytest
from sira_agents.runtime import AgentRunContext, AgentRunRequest, AgentRunResult
from sira_api.fixtures import DemoFixtureBundle
from sira_api.seil_web_research import (
    SeilProductIdentity,
    SeilWebResearchResult,
    SeilWebSource,
)
from sira_api.workspace_schemas import WorkspaceChatCreate
from sira_api.workspace_service import WorkspaceService


class _FakeResearcher:
    async def research(self, request: str) -> SeilWebResearchResult:
        assert "https://example.com/product" in request
        return SeilWebResearchResult(
            identity=SeilProductIdentity(
                product_name="Example Product",
                seller_name="Example",
                canonical_url="https://example.com/product",
            ),
            summary="A source-linked product summary.",
            claims=["Supports the documented integration."],
            fit_rules=["Buyer needs the documented integration."],
            anti_fit_rules=[],
            unknowns=["Enterprise pricing is not public."],
            conflicts=[],
            qualification_blockers=["Verify enterprise pricing."],
            sources=[
                SeilWebSource(title="Product", url="https://example.com/product"),
                SeilWebSource(title="Duplicate", url="https://example.com/product"),
                SeilWebSource(title="Unsafe", url="javascript:alert(1)"),
            ],
        )


class _UnexpectedRuntime:
    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        raise AssertionError("public research must not use the full agent runtime")


def _run_context(service: WorkspaceService) -> AgentRunContext:
    return AgentRunContext(
        organization_id="org_consultco",
        actor_id="actor_requester",
        permissions=frozenset({"can_view_context"}),
        services={"workspace_catalog": service},
    )


@pytest.mark.asyncio
async def test_seil_public_research_uses_bounded_research_path() -> None:
    service = WorkspaceService(
        DemoFixtureBundle.load(),
        api_key="configured",
        seil_api_key="configured",
        model="test",
        seil_web_researcher=_FakeResearcher(),
    )
    service.runtime = _UnexpectedRuntime()  # type: ignore[assignment]

    result = await service.chat(
        WorkspaceChatCreate(
            mode="seil",
            message="Research https://example.com/product using the public web",
        ),
        run_context=_run_context(service),
    )

    assert result["tool_calls"] == ["web_search"]
    assert result["advisory_only"] is True
    assert result["mission"]["stop_reason"] == "SEIL_WEB_RESEARCH_READY"
    assert len(result["artifacts"]) == 1
    artifact = result["artifacts"][0]
    assert artifact["kind"] == "seller_evidence"
    assert artifact["source_refs"] == [
        {
            "title": "Product",
            "url": "https://example.com/product",
            "authority": "PUBLIC_WEB",
        }
    ]


def test_source_refs_fail_closed_without_public_urls() -> None:
    result = SeilWebResearchResult(
        identity=SeilProductIdentity(
            product_name="Unsafe Product", seller_name="Unsafe", canonical_url="file:///tmp/a"
        ),
        summary="No valid public sources.",
        claims=[],
        fit_rules=[],
        anti_fit_rules=[],
        unknowns=[],
        conflicts=[],
        qualification_blockers=[],
        sources=[SeilWebSource(title="Unsafe", url="file:///tmp/a")],
    )

    with pytest.raises(ValueError, match="no usable public source URLs"):
        result.source_refs()
    assert result.artifact_payload()["identity"]["canonical_url"] is None
