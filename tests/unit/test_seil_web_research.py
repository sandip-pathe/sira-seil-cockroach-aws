from __future__ import annotations

import asyncio

import pytest
from sira_agents.runtime import AgentRunContext, AgentRunRequest, AgentRunResult
from sira_api.fixtures import DemoFixtureBundle
from sira_api.seil_web_research import (
    SeilDiscoveredProduct,
    SeilMarketDiscoveryResult,
    SeilProductIdentity,
    SeilWebResearchResult,
    SeilWebSource,
)
from sira_api.workspace_schemas import WorkspaceChatCreate
from sira_api.workspace_service import WorkspaceService


class _FakeResearcher:
    calls = 0

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

    async def discover(self, request: str) -> SeilMarketDiscoveryResult:
        self.calls += 1
        assert "note taking" in request
        return SeilMarketDiscoveryResult(
            category="AI meeting notes",
            products=[
                SeilDiscoveredProduct(
                    identity=SeilProductIdentity(
                        product_name="Public Note",
                        seller_name="Public Note Inc.",
                        canonical_url="https://public-note.example/product",
                    ),
                    summary="A publicly researched meeting-notes product.",
                    price="Public pricing available",
                    claims=["Supports meeting summaries."],
                    integrations=["zoom", "hubspot"],
                    sources=[
                        SeilWebSource(
                            title="Public Note product",
                            url="https://public-note.example/product",
                        )
                    ],
                ),
                SeilDiscoveredProduct(
                    identity=SeilProductIdentity(
                        product_name="Fathom duplicate",
                        seller_name="Fathom",
                        canonical_url="https://fathom.video/",
                    ),
                    summary="A duplicate of an existing researched listing.",
                    price="USD 19",
                    claims=["Meeting summaries."],
                    integrations=["zoom"],
                    sources=[SeilWebSource(title="Fathom", url="https://fathom.video/pricing")],
                ),
            ],
        )


class _UnexpectedRuntime:
    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        raise AssertionError("public research must not use the full agent runtime")


class _CaptureRuntime:
    called = False

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        self.called = True
        return AgentRunResult(
            output={
                "message": "Seller workspace updated.",
                "mission_state": "SYNTHESIZING",
                "stop_reason": "SELLER_WORKSPACE_UPDATED",
            }
        )


def _run_context(service: WorkspaceService) -> AgentRunContext:
    return AgentRunContext(
        organization_id="org_consultco",
        actor_id="actor_requester",
        permissions=frozenset({"can_view_context"}),
        services={"workspace_catalog": service},
    )


@pytest.mark.asyncio
async def test_sira_buying_request_uses_seil_marketplace_discovery() -> None:
    researcher = _FakeResearcher()
    service = WorkspaceService(
        DemoFixtureBundle.load(),
        api_key="configured",  # pragma: allowlist secret
        seil_api_key="configured",  # pragma: allowlist secret
        model="test",
        seil_web_researcher=researcher,
    )
    service.runtime = _UnexpectedRuntime()  # type: ignore[assignment]

    result = await service.chat(
        WorkspaceChatCreate(
            mode="sira",
            message="I need a note taking system for our Zoom sales calls with HubSpot",
        ),
        run_context=_run_context(service),
    )

    await asyncio.sleep(0)
    assert researcher.calls == 1
    assert result["tool_calls"] == [
        "search_published_products",
        "search_seil_researched_listings",
        "compare_product_evidence",
    ]
    assert result["panel"] == "catalog"
    assert result["mission"]["stop_reason"] == "SIRA_MARKETPLACE_CANDIDATES_READY"
    assert (
        sum(product["listing_origin"] == "SELLER_PUBLISHED" for product in result["products"]) == 2
    )
    assert (
        sum(product["listing_origin"] == "SEIL_RESEARCHED" for product in result["products"]) == 2
    )
    assert len(result["products"]) == 4
    researched = next(product for product in result["products"] if product["name"] == "Fathom")
    assert researched["evidence_status"] == "RESEARCH_ONLY"
    assert researched["seller_attested"] is False
    assert researched["fit"] == "Strong fit"
    assert researched["requirement_coverage"] == "2/2 stated integrations"
    refreshed_names = {product["name"] for product in service.catalog()}
    assert "Public Note" in refreshed_names
    assert "Fathom duplicate" not in refreshed_names
    assert len(result["artifacts"]) == 1
    artifact = result["artifacts"][0]
    assert artifact["kind"] == "candidate_set"
    assert {source["authority"] for source in artifact["source_refs"]} == {"PUBLIC_WEB"}


@pytest.mark.asyncio
async def test_vendor_seil_chat_does_not_trigger_market_discovery() -> None:
    researcher = _FakeResearcher()
    service = WorkspaceService(
        DemoFixtureBundle.load(),
        api_key="configured",  # pragma: allowlist secret
        seil_api_key="configured",  # pragma: allowlist secret
        model="test",
        seil_web_researcher=researcher,
    )
    runtime = _CaptureRuntime()
    service.runtime = runtime  # type: ignore[assignment]

    result = await service.chat(
        WorkspaceChatCreate(
            mode="seil",
            message="Research our product website and improve our positioning",
        ),
        run_context=_run_context(service),
    )

    assert runtime.called is True
    assert researcher.calls == 0
    assert result["message"] == "Seller workspace updated."


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
