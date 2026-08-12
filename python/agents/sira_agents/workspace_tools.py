"""Bounded read-only tools for the commerce workspace agent."""

from __future__ import annotations

from typing import Any, Protocol, cast

from pydantic import BaseModel, Field

from agents import RunContextWrapper, function_tool
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
    listing_origin: str | None = None
    evidence_status: str | None = None
    seller_attested: bool | None = None


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
    stop_words = {"a", "an", "and", "for", "in", "of", "or", "the", "to", "with"}
    query_terms = {
        term
        for term in normalized_query.replace("-", " ").split()
        if len(term) > 2 and term not in stop_words
    }
    scored: list[tuple[int, CatalogProductResult]] = []
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
        if not normalized_query:
            score = 1
        elif normalized_query in searchable:
            score = len(query_terms) + 2
        else:
            score = sum(1 for term in query_terms if term in searchable)
        if score:
            scored.append((score, product))
    scored.sort(key=lambda item: (-item[0], item[1].name.casefold()))
    return [product for _, product in scored[:bounded_limit]]


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


def workspace_tool_registry() -> dict[str, object]:
    return {
        "search_published_products": search_published_products,
        "get_published_product": get_published_product,
    }
