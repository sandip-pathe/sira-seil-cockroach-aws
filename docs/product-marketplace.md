# Persistent marketplace and live product discovery

SIRA discovers products from public sources when the catalog cannot answer a buying request.
SEIL helps authenticated sellers create private product drafts, attach evidence, and release
reviewed versions. Both use a persistent public catalog in CockroachDB.

## Search choice

OpenAI Responses `web_search` uses the existing server-side `OPENAI_API_KEY`.
`OPENAI_SEARCH_MODEL` selects the search/extraction model (default `gpt-4.1-mini`).
The adapter requests the consulted source URLs, then extracts a validated product schema.
It accepts facts only when their cited URLs occur in that source set and the product's official
host occurs among consulted sources. This checks provenance membership; it does not independently
prove every assertion on a vendor page. Facts remain labeled public-web research.

Official API reference: https://developers.openai.com/api/docs/guides/tools-web-search

## Jack and Jill: documented behavior and the mapping

Jack works with candidates and maintains structured profiles through ongoing conversations.
Jill works with hiring teams, creates a hiring brief, and evaluates candidates through a sequence
of gates. Their public-profile pool supplements their own network and has different introduction
and fee behavior. Their public documentation does not disclose their database engine, schemas,
search provider, or internal retention design. We are adopting the product pattern rather than
claiming to reproduce those internals.

Sources:

- https://www.jackandjill.ai/docs/who-is-jill
- https://www.jackandjill.ai/docs/search-and-candidate-discovery
- https://web.jackandjill.ai/blog/ai-sourcing-is-broken-by-design

In our marketplace, SIRA maintains buyer-specific needs privately. SEIL maintains seller-owned
product evidence privately until reviewed publication. Public web observations supplement the
seller network. Buyer fit and private budgets never become fields on a shared product record.
The existing qualification engine remains the separate authority/evaluation path; web research
does not manufacture seller qualification, an offer, or a purchase authorization.

## Data and freshness

- `marketplace_products`: shared product identity, canonical official URL and edition, searchable text.
- `marketplace_observations`: versioned public facts, provenance, source links, observation times,
  content hashes, expiry, and withdrawal times. Refreshed facts preserve previous versions.
- `marketplace_seller_links`: tenant-scoped registration identity and seller name, protected by RLS.
- Existing seller draft/review/evidence tables remain private. Publication copies an explicit
  public projection into the catalog atomically with the approved pack. Suspension withdraws it
  at its effective time. Logging in or registering a draft does not publish it.

Identity normalization removes query strings/fragments and `www`, and normalizes trailing slashes.
Identity uses the official URL plus edition. Aliases across different official URLs or differently
named editions need later identity reconciliation; they are not merged by fuzzy name alone.

Price/stock/availability observations expire after 24 hours; other facts after seven days.
These are initial cache policies, not freshness guarantees. Explicit refresh bypasses the cache.
Exact commercial terms must still be confirmed at purchase time. Fresh seller observations take
precedence over fresh web observations; conflicting and historical versions remain visible in
product details. Stale facts are flagged and do not silently become current facts.

Discovery is bounded (up to ten products per request), performs provider I/O outside database
transactions, and persists only structured public facts and supporting links. It does not scrape
the whole internet, store private buying queries in the shared catalog, or seed fictional listings.
The catalog search currently uses bounded text retrieval; the existing qualified seller-bundle
vector index remains separate. A unified semantic index over researched products is future work.

## Interfaces

- SIRA `discover_products`: search reusable observations, use live web research when needed.
- SEIL `research_product`: the same public research path, without claiming ownership/publication.
- `GET /v1/workspace/catalog?query=...`: persisted catalog search.
- `GET /v1/workspace/catalog/{product_id}`: current product and evidence history.
- `POST /v1/marketplace/research`: `{query, limit, refresh}`. Query must contain public search terms.
- `POST /v1/seller/products`: authenticated seller registration with an idempotency key.
- SEIL Product Evidence panel: Add product creates a private draft, then existing evidence/review
  controls prepare and publish it. Firebase account configuration is required for real seller login.

Migration `cdb0020` adds these tables. It does not insert products. Only real discovery or seller
publication populates the shared catalog.
