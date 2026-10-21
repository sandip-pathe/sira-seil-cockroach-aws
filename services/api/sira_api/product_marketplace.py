"""Demand-driven public catalog shared by SIRA and published SEIL products."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from openai import AuthenticationError, OpenAIError, RateLimitError
from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from domain import content_hash
from integrations.product_search import ProductResearch, canonical_product_url, public_url
from persistence.database import Database
from persistence.marketplace_models import (
    MarketplaceObservation,
    MarketplaceProduct,
    MarketplaceSellerLink,
)
from persistence.models import SellerPackVersion, SellerProduct
from persistence.repositories import new_id

from .errors import ApiProblem


class ProductSearch(Protocol):
    async def search(
        self, query: str, *, limit: int = 5
    ) -> tuple[ProductResearch, list[dict[str, Any]]]: ...


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _expiry(field: str, now: datetime) -> datetime:
    return now + (
        timedelta(hours=24)
        if field in {"price", "annual_price_usd", "availability", "stock"}
        else timedelta(days=7)
    )


def _priority(observation: MarketplaceObservation) -> tuple[bool, bool, float]:
    return (
        _utc(observation.expires_at) <= datetime.now(UTC),
        observation.origin != "SELLER_PUBLISHED",
        -_utc(observation.observed_at).timestamp(),
    )


async def record_observation(
    session: AsyncSession,
    *,
    website: str,
    edition: str,
    payload: dict[str, Any],
    origin: str,
    source_key: str,
    sources: list[dict[str, Any]],
    now: datetime,
) -> str:
    """Only public product facts belong here. No buyer context or private seller draft."""
    website = canonical_product_url(website)
    key = content_hash({"website": website, "edition": edition.strip().casefold()})
    product_id = "prd_" + key.removeprefix("sha256:")[:40]
    insert = sqlite_insert if session.get_bind().dialect.name == "sqlite" else pg_insert
    await session.execute(
        insert(MarketplaceProduct)
        .values(
            id=product_id,
            identity_key=key,
            name=payload["name"],
            website=website,
            edition=edition.strip(),
            search_text=" ".join(
                [str(payload.get(k) or "") for k in ("name", "seller", "summary", "category")]
                + [str(fact.get("value", "")) for fact in payload.get("facts", [])]
            ),
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    product = await session.get(MarketplaceProduct, product_id)
    assert product is not None
    additions = " ".join(str(fact.get("value", "")) for fact in payload.get("facts", []))
    product.search_text = (product.search_text + " " + additions)[-20000:]
    # Preserve versions; replace current evidence only within the same provenance stream.
    await session.execute(
        update(MarketplaceObservation)
        .where(
            MarketplaceObservation.product_id == product_id,
            MarketplaceObservation.origin == origin,
            MarketplaceObservation.source_key == source_key,
            MarketplaceObservation.active.is_(True),
        )
        .values(active=False)
    )
    facts = [
        {
            **fact,
            "observed_at": now.isoformat(),
            "expires_at": _expiry(str(fact["field"]), now).isoformat(),
        }
        for fact in payload.get("facts", [])
    ]
    observed = {**payload, "facts": facts}
    session.add(
        MarketplaceObservation(
            id=new_id("pobs"),
            product_id=product_id,
            origin=origin,
            source_key=source_key,
            payload=observed,
            content_hash=content_hash(observed),
            source_refs=sources,
            observed_at=now,
            expires_at=min(
                (_expiry(str(f["field"]), now) for f in facts), default=now + timedelta(days=7)
            ),
            active=True,
        )
    )
    return product_id


async def publish_seller_observation(
    session: AsyncSession,
    *,
    organization_id: str,
    product: SellerProduct,
    pack: SellerPackVersion,
) -> None:
    link = await session.scalar(
        select(MarketplaceSellerLink).where(
            MarketplaceSellerLink.organization_id == organization_id,
            MarketplaceSellerLink.seller_product_id == product.id,
        )
    )
    if link is None:
        return  # Existing products must supply their canonical identity before catalog publication.
    public_sources: dict[str, dict[str, Any]] = {}
    for evidence in pack.payload.get("evidence", []):
        if not evidence.get("source_url"):
            continue
        try:
            url = public_url(evidence["source_url"])
        except ValueError:
            continue
        public_sources[str(evidence["id"])] = {
            "url": url,
            "observed_at": evidence.get("observed_at"),
            "verification_state": evidence.get("verification_state"),
        }
    facts = []
    for claim in pack.payload.get("claims", []):
        evidence_refs = [
            public_sources[key] for key in claim.get("evidence_ids", []) if key in public_sources
        ]
        facts.append(
            {
                "field": str(claim["field"]),
                "value": claim["value"],
                "source_urls": [ref["url"] for ref in evidence_refs],
                "evidence_refs": evidence_refs,
                "pack_version_id": pack.id,
            }
        )
    public_claims = {str(c["field"]): c["value"] for c in pack.payload.get("claims", [])}
    payload = {
        "name": str(public_claims.get("product_name", product.name)),
        "seller": link.seller_name,
        "summary": str(public_claims.get("public_summary", product.public_summary)),
        "category": product.category,
        "facts": facts,
        "pack_version_id": pack.id,
        "pack_hash": pack.content_hash,
    }
    await record_observation(
        session,
        website=link.website,
        edition=link.edition,
        payload=payload,
        origin="SELLER_PUBLISHED",
        source_key=f"{organization_id}:{product.id}",
        sources=[
            {
                "url": link.website,
                "title": product.name,
                "authority": "SELLER_PUBLISHED",
                "pack_version_id": pack.id,
            }
        ]
        + [
            {
                "url": ref["url"],
                "title": "Published supporting evidence",
                "authority": "SELLER_PUBLISHED",
                "pack_version_id": pack.id,
            }
            for ref in public_sources.values()
        ],
        now=_utc(pack.published_at),
    )


class ProductMarketplace:
    def __init__(self, database: Database, search_provider: ProductSearch | None = None) -> None:
        self.database = database
        self.search_provider = search_provider

    async def search(
        self, organization_id: str, *, query: str = "", limit: int = 20
    ) -> dict[str, Any]:
        if not 1 <= limit <= 50 or len(query) > 1000:
            raise ValueError("Marketplace query or result limit is invalid")
        terms = list(dict.fromkeys(re.findall(r"[\w-]{2,}", query.casefold())))[:20]
        terms = [
            t
            for t in terms
            if t
            not in {
                "the",
                "for",
                "and",
                "with",
                "buy",
                "need",
                "find",
                "me",
                "some",
                "our",
                "want",
                "products",
            }
        ]
        async with self.database.transaction(organization_id) as session:
            statement = (
                select(MarketplaceProduct, MarketplaceObservation)
                .join(
                    MarketplaceObservation,
                    MarketplaceObservation.product_id == MarketplaceProduct.id,
                )
                .where(MarketplaceObservation.active.is_(True))
            )
            statement = statement.where(
                or_(
                    MarketplaceObservation.withdrawn_at.is_(None),
                    MarketplaceObservation.withdrawn_at > datetime.now(UTC),
                )
            )
            if terms:
                statement = statement.where(
                    or_(
                        *[
                            MarketplaceProduct.search_text.icontains(term, autoescape=True)
                            for term in terms
                        ]
                    )
                )
            records = (
                await session.execute(
                    statement.order_by(MarketplaceObservation.observed_at.desc()).limit(300)
                )
            ).all()
        grouped: dict[str, tuple[Any, Any]] = {}
        for product, observation in records:
            previous = grouped.get(product.id)
            if previous is None or _priority(observation) < _priority(previous[1]):
                grouped[product.id] = (product, observation)
        candidates = [
            pair
            for pair in grouped.values()
            if not terms
            or sum(term in pair[0].search_text.casefold() for term in terms) >= min(2, len(terms))
        ]
        ordered = sorted(
            candidates,
            key=lambda pair: (
                -sum(term in pair[0].search_text.casefold() for term in terms),
                pair[0].id,
            ),
        )[:limit]
        return {"results": [self._view(p, o) for p, o in ordered], "source": "catalog"}

    async def product(
        self, organization_id: str, product_id: str, *, include_history: bool = True
    ) -> dict[str, Any]:
        async with self.database.transaction(organization_id) as session:
            product = await session.get(MarketplaceProduct, product_id)
            statement = (
                select(MarketplaceObservation)
                .where(MarketplaceObservation.product_id == product_id)
                .order_by(MarketplaceObservation.observed_at.desc())
            )
            current = list(
                (
                    await session.scalars(
                        statement.where(
                            MarketplaceObservation.active.is_(True),
                            or_(
                                MarketplaceObservation.withdrawn_at.is_(None),
                                MarketplaceObservation.withdrawn_at > datetime.now(UTC),
                            ),
                        ).limit(100)
                    )
                ).all()
            )
            observations = (
                list((await session.scalars(statement.limit(10))).all()) if include_history else []
            )
        if product is None or not current:
            raise ApiProblem(
                code="PRODUCT_NOT_FOUND", message="That product is unavailable.", status_code=404
            )
        chosen = min(current, key=_priority)
        return {
            **self._view(product, chosen),
            "observations": [
                {
                    "id": o.id,
                    "origin": o.origin,
                    "active": o.active
                    and (o.withdrawn_at is None or _utc(o.withdrawn_at) > datetime.now(UTC)),
                    "withdrawn_at": _utc(o.withdrawn_at).isoformat() if o.withdrawn_at else None,
                    "facts": o.payload.get("facts", []),
                    "source_refs": o.source_refs,
                    "observed_at": _utc(o.observed_at).isoformat(),
                    "expires_at": _utc(o.expires_at).isoformat(),
                    "content_hash": o.content_hash,
                }
                for o in observations
            ],
        }

    async def discover(
        self, organization_id: str, *, query: str, limit: int = 5, refresh: bool = False
    ) -> dict[str, Any]:
        if not query.strip() or len(query) > 1000 or not 1 <= limit <= 10:
            raise ValueError("A public product query and limit between 1 and 10 are required")
        cached = await self.search(organization_id, query=query, limit=limit)
        if (
            not refresh
            and len(cached["results"]) >= min(limit, 3)
            and all(not row["stale"] for row in cached["results"])
        ):
            return cached
        if self.search_provider is None:
            raise ApiProblem(
                code="PRODUCT_SEARCH_UNAVAILABLE",
                message="Live product search is not configured.",
                status_code=503,
            )
        try:
            research, sources = await self.search_provider.search(query.strip(), limit=limit)
        except AuthenticationError as error:
            raise ApiProblem(
                code="PRODUCT_SEARCH_CREDENTIALS_INVALID",
                message="Live product search is unavailable: the server's OpenAI key was rejected.",
                status_code=503,
                retryable=False,
                next_action="configure_openai_api_key",
            ) from error
        except RateLimitError as error:
            raise ApiProblem(
                code="PRODUCT_SEARCH_LIMIT_REACHED",
                message="Live product search has reached its provider usage limit.",
                status_code=503,
                retryable=error.code != "insufficient_quota",
                next_action="check_openai_usage_limits",
            ) from error
        except (ValueError, TimeoutError, OpenAIError) as error:
            raise ApiProblem(
                code="PRODUCT_RESEARCH_FAILED",
                message="Product sources could not be verified. Try again.",
                status_code=502,
                retryable=True,
            ) from error
        now = datetime.now(UTC)

        async def save(session: AsyncSession) -> list[str]:
            ids = []
            for product in research.products:
                urls = {url for fact in product.facts for url in fact.source_urls}
                ids.append(
                    await record_observation(
                        session,
                        website=product.website,
                        edition=product.edition,
                        payload=product.model_dump(exclude={"website", "edition"}),
                        origin="PUBLIC_WEB",
                        source_key=content_hash(product.website),
                        sources=[
                            {**source, "authority": "PUBLIC_WEB"}
                            for source in sources
                            if source["url"] in urls
                        ],
                        now=now,
                    )
                )
            return ids

        ids = await self.database.run_retryable(organization_id, save)
        return {
            "results": [
                await self.product(organization_id, key, include_history=False)
                for key in dict.fromkeys(ids)
            ],
            "source": "live_web",
            "researched_at": now.isoformat(),
        }

    @staticmethod
    def _view(product: MarketplaceProduct, observation: MarketplaceObservation) -> dict[str, Any]:
        payload = observation.payload
        now = datetime.now(UTC)
        facts = payload.get("facts", [])
        stale_fields = [f["field"] for f in facts if datetime.fromisoformat(f["expires_at"]) <= now]
        price = next(
            (str(f["value"]) for f in facts if f["field"] in {"price", "annual_price_usd"}), None
        )
        seller = observation.origin == "SELLER_PUBLISHED"
        return {
            "id": product.id,
            "product_id": product.id,
            "name": product.name,
            "seller": payload["seller"],
            "edition": product.edition,
            "website": product.website,
            "category": payload.get("category", ""),
            "summary": payload["summary"],
            "price": price or "Price not available",
            "billing_unit": "see_source",
            "claims": [str(f["value"]) for f in facts if f["field"] != "price"],
            "integrations": [str(f["value"]) for f in facts if f["field"] == "integration"],
            "facts": facts,
            "source_refs": observation.source_refs,
            "status": "published" if seller else "research_only",
            "listing_origin": "SELLER_PUBLISHED" if seller else "SEIL_RESEARCHED",
            "evidence_status": "PUBLISHED" if seller else "RESEARCH_ONLY",
            "seller_attested": seller,
            "observed_at": _utc(observation.observed_at).isoformat(),
            "expires_at": _utc(observation.expires_at).isoformat(),
            "evidence_freshness": f"Checked {_utc(observation.observed_at).isoformat()}",
            "stale": _utc(observation.expires_at) <= now,
            "stale_fields": stale_fields,
            "observation_id": observation.id,
        }
