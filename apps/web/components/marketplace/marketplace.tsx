"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Database, Search, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { buyerDevelopmentHeaders, getBrowserApiClient } from "@/lib/api";

import styles from "./marketplace.module.css";

type ProductResult = {
  bundle_digest: string;
  category: string;
  cosine_distance: string;
  href: string;
  name: string;
  product_id: string;
  seller: string | null;
  summary: string | null;
};

function safeResult(raw: Record<string, unknown>): ProductResult {
  return {
    bundle_digest: String(raw.bundle_digest),
    category: String(raw.category),
    cosine_distance: String(raw.cosine_distance),
    href: String(raw.href),
    name: String(raw.name),
    product_id: String(raw.product_id),
    seller: raw.seller ? String(raw.seller) : null,
    summary: raw.summary ? String(raw.summary) : null,
  };
}

export function MarketplaceSearch() {
  const [draft, setDraft] = useState("EU hosted meeting intelligence for a 40-person sales team");
  const [query, setQuery] = useState(draft);
  const category = "meeting-intelligence";
  const search = useQuery({
    queryKey: ["public-marketplace", category, query],
    queryFn: async () => {
      const payload = await getBrowserApiClient().request("qualification_search_marketplace", {
        headers: buyerDevelopmentHeaders,
        query: { category, query, limit: 12 },
      });
      return {
        model: payload.query_model_id,
        results: payload.results.map((item) => safeResult(item)),
      };
    },
  });

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <Link href="/sira" className={styles.wordmark}>
          SIRA
        </Link>
        <nav aria-label="Marketplace navigation">
          <Link href="/sira">Workspace</Link>
          <Link aria-current="page" href="/marketplace">
            Marketplace
          </Link>
          <Link href="/sira/inbox">Inbox</Link>
        </nav>
      </header>
      <section className={styles.hero}>
        <p>Evidence-qualified marketplace</p>
        <h1>Search current product truth.</h1>
        <span>
          Bedrock embeds the buyer intent. CockroachDB DVI retrieves only active public Product
          Bundles; relational gates remove stale versions.
        </span>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            setQuery(draft.trim());
          }}
        >
          <Search aria-hidden="true" />
          <label className="sr-only" htmlFor="marketplace-query">
            Describe what your company needs
          </label>
          <input
            id="marketplace-query"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            minLength={3}
          />
          <button type="submit">Search evidence</button>
        </form>
      </section>
      <section className={styles.content} aria-live="polite">
        <div className={styles.resultHead}>
          <div>
            <p>Current published bundles</p>
            <h2>Qualified candidates</h2>
          </div>
          {search.data ? <code>{search.data.model}</code> : null}
        </div>
        {search.isPending ? (
          <div className={styles.state}>
            Embedding intent and querying the distributed vector index…
          </div>
        ) : null}
        {search.isError ? (
          <div className={styles.state} role="alert">
            <strong>Marketplace unavailable.</strong>
            <span>
              No fixture products were substituted. Start the catalog database and Bedrock provider,
              then retry.
            </span>
            <button onClick={() => void search.refetch()} type="button">
              Retry
            </button>
          </div>
        ) : null}
        {search.data && !search.data.results.length ? (
          <div className={styles.state}>
            <strong>No current published match.</strong>
            <span>Try a broader requirement or ask a seller to publish eligible evidence.</span>
          </div>
        ) : null}
        <div className={styles.grid}>
          {search.data?.results.map((product) => (
            <article className={styles.card} key={`${product.product_id}:${product.bundle_digest}`}>
              <div className={styles.cardMeta}>
                <span>
                  <ShieldCheck aria-hidden="true" /> Published
                </span>
                <code>{product.cosine_distance}</code>
              </div>
              <h2>{product.name}</h2>
              <p>{product.summary ?? "Buyer-safe published evidence bundle"}</p>
              <dl>
                <div>
                  <dt>Seller</dt>
                  <dd>{product.seller ?? "Verified publisher"}</dd>
                </div>
                <div>
                  <dt>Category</dt>
                  <dd>{product.category}</dd>
                </div>
              </dl>
              <Link href={product.href}>
                Inspect current bundle <ArrowRight aria-hidden="true" />
              </Link>
            </article>
          ))}
        </div>
        <aside className={styles.boundary}>
          <Database aria-hidden="true" />
          <div>
            <strong>Retrieval is not authority.</strong>
            <span>
              Vector distance proposes candidates. Active-bundle joins, evidence eligibility, and
              the qualification worker decide what can be used.
            </span>
          </div>
        </aside>
      </section>
    </main>
  );
}

export function MarketplaceProduct({ productId }: { productId: string }) {
  const product = useQuery({
    queryKey: ["public-marketplace-product", productId],
    queryFn: () =>
      getBrowserApiClient().request("qualification_get_marketplace_product", {
        headers: buyerDevelopmentHeaders,
        pathParams: { product_id: productId },
      }),
  });
  const record = product.data?.product as Record<string, unknown> | undefined;
  const payload = record?.payload as Record<string, unknown> | undefined;
  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <Link href="/marketplace" className={styles.wordmark}>
          SIRA Marketplace
        </Link>
      </header>
      <section className={styles.productPage}>
        {product.isPending ? (
          <div className={styles.state}>Loading the current Product Bundle…</div>
        ) : product.isError || !record ? (
          <div className={styles.state} role="alert">
            <strong>Published product unavailable.</strong>
            <Link href="/marketplace">Return to marketplace</Link>
          </div>
        ) : (
          <>
            <p>Active Product Bundle</p>
            <h1>{String(payload?.name ?? payload?.product_name ?? productId)}</h1>
            <span>
              {String(
                payload?.summary ??
                  payload?.public_summary ??
                  "Buyer-safe published product evidence",
              )}
            </span>
            <dl>
              <div>
                <dt>Product</dt>
                <dd>{productId}</dd>
              </div>
              <div>
                <dt>Generation</dt>
                <dd>{String(record.generation)}</dd>
              </div>
              <div>
                <dt>Evidence</dt>
                <dd>{String(record.evidence_status)}</dd>
              </div>
            </dl>
            <section className={styles.bundle}>
              <h2>Buyer-safe projection</h2>
              <pre>{JSON.stringify(payload, null, 2)}</pre>
            </section>
            <Link href="/marketplace">← Back to marketplace</Link>
          </>
        )}
      </section>
    </main>
  );
}
