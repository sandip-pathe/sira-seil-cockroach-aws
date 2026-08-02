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


def workspace_tool_registry() -> dict[str, object]:
    return {
        "search_published_products": search_published_products,
        "get_published_product": get_published_product,
    }
