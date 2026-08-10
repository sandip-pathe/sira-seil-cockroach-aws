"""Bounded public-web research for SEIL Product Evidence drafts."""

from __future__ import annotations

import json
from typing import Any, Protocol
from urllib.parse import urlparse

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field


class SeilWebSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=240)
    url: str = Field(min_length=1, max_length=2_000)


class SeilProductIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_name: str = Field(min_length=1, max_length=160)
    seller_name: str = Field(min_length=1, max_length=160)
    canonical_url: str | None


class SeilWebResearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity: SeilProductIdentity
    summary: str = Field(min_length=1, max_length=1_500)
    claims: list[str] = Field(max_length=12)
    fit_rules: list[str] = Field(max_length=10)
    anti_fit_rules: list[str] = Field(max_length=10)
    unknowns: list[str] = Field(max_length=10)
    conflicts: list[str] = Field(max_length=10)
    qualification_blockers: list[str] = Field(max_length=10)
    sources: list[SeilWebSource] = Field(min_length=1, max_length=8)

    def artifact_payload(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json", exclude={"sources"})
        identity = payload["identity"]
        if identity.get("canonical_url") and not _is_public_url(identity["canonical_url"]):
            identity["canonical_url"] = None
        return payload

    def source_refs(self) -> list[dict[str, str]]:
        seen: set[str] = set()
        refs: list[dict[str, str]] = []
        for source in self.sources:
            normalized = source.url.strip()
            if not _is_public_url(normalized) or normalized in seen:
                continue
            seen.add(normalized)
            refs.append(
                {"title": source.title.strip(), "url": normalized, "authority": "PUBLIC_WEB"}
            )
        if not refs:
            raise ValueError("SEIL web research returned no usable public source URLs")
        return refs


class SeilWebResearcher(Protocol):
    async def research(self, request: str) -> SeilWebResearchResult: ...

    async def discover(self, request: str) -> SeilMarketDiscoveryResult: ...


class SeilDiscoveredProduct(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity: SeilProductIdentity
    summary: str = Field(min_length=1, max_length=1_000)
    price: str = Field(min_length=1, max_length=120)
    claims: list[str] = Field(max_length=6)
    integrations: list[str] = Field(max_length=12)
    sources: list[SeilWebSource] = Field(min_length=1, max_length=5)


class SeilMarketDiscoveryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str = Field(min_length=1, max_length=120)
    products: list[SeilDiscoveredProduct] = Field(min_length=1, max_length=3)


class OpenAISeilWebResearcher:
    """Use one Responses API call instead of the full multi-turn agent runtime."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self.model = model
        self.client = client or AsyncOpenAI(api_key=api_key, timeout=90, max_retries=0)

    async def research(self, request: str) -> SeilWebResearchResult:
        response = await self.client.responses.create(
            model=self.model,
            instructions=(
                "You are SEIL's public product researcher. Search the public web once and create "
                "a concise, source-linked Product Evidence draft. Prefer the seller's official "
                "product, pricing, documentation, security, privacy, and integration pages. "
                "Separate facts from unknowns. Never imply seller attestation, invent a URL, or "
                "claim that the draft is publishable. Return direct page URLs, not search pages."
            ),
            input=request,
            tools=[{"type": "web_search", "search_context_size": "low"}],
            tool_choice="auto",
            max_tool_calls=2,
            max_output_tokens=5_000,
            reasoning={"effort": "low"},
            text={
                "format": {
                    "type": "json_schema",
                    "name": "seil_product_research",
                    "strict": True,
                    "schema": SeilWebResearchResult.model_json_schema(),
                }
            },
        )
        if response.status != "completed" or not response.output_text:
            reason = getattr(response.incomplete_details, "reason", "empty_response")
            raise ValueError(f"SEIL web research did not complete: {reason}")
        result = SeilWebResearchResult.model_validate(json.loads(response.output_text))
        result.source_refs()
        return result

    async def discover(self, request: str) -> SeilMarketDiscoveryResult:
        response = await self.client.responses.create(
            model=self.model,
            instructions=(
                "You are SEIL's marketplace supply researcher. Infer the software category the "
                "buyer needs, then find two credible products from different vendors on the "
                "public web. Prefer official product, pricing, documentation, security, privacy, "
                "and integration pages. Create concise provisional listings using only facts "
                "supported by direct page URLs. These are platform-researched listings, not "
                "seller-attested listings. Do not return search-result URLs."
            ),
            input=request,
            tools=[{"type": "web_search", "search_context_size": "low"}],
            tool_choice="auto",
            max_tool_calls=3,
            max_output_tokens=5_000,
            reasoning={"effort": "low"},
            text={
                "format": {
                    "type": "json_schema",
                    "name": "seil_market_discovery",
                    "strict": True,
                    "schema": SeilMarketDiscoveryResult.model_json_schema(),
                }
            },
        )
        if response.status != "completed" or not response.output_text:
            reason = getattr(response.incomplete_details, "reason", "empty_response")
            raise ValueError(f"SEIL marketplace discovery did not complete: {reason}")
        result = SeilMarketDiscoveryResult.model_validate(json.loads(response.output_text))
        for product in result.products:
            if not any(_is_public_url(source.url.strip()) for source in product.sources):
                raise ValueError("SEIL marketplace discovery returned a product without sources")
        return result


def _is_public_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)
