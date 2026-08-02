"""Bounded read-only tools for the commerce workspace agent."""

from __future__ import annotations

from typing import Any, Protocol, cast

from pydantic import BaseModel, Field

from agents import RunContextWrapper, function_tool
from integrations.senso import SensoEvidenceProvider, SensoSearchRequest
from sira_agents.runtime import AgentRunContext


class WorkspaceCatalog(Protocol):
    def catalog(self) -> list[dict[str, Any]]: ...

    def product(self, product_id: str) -> dict[str, Any] | None: ...


class CatalogProductResult(BaseModel):
    id: str
    name: str
    seller: str
    edition: str
    price: str
    billing_unit: str
    status: str
    summary: str
    claims: list[str]
    integrations: list[str]


class SensoEvidenceResult(BaseModel):
    answer: str | None
    sources: list[dict[str, object]]
    truth_verified: bool = False


def _catalog(context: AgentRunContext) -> WorkspaceCatalog:
    if "can_view_context" not in context.permissions:
        raise PermissionError("catalog tools require can_view_context")
    service = context.services.get("workspace_catalog")
    if service is None:
        raise RuntimeError("workspace catalog service is unavailable")
    return cast(WorkspaceCatalog, service)


def search_catalog(
    context: AgentRunContext, *, query: str = "", limit: int = 8
) -> list[CatalogProductResult]:
    """Search the published catalogue with a deterministic bounded result set."""

    normalized_query = query.strip().casefold()
    bounded_limit = min(max(limit, 1), 20)
    matches: list[CatalogProductResult] = []
    for raw_product in _catalog(context).catalog():
        product = CatalogProductResult.model_validate(raw_product)
        searchable = " ".join(
            [
                product.name,
                product.seller,
                product.edition,
                product.summary,
                *product.claims,
                *product.integrations,
            ]
        ).casefold()
        if normalized_query and normalized_query not in searchable:
            continue
        matches.append(product)
        if len(matches) == bounded_limit:
            break
    return matches


def get_catalog_product(
    context: AgentRunContext, *, product_id: str
) -> CatalogProductResult | None:
    """Return one exact published product by server-owned identifier."""

    raw_product = _catalog(context).product(product_id.strip())
    if raw_product is None:
        return None
    return CatalogProductResult.model_validate(raw_product)


@function_tool(strict_mode=True)
async def search_published_products(
    wrapper: RunContextWrapper[AgentRunContext],
    query: str = "",
    limit: int = Field(default=8, ge=1, le=20),
) -> list[CatalogProductResult]:
    """Search current published products. Use an empty query to browse the catalogue."""

    return search_catalog(wrapper.context, query=query, limit=limit)


@function_tool(strict_mode=True)
async def get_published_product(
    wrapper: RunContextWrapper[AgentRunContext], product_id: str
) -> CatalogProductResult | None:
    """Get exact published facts for one product returned by catalogue search."""

    return get_catalog_product(wrapper.context, product_id=product_id)


@function_tool(strict_mode=True)
async def search_senso_evidence(
    wrapper: RunContextWrapper[AgentRunContext],
    query: str,
    max_results: int = Field(default=5, ge=1, le=10),
) -> SensoEvidenceResult:
    """Search the caller's verified private Senso folder with source provenance."""

    service_name = "senso_seller" if wrapper.context.party == "SELLER" else "senso_buyer"
    provider = wrapper.context.services.get(service_name)
    if provider is None:
        raise RuntimeError("verified Senso scope is unavailable")
    senso = cast(SensoEvidenceProvider, provider)
    result = await senso.search(
        SensoSearchRequest(query=query, scope=senso.scope, max_results=max_results)
    )
    return SensoEvidenceResult(
        answer=result.answer,
        sources=[
            {
                "content_id": hit.content_id,
                "title": hit.title,
                "chunk_text": hit.chunk_text,
                "score": hit.score,
                "source_version": hit.source_version,
            }
            for hit in result.hits
        ],
    )


def workspace_tool_registry() -> dict[str, object]:
    return {
        "search_published_products": search_published_products,
        "get_published_product": get_published_product,
        "search_senso_evidence": search_senso_evidence,
    }
