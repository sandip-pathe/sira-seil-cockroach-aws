"use client";

import type {
  SellerEvidenceClaim,
  SellerEvidenceState,
  SellerEvidenceView,
  SellerPackDraftView,
  SellerProductSearchItem,
  SellerProductSearchView,
} from "@sira/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Download,
  FileCheck2,
  FileSearch,
  FlaskConical,
  Home,
  Info,
  Package,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  X,
} from "lucide-react";
import Link from "next/link";
import {
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  WEB_DATA_MODE,
  createIdempotencyKey,
  getBrowserApiClient,
  sellerEditorDevelopmentHeaders,
} from "@/lib/api";

import styles from "./seller-surfaces.module.css";

const IS_FIXTURE_MODE = WEB_DATA_MODE === "fixture";

const AUTHORITY_COPY =
  "Publisher authority identifies who stands behind this package; it does not mean every claim was independently verified.";

const FIXTURE_SEARCH: SellerProductSearchView = {
  results: [
    {
      category: "Meeting intelligence",
      href: "/seller/product-evidence/product_fixture_d",
      id: "product_fixture_d",
      name: "Northstar Meeting Notes",
      public_summary:
        "Meeting capture and searchable decision records for client-service teams.",
      publisher_authority: "PLATFORM_COMPILED",
      state: "SELLER_DRAFT",
    },
    {
      category: "Meeting intelligence",
      href: "/seller/product-evidence/product_fixture_c",
      id: "product_fixture_c",
      name: "CurrentCall Workspace",
      public_summary:
        "Collaborative meeting records with workspace administration and exports.",
      publisher_authority: "SELLER_SEALED",
      state: "PUBLISHED",
    },
    {
      category: "Meeting intelligence",
      href: "/seller/product-evidence/product_fixture_b",
      id: "product_fixture_b",
      name: "Briefly Capture",
      public_summary:
        "Externally discovered product information awaiting an authorized publisher.",
      publisher_authority: "EXTERNAL_UNSEALED",
      state: "UNCLAIMED",
    },
  ],
};

const FIXTURE_DRAFT: SellerPackDraftView = {
  anti_fit_rules: [
    {
      evidence_ids: ["evidence_regional_availability"],
      field: "buyer.region",
      value: ["outside_us_ca"],
    },
  ],
  claims: [
    {
      evidence_ids: ["evidence_security_overview"],
      field: "customer_data_used_for_training",
      value: false,
    },
    {
      evidence_ids: ["evidence_retention_policy"],
      field: "data_retention_days",
      value: 30,
    },
    {
      evidence_ids: ["evidence_sso_matrix"],
      field: "sso_available",
      value: true,
    },
  ],
  fit_rules: [
    {
      evidence_ids: ["evidence_team_plan"],
      field: "buyer.seat_count",
      value: "10-200",
    },
    {
      evidence_ids: ["evidence_workspace_support"],
      field: "buyer.identity_provider",
      value: ["google_workspace", "microsoft_365"],
    },
  ],
  id: "draft_fixture_d",
  product_id: "product_fixture_d",
  publisher_authority: "PLATFORM_COMPILED",
  revision: 3,
  revision_hash:
    "sha256:6ef651573cb6807db070606022072f95ac693698f7a671cdbcf569a163284f3d",
  state: "SELLER_DRAFT",
  updated_at: "2026-08-02T08:42:00Z",
  validation: {
    gaps: [
      {
        field: "data_retention_days",
        href: "/seller/product-evidence/product_fixture_d?field=data_retention_days",
        id: "gap_retention",
        safe_message:
          "Confirm the current retention value with non-expired supporting evidence.",
      },
    ],
    status: "HAS_GAPS",
  },
};

const STATE_GUIDANCE: Record<
  SellerEvidenceState,
  { heading: string; message: string; tone: Tone }
> = {
  UNCLAIMED: {
    heading: "Not claimed",
    message:
      "Only the public-safe package summary is available. Editing stays unavailable until an authorized claim succeeds.",
    tone: "neutral",
  },
  CLAIM_PENDING: {
    heading: "Claim under review",
    message:
      "The submitted authority proof is preserved. Only actions returned by the server are available while review is pending.",
    tone: "info",
  },
  CLAIM_DENIED: {
    heading: "Claim needs different proof",
    message:
      "The provisional package remains intact. Submit different authority proof only when the server provides that action.",
    tone: "danger",
  },
  SELLER_DRAFT: {
    heading: "Draft in progress",
    message:
      "Resolve validation gaps and stale evidence before freezing this revision for review.",
    tone: "warning",
  },
  VALIDATION_CONFLICT: {
    heading: "Validation conflict",
    message:
      "Conflicting fields block review. Follow the field links below and preserve the last confirmed server revision.",
    tone: "danger",
  },
  IN_REVIEW: {
    heading: "Revision frozen for review",
    message:
      "This exact revision is read-only while its assigned reviewer evaluates the evidence and publication fields.",
    tone: "info",
  },
  CHANGES_REQUESTED: {
    heading: "Changes requested",
    message:
      "Reviewer comments are bound to the frozen revision. A revised draft must be a new server-authorized revision.",
    tone: "warning",
  },
  PUBLISH_READY: {
    heading: "Approved and ready to publish",
    message:
      "The publication preview is immutable. Publishing remains available only to an authorized reviewer.",
    tone: "success",
  },
  PUBLISHED: {
    heading: "Current published Product Evidence",
    message:
      "This Pack version is immutable. Corrections require a new version and never rewrite historical decisions.",
    tone: "success",
  },
  SUPERSEDED: {
    heading: "Historical version",
    message:
      "This version is read-only and retained for audit. Use the current-version link for active Product Evidence.",
    tone: "neutral",
  },
  PUBLICATION_FAILED: {
    heading: "Publication did not complete",
    message:
      "The last safe checkpoint is preserved. Retry or escalate only when the server returns that action.",
    tone: "danger",
  },
};

type Tone = "neutral" | "info" | "warning" | "danger" | "success";
type ProductTab = "pack" | "evidence" | "fit" | "publish" | "activity";

const PRODUCT_TABS: Array<{
  id: ProductTab;
  label: string;
  icon: typeof Package;
}> = [
  { id: "pack", label: "Pack", icon: Package },
  { id: "evidence", label: "Evidence", icon: FileSearch },
  { id: "fit", label: "Fit", icon: ShieldCheck },
  { id: "publish", label: "Publish", icon: FileCheck2 },
  { id: "activity", label: "Activity", icon: Activity },
];

function fixtureViewFor(productId: string): SellerEvidenceView {
  const searchItem = FIXTURE_SEARCH.results.find((item) => item.id === productId);
  if (!searchItem) {
    throw new Error(`No deterministic seller fixture exists for ${productId}`);
  }
  const isPublished = searchItem.state === "PUBLISHED";
  const isUnclaimed = searchItem.state === "UNCLAIMED";

  return {
    activity_metrics: {
      answer_rendered_count: isPublished ? 42 : 18,
      href: `/v1/seller/products/${searchItem.id}/activity-metrics`,
      measurement_label: "OBSERVATIONAL_NOT_CAUSAL",
      observed_self_service_count: isPublished ? 35 : 12,
      seller_handoff_requested_count: isPublished ? 7 : 6,
      window_end: "2026-08-01T00:00:00Z",
      window_start: "2026-07-01T00:00:00Z",
    },
    actor: {
      capabilities: isUnclaimed
        ? ["CLAIM_PRODUCT"]
        : isPublished
          ? ["EXPORT", "VIEW_ACTIVITY_METRICS"]
          : [
              "VIEW_OWN_DRAFT",
              "EDIT_CLAIMS",
              "ADD_EVIDENCE",
              "SUBMIT_REVIEW",
              "VIEW_ACTIVITY_METRICS",
            ],
      role: "SELLER_EDITOR",
    },
    available_actions:
      searchItem.id === "product_fixture_d"
        ? [
            {
              href: "/v1/seller/pack-drafts/draft_fixture_d/submit-review",
              id: "SUBMIT_REVIEW",
              label: "Submit for review",
              method: "POST",
              requires_confirmation: true,
            },
          ]
        : [],
    pack_health: isPublished
      ? {
          complete_claim_count: 12,
          conflict_count: 0,
          required_claim_count: 12,
          stale_claim_count: 0,
          status: "HEALTHY",
        }
      : isUnclaimed
        ? {
            complete_claim_count: 5,
            conflict_count: 0,
            required_claim_count: 12,
            stale_claim_count: 3,
            status: "NEEDS_ATTENTION",
          }
        : {
            complete_claim_count: 9,
            conflict_count: 1,
            required_claim_count: 12,
            stale_claim_count: 1,
            status: "NEEDS_ATTENTION",
          },
    product: {
      current_version: isPublished ? 4 : 3,
      href: `/seller/product-evidence/${searchItem.id}`,
      id: searchItem.id,
      name: searchItem.name,
      seller_state: searchItem.state,
    },
    publisher_authority: {
      label:
        searchItem.publisher_authority === "SELLER_SEALED"
          ? "Published by vendor"
          : searchItem.publisher_authority === "PLATFORM_COMPILED"
            ? "Compiled by Seilnsara"
            : "External, not claimed",
      supporting_copy: AUTHORITY_COPY,
      value: searchItem.publisher_authority,
    },
    reusable_answers: {
      formats: isPublished ? ["JSON", "HTML", "REUSABLE_ANSWER"] : [],
      href: isPublished
        ? `/v1/seller/pack-versions/pack_${searchItem.id}_v4/exports`
        : null,
      published_answer_count: isPublished ? 18 : 0,
      published_version: isPublished ? 4 : null,
    },
    review: null,
    validation: isPublished
      ? { gaps: [], status: "VALID" }
      : {
          gaps: [
            {
              field: "data_retention_days",
              href: `/seller/product-evidence/${searchItem.id}?field=data_retention_days`,
              id: "gap_retention",
              safe_message:
                "Add a current retention value and supporting evidence.",
            },
          ],
          status: "HAS_GAPS",
        },
    version_links: {
      current: `/seller/product-evidence/${searchItem.id}/versions/${isPublished ? 4 : 3}`,
      previous: `/seller/product-evidence/${searchItem.id}/versions/${isPublished ? 3 : 2}`,
    },
  };
}

function fixtureDraftFor(productId: string, draftId: string): SellerPackDraftView {
  return {
    ...FIXTURE_DRAFT,
    id: draftId,
    product_id: productId,
    validation: {
      ...FIXTURE_DRAFT.validation,
      gaps: FIXTURE_DRAFT.validation.gaps.map((gap) => ({
        ...gap,
        href: `/seller/product-evidence/${productId}?field=${gap.field}`,
      })),
    },
  };
}

function sellerRequestHeaders(): Record<string, string> {
  const configured: unknown = sellerEditorDevelopmentHeaders;
  if (typeof configured === "function") {
    return (configured as () => Record<string, string>)();
  }
  return { ...(configured as Record<string, string>) };
}

function useSellerProducts() {
  return useQuery({
    queryKey: ["seller", "products", WEB_DATA_MODE],
    queryFn: async ({ signal }) => {
      if (IS_FIXTURE_MODE) return FIXTURE_SEARCH;
      return getBrowserApiClient().request("seller_evidence_search_products", {
        headers: sellerRequestHeaders(),
        signal,
      });
    },
  });
}

function useSellerProduct(productId: string) {
  return useQuery({
    queryKey: ["seller", "product", productId, WEB_DATA_MODE],
    queryFn: async ({ signal }) => {
      if (IS_FIXTURE_MODE) return fixtureViewFor(productId);
      return getBrowserApiClient().request("seller_evidence_product_view", {
        headers: sellerRequestHeaders(),
        pathParams: { product_id: productId },
        signal,
      });
    },
  });
}

function parseSubmitReviewDraftId(href: string): string | null {
  try {
    const path = new URL(href, "https://seller.local").pathname;
    const match = path.match(
      /^\/v1\/seller\/pack-drafts\/([^/]+)\/submit-review$/,
    );
    return match?.[1] ? decodeURIComponent(match[1]) : null;
  } catch {
    return null;
  }
}

function formatState(value: string): string {
  return value
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "Not recorded";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "Not recorded";
  return new Intl.DateTimeFormat("en", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
    timeZoneName: "short",
  }).format(date);
}

function formatValue(value: SellerEvidenceClaim["value"]): string {
  if (value === null) return "Unknown";
  if (Array.isArray(value)) return value.map(formatState).join(", ");
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

function toneClass(tone: Tone): string {
  if (tone === "danger") return styles.toneDanger;
  if (tone === "warning") return styles.toneWarning;
  if (tone === "success") return styles.toneSuccess;
  if (tone === "info") return styles.toneInfo;
  return styles.toneNeutral;
}

function SellerShell({
  active,
  children,
}: {
  active: "home" | "search" | "product";
  children: ReactNode;
}) {
  return (
    <div className={styles.shell}>
      <aside className={styles.rail} aria-label="SEIL workspace navigation">
        <div>
          <Link className={styles.wordmark} href="/seller" aria-label="SEIL home">
            SEIL
          </Link>
          <p className={styles.railDescriptor}>Product Evidence</p>
        </div>

        <nav className={styles.nav} aria-label="Seller">
          <Link
            className={active === "home" ? styles.navActive : styles.navItem}
            href="/seller"
          >
            <Home aria-hidden="true" />
            Overview
          </Link>
          <Link
            className={active === "search" ? styles.navActive : styles.navItem}
            href="/seller/products/search"
          >
            <Search aria-hidden="true" />
            Find a product
          </Link>
          {active === "product" ? (
            <span className={styles.navActive} aria-current="page">
              <Package aria-hidden="true" />
              Product workspace
            </span>
          ) : null}
        </nav>

        <div className={styles.boundaryNote}>
          <ShieldCheck aria-hidden="true" />
          <div>
            <strong>Private seller workspace</strong>
            <span>Only reviewed, allowlisted fields can be published.</span>
          </div>
        </div>
      </aside>

      <div className={styles.workspace}>
        {IS_FIXTURE_MODE ? <FixtureBanner /> : null}
        <main id="seller-main" className={styles.canvas}>
          {children}
        </main>
      </div>
    </div>
  );
}

function FixtureBanner() {
  return (
    <div className={styles.fixtureBanner} role="status">
      <FlaskConical aria-hidden="true" />
      <strong>Development fixture</strong>
      <span>
        Local deterministic data only. No production seller, evidence provider,
        publication, or marketplace integration is connected.
      </span>
    </div>
  );
}

function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className={styles.pageHeader}>
      <div>
        <p className={styles.eyebrow}>{eyebrow}</p>
        <h1>{title}</h1>
        <p className={styles.pageDescription}>{description}</p>
      </div>
      {action ? <div className={styles.headerAction}>{action}</div> : null}
    </header>
  );
}

function StatusPill({ children, tone }: { children: ReactNode; tone: Tone }) {
  return (
    <span className={`${styles.statusPill} ${toneClass(tone)}`}>
      {children}
    </span>
  );
}

function SafeError({ retry }: { retry: () => void }) {
  return (
    <section className={styles.safeError} role="alert">
      <AlertTriangle aria-hidden="true" />
      <div>
        <h2>Seller data could not be loaded</h2>
        <p>
          No fixture data was substituted. The last confirmed server state, if
          any, remains unchanged.
        </p>
        <button type="button" onClick={retry}>
          <RefreshCw aria-hidden="true" />
          Try again
        </button>
      </div>
    </section>
  );
}

function LoadingState({ label }: { label: string }) {
  return (
    <div className={styles.loadingState} role="status" aria-live="polite">
      <RefreshCw className={styles.spin} aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

function ProductCard({ item }: { item: SellerProductSearchItem }) {
  const guidance = STATE_GUIDANCE[item.state];
  const authorityLabel =
    item.publisher_authority === "SELLER_SEALED"
      ? "Published by vendor"
      : item.publisher_authority === "PLATFORM_COMPILED"
        ? "Compiled by Seilnsara"
        : "External, not claimed";

  return (
    <article className={styles.productCard}>
      <div className={styles.cardHeading}>
        <Package aria-hidden="true" />
        <div>
          <p>{item.category}</p>
          <h2>{item.name}</h2>
        </div>
      </div>
      <p className={styles.productSummary}>{item.public_summary}</p>
      <div className={styles.cardMeta}>
        <StatusPill tone={guidance.tone}>{formatState(item.state)}</StatusPill>
        <span>{authorityLabel}</span>
      </div>
      <Link className={styles.cardLink} href={item.href}>
        Open Product Evidence
        <ArrowRight aria-hidden="true" />
      </Link>
    </article>
  );
}

export function SellerHome() {
  const products = useSellerProducts();
  const attention =
    products.data?.results.filter(
      (item) => item.state !== "PUBLISHED" && item.state !== "SUPERSEDED",
    ) ?? [];

  return (
    <SellerShell active="home">
      <PageHeader
        eyebrow="SEIL seller workspace"
        title="Product Evidence"
        description="Maintain accurate product truth, resolve evidence gaps, and submit an exact revision for review."
        action={
          <Link className={styles.primaryLink} href="/seller/products/search">
            <Search aria-hidden="true" />
            Find a product
          </Link>
        }
      />

      {products.isPending ? (
        <LoadingState label="Loading authorized seller products" />
      ) : products.isError ? (
        <SafeError retry={() => void products.refetch()} />
      ) : (
        <>
          <section className={styles.attentionSummary} aria-labelledby="attention-title">
            <div>
              <p className={styles.sectionKicker}>Current queue</p>
              <h2 id="attention-title">Products needing attention</h2>
              <p>
                This list uses public-safe search state. Private draft details
                load only inside an authorized product workspace.
              </p>
            </div>
            <div className={styles.attentionCount}>
              <strong>{attention.length}</strong>
              <span>open items</span>
            </div>
          </section>

          {attention.length > 0 ? (
            <section className={styles.cardGrid} aria-label="Products needing attention">
              {attention.map((item) => (
                <ProductCard item={item} key={item.id} />
              ))}
            </section>
          ) : (
            <section className={styles.emptyState}>
              <CheckCircle2 aria-hidden="true" />
              <h2>No product currently needs attention</h2>
              <p>Search for a provisional product or return when a review task is assigned.</p>
              <Link href="/seller/products/search">Search products</Link>
            </section>
          )}
        </>
      )}
    </SellerShell>
  );
}

export function SellerProductSearch() {
  const products = useSellerProducts();
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return products.data?.results ?? [];
    return (products.data?.results ?? []).filter((item) =>
      [item.name, item.category, item.public_summary]
        .join(" ")
        .toLowerCase()
        .includes(normalized),
    );
  }, [products.data, query]);

  return (
    <SellerShell active="search">
      <PageHeader
        eyebrow="Public-safe registry search"
        title="Find a product"
        description="Locate an existing provisional product identity. Search results never expose a private draft or seller source."
      />

      <label className={styles.searchField}>
        <span className="visually-hidden">Search products</span>
        <Search aria-hidden="true" />
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search product name, category, or public summary"
        />
      </label>

      {products.isPending ? (
        <LoadingState label="Searching the public-safe product registry" />
      ) : products.isError ? (
        <SafeError retry={() => void products.refetch()} />
      ) : filtered.length > 0 ? (
        <section className={styles.cardGrid} aria-label="Product search results">
          {filtered.map((item) => (
            <ProductCard item={item} key={item.id} />
          ))}
        </section>
      ) : (
        <section className={styles.emptyState}>
          <FileSearch aria-hidden="true" />
          <h2>No matching public product</h2>
          <p>Try a product name or category. No private records were searched.</p>
        </section>
      )}
    </SellerShell>
  );
}

function HealthPanel({ view }: { view: SellerEvidenceView }) {
  const health = view.pack_health;
  const percent = health.required_claim_count
    ? Math.min(
        100,
        Math.round(
          (health.complete_claim_count / health.required_claim_count) * 100,
        ),
      )
    : 100;

  return (
    <section className={styles.healthPanel} aria-labelledby="health-heading">
      <div className={styles.panelHeading}>
        <div>
          <p className={styles.sectionKicker}>Pack health</p>
          <h2 id="health-heading">Publication coverage</h2>
        </div>
        <StatusPill
          tone={
            health.status === "HEALTHY"
              ? "success"
              : health.status === "BLOCKED"
                ? "danger"
                : "warning"
          }
        >
          {formatState(health.status)}
        </StatusPill>
      </div>
      <progress max={100} value={percent} aria-label={`${percent}% of required claims complete`} />
      <div className={styles.healthGrid}>
        <div>
          <strong>{health.complete_claim_count}</strong>
          <span>complete</span>
        </div>
        <div>
          <strong>{health.required_claim_count}</strong>
          <span>required</span>
        </div>
        <div>
          <strong>{health.stale_claim_count}</strong>
          <span>stale</span>
        </div>
        <div>
          <strong>{health.conflict_count}</strong>
          <span>conflicts</span>
        </div>
      </div>
    </section>
  );
}

function ValidationPanel({ view }: { view: SellerEvidenceView }) {
  const validation = view.validation;
  return (
    <section className={styles.recordPanel} aria-labelledby="validation-heading">
      <div className={styles.panelHeading}>
        <div>
          <p className={styles.sectionKicker}>Validation</p>
          <h2 id="validation-heading">Field-linked recovery</h2>
        </div>
        <StatusPill
          tone={
            validation.status === "VALID"
              ? "success"
              : validation.status === "CONFLICT"
                ? "danger"
                : validation.status === "HAS_GAPS"
                  ? "warning"
                  : "neutral"
          }
        >
          {formatState(validation.status)}
        </StatusPill>
      </div>

      {validation.gaps.length ? (
        <ul className={styles.gapList}>
          {validation.gaps.map((gap) => (
            <li key={gap.id}>
              <AlertTriangle aria-hidden="true" />
              <div>
                <code>{gap.field}</code>
                <p>{gap.safe_message}</p>
              </div>
              <Link href={gap.href}>Open field</Link>
            </li>
          ))}
        </ul>
      ) : (
        <div className={styles.verifiedEmpty}>
          <CheckCircle2 aria-hidden="true" />
          <p>No validation gaps are present in this server projection.</p>
        </div>
      )}
    </section>
  );
}

function ClaimRows({
  claims,
  empty,
}: {
  claims: SellerEvidenceClaim[];
  empty: string;
}) {
  if (!claims.length) return <p className={styles.quietEmpty}>{empty}</p>;
  return (
    <dl className={styles.claimRows}>
      {claims.map((claim) => (
        <div key={`${claim.field}-${String(claim.value)}`}>
          <dt>{formatState(claim.field.replaceAll(".", "_"))}</dt>
          <dd>
            <strong>{formatValue(claim.value)}</strong>
            <span>
              {claim.evidence_ids.length} evidence reference
              {claim.evidence_ids.length === 1 ? "" : "s"}
            </span>
          </dd>
        </div>
      ))}
    </dl>
  );
}

function PackTab({ view }: { view: SellerEvidenceView }) {
  return (
    <div className={styles.twoColumn}>
      <HealthPanel view={view} />
      <section className={styles.recordPanel} aria-labelledby="authority-heading">
        <div className={styles.panelHeading}>
          <div>
            <p className={styles.sectionKicker}>Publisher authority</p>
            <h2 id="authority-heading">{view.publisher_authority.label}</h2>
          </div>
          <ShieldCheck aria-hidden="true" />
        </div>
        <p className={styles.authorityCopy}>
          {view.publisher_authority.supporting_copy}
        </p>
        <dl className={styles.factList}>
          <div>
            <dt>Product Evidence version</dt>
            <dd>v{view.product.current_version}</dd>
          </div>
          <div>
            <dt>Authority code</dt>
            <dd><code>{view.publisher_authority.value}</code></dd>
          </div>
          <div>
            <dt>Current role</dt>
            <dd>{formatState(view.actor.role)}</dd>
          </div>
        </dl>
      </section>
      <ValidationPanel view={view} />
    </div>
  );
}

function EvidenceTab({ view }: { view: SellerEvidenceView }) {
  return (
    <div className={styles.twoColumn}>
      <ValidationPanel view={view} />
      <section className={styles.recordPanel} aria-labelledby="freshness-heading">
        <div className={styles.panelHeading}>
          <div>
            <p className={styles.sectionKicker}>Evidence state</p>
            <h2 id="freshness-heading">Freshness and conflicts</h2>
          </div>
          <FileSearch aria-hidden="true" />
        </div>
        <dl className={styles.factList}>
          <div>
            <dt>Stale claims</dt>
            <dd>{view.pack_health.stale_claim_count}</dd>
          </div>
          <div>
            <dt>Conflicting claims</dt>
            <dd>{view.pack_health.conflict_count}</dd>
          </div>
          <div>
            <dt>Verification</dt>
            <dd>Separate from publisher authority</dd>
          </div>
        </dl>
        <p className={styles.panelNote}>
          Retrieved evidence is not automatically verified. Source, scope,
          verifier, freshness, and claim state remain separate fields.
        </p>
      </section>
    </div>
  );
}

function FitTab({
  draft,
  draftPending,
  draftError,
  retryDraft,
}: {
  draft?: SellerPackDraftView;
  draftPending: boolean;
  draftError: boolean;
  retryDraft: () => void;
}) {
  if (draftPending) return <LoadingState label="Loading the authorized draft rules" />;
  if (draftError) return <SafeError retry={retryDraft} />;
  if (!draft) {
    return (
      <section className={styles.emptyState}>
        <ShieldCheck aria-hidden="true" />
        <h2>No editable fit draft was supplied</h2>
        <p>
          Fit and anti-fit controls remain absent until the server provides an
          authorized draft action.
        </p>
      </section>
    );
  }

  return (
    <div className={styles.twoColumn}>
      <section className={styles.recordPanel} aria-labelledby="fit-rules-heading">
        <div className={styles.panelHeading}>
          <div>
            <p className={styles.sectionKicker}>Fit rules</p>
            <h2 id="fit-rules-heading">Supported conditions</h2>
          </div>
          <span className={styles.countBadge}>{draft.fit_rules.length}</span>
        </div>
        <ClaimRows
          claims={draft.fit_rules}
          empty="No fit rules are present in this draft revision."
        />
      </section>
      <section className={styles.recordPanel} aria-labelledby="anti-fit-heading">
        <div className={styles.panelHeading}>
          <div>
            <p className={styles.sectionKicker}>Anti-fit rules</p>
            <h2 id="anti-fit-heading">Vendor-not-supported conditions</h2>
          </div>
          <span className={styles.countBadge}>{draft.anti_fit_rules.length}</span>
        </div>
        <ClaimRows
          claims={draft.anti_fit_rules}
          empty="No anti-fit rules are present in this draft revision."
        />
        <p className={styles.panelNote}>
          Published anti-fit rules remain executable without a live seller and
          cannot be suppressed to improve conversion.
        </p>
      </section>
    </div>
  );
}

function ReviewPanel({ view }: { view: SellerEvidenceView }) {
  const review = view.review;
  return (
    <section className={styles.recordPanel} aria-labelledby="review-heading">
      <div className={styles.panelHeading}>
        <div>
          <p className={styles.sectionKicker}>Review</p>
          <h2 id="review-heading">Exact revision history</h2>
        </div>
        <FileCheck2 aria-hidden="true" />
      </div>
      {review ? (
        <dl className={styles.factList}>
          <div>
            <dt>Status</dt>
            <dd>{formatState(review.status)}</dd>
          </div>
          <div>
            <dt>Reviewer role</dt>
            <dd>{formatState(review.reviewer_role)}</dd>
          </div>
          <div>
            <dt>Decision</dt>
            <dd>{review.decision ? formatState(review.decision) : "Pending"}</dd>
          </div>
          <div>
            <dt>Recorded</dt>
            <dd>{formatDateTime(review.recorded_at)}</dd>
          </div>
          <div className={styles.fullFact}>
            <dt>Revision hash</dt>
            <dd><code>{review.revision_hash}</code></dd>
          </div>
          {review.reason ? (
            <div className={styles.fullFact}>
              <dt>Safe reason</dt>
              <dd>{review.reason}</dd>
            </div>
          ) : null}
        </dl>
      ) : (
        <p className={styles.quietEmpty}>
          No review decision is attached to this seller projection.
        </p>
      )}
    </section>
  );
}

function ExportsPanel({ view }: { view: SellerEvidenceView }) {
  return (
    <section className={styles.recordPanel} aria-labelledby="exports-heading">
      <div className={styles.panelHeading}>
        <div>
          <p className={styles.sectionKicker}>Published outputs</p>
          <h2 id="exports-heading">Reusable answer and export</h2>
        </div>
        <Download aria-hidden="true" />
      </div>
      {view.reusable_answers.published_version ? (
        <>
          <dl className={styles.factList}>
            <div>
              <dt>Published version</dt>
              <dd>v{view.reusable_answers.published_version}</dd>
            </div>
            <div>
              <dt>Answer renders</dt>
              <dd>{view.reusable_answers.published_answer_count}</dd>
            </div>
          </dl>
          <div className={styles.formatList} aria-label="Available export formats">
            {view.reusable_answers.formats.map((format) => (
              <span key={format}>{formatState(format)}</span>
            ))}
          </div>
          {view.reusable_answers.href ? (
            <Link className={styles.secondaryLink} href={view.reusable_answers.href}>
              Review hash-bound exports
              <ArrowRight aria-hidden="true" />
            </Link>
          ) : null}
          <p className={styles.panelNote}>
            Exports contain published fields only. Generated reusable answers
            cannot add claims.
          </p>
        </>
      ) : (
        <p className={styles.quietEmpty}>
          Exports appear only after an immutable Pack version is published.
        </p>
      )}
    </section>
  );
}

function PublishTab({
  view,
  draft,
  draftPending,
  canSubmit,
  openConfirmation,
}: {
  view: SellerEvidenceView;
  draft?: SellerPackDraftView;
  draftPending: boolean;
  canSubmit: boolean;
  openConfirmation: () => void;
}) {
  return (
    <div className={styles.twoColumn}>
      <ReviewPanel view={view} />
      <ExportsPanel view={view} />
      <section className={styles.actionPanel} aria-labelledby="next-action-heading">
        <div>
          <p className={styles.sectionKicker}>Server-authorized next action</p>
          <h2 id="next-action-heading">
            {canSubmit ? "Submit this revision for review" : "No supported mutation available"}
          </h2>
          <p>
            {canSubmit
              ? "Submission freezes the exact draft revision and hash shown here. It does not publish Product Evidence."
              : "Unsupported claim, evidence, review, publication, and suspension controls are intentionally omitted."}
          </p>
          {draft ? (
            <code className={styles.hashLine}>{draft.revision_hash}</code>
          ) : null}
        </div>
        {canSubmit ? (
          <button
            className={styles.primaryButton}
            type="button"
            onClick={openConfirmation}
            disabled={draftPending || !draft}
          >
            <Send aria-hidden="true" />
            Submit for review
          </button>
        ) : null}
      </section>
    </div>
  );
}

function ActivityTab({ view }: { view: SellerEvidenceView }) {
  const metrics = view.activity_metrics;
  return (
    <div className={styles.twoColumn}>
      <section className={styles.metricsPanel} aria-labelledby="activity-heading">
        <div className={styles.panelHeading}>
          <div>
            <p className={styles.sectionKicker}>Artifact activity</p>
            <h2 id="activity-heading">Observed self-service</h2>
          </div>
          <Activity aria-hidden="true" />
        </div>
        <div className={styles.metricGrid}>
          <div>
            <strong>{metrics.answer_rendered_count}</strong>
            <span>answer renders</span>
          </div>
          <div>
            <strong>{metrics.seller_handoff_requested_count}</strong>
            <span>handoff requests</span>
          </div>
          <div>
            <strong>{metrics.observed_self_service_count}</strong>
            <span>observed self-service</span>
          </div>
        </div>
        <p className={styles.measurementWindow}>
          <Clock aria-hidden="true" />
          {formatDateTime(metrics.window_start)} to {formatDateTime(metrics.window_end)}
        </p>
      </section>
      <section className={styles.recordPanel} aria-labelledby="metric-definition-heading">
        <div className={styles.panelHeading}>
          <div>
            <p className={styles.sectionKicker}>Measurement definition</p>
            <h2 id="metric-definition-heading">Observational, not causal</h2>
          </div>
          <Info aria-hidden="true" />
        </div>
        <p className={styles.authorityCopy}>
          A published-answer render counts at most once per tenant, session, and
          question fingerprint within 24 hours. It counts as observed
          self-service only when no seller handoff follows in that session.
        </p>
        <p className={styles.panelNote}>
          This is not proven question deflection, labor savings, or an outcome
          claim.
        </p>
      </section>
    </div>
  );
}

function SubmitReviewDialog({
  draft,
  pending,
  onCancel,
  onConfirm,
}: {
  draft: SellerPackDraftView;
  pending: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !pending) onCancel();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onCancel, pending]);

  return (
    <div className={styles.dialogBackdrop}>
      <section
        className={styles.dialog}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="submit-review-title"
        aria-describedby="submit-review-description"
      >
        <div className={styles.dialogHeading}>
          <div>
            <p className={styles.sectionKicker}>Consequential action</p>
            <h2 id="submit-review-title">Submit revision {draft.revision} for review?</h2>
          </div>
          <button
            className={styles.iconButton}
            type="button"
            onClick={onCancel}
            disabled={pending}
            aria-label="Close"
          >
            <X aria-hidden="true" />
          </button>
        </div>
        <p id="submit-review-description">
          This freezes the exact revision for reviewer approval. It does not
          publish the Pack and it does not verify unsupported claims.
        </p>
        <code className={styles.dialogHash}>{draft.revision_hash}</code>
        <div className={styles.dialogActions}>
          <button
            className={styles.secondaryButton}
            type="button"
            onClick={onCancel}
            disabled={pending}
          >
            Keep editing
          </button>
          <button
            className={styles.primaryButton}
            type="button"
            onClick={onConfirm}
            disabled={pending}
            autoFocus
          >
            {pending ? <RefreshCw className={styles.spin} aria-hidden="true" /> : <Send aria-hidden="true" />}
            {pending ? "Submitting" : "Submit exact revision"}
          </button>
        </div>
      </section>
    </div>
  );
}

export function SellerProductWorkspace({ productId }: { productId: string }) {
  const [activeTab, setActiveTab] = useState<ProductTab>("pack");
  const [confirmSubmit, setConfirmSubmit] = useState(false);
  const [submitAcknowledged, setSubmitAcknowledged] = useState(false);
  const queryClient = useQueryClient();
  const product = useSellerProduct(productId);

  const submitAction = product.data?.available_actions.find(
    (action) => action.id === "SUBMIT_REVIEW" && action.method === "POST",
  );
  const draftId = submitAction ? parseSubmitReviewDraftId(submitAction.href) : null;
  const draft = useQuery({
    enabled: Boolean(draftId),
    queryKey: ["seller", "draft", draftId, WEB_DATA_MODE],
    queryFn: async ({ signal }) => {
      if (!draftId) throw new Error("No server-authorized draft reference");
      if (IS_FIXTURE_MODE) return fixtureDraftFor(productId, draftId);
      return getBrowserApiClient().request("seller_evidence_get_draft", {
        headers: sellerRequestHeaders(),
        pathParams: { draft_id: draftId },
        signal,
      });
    },
  });

  const submitReview = useMutation({
    mutationFn: async () => {
      if (!draftId || !draft.data || !submitAction) {
        throw new Error("The server did not provide a safe submit-review action");
      }
      if (IS_FIXTURE_MODE) {
        return { ...draft.data, state: "IN_REVIEW" as const };
      }
      return getBrowserApiClient().request("seller_evidence_submit_review", {
        body: { revision_hash: draft.data.revision_hash },
        headers: sellerRequestHeaders(),
        idempotencyKey: createIdempotencyKey("seller-submit-review"),
        pathParams: { draft_id: draftId },
      });
    },
    onSuccess: (nextDraft) => {
      setConfirmSubmit(false);
      setSubmitAcknowledged(true);
      queryClient.setQueryData(
        ["seller", "draft", draftId, WEB_DATA_MODE],
        nextDraft,
      );
      if (IS_FIXTURE_MODE) {
        queryClient.setQueryData<SellerEvidenceView>(
          ["seller", "product", productId, WEB_DATA_MODE],
          (current) =>
            current
              ? {
                  ...current,
                  available_actions: current.available_actions.filter(
                    (action) => action.id !== "SUBMIT_REVIEW",
                  ),
                  product: { ...current.product, seller_state: "IN_REVIEW" },
                  review: {
                    decision: null,
                    reason: null,
                    recorded_at: null,
                    review_id: "review_fixture_d",
                    reviewer_role: "SELLER_REVIEWER",
                    revision_hash: nextDraft.revision_hash,
                    status: "PENDING",
                  },
                }
              : current,
        );
      } else {
        void queryClient.invalidateQueries({
          queryKey: ["seller", "product", productId, WEB_DATA_MODE],
        });
      }
    },
  });

  if (product.isPending) {
    return (
      <SellerShell active="product">
        <LoadingState label="Loading the authorized Product Evidence view" />
      </SellerShell>
    );
  }

  if (product.isError || !product.data) {
    return (
      <SellerShell active="product">
        <SafeError retry={() => void product.refetch()} />
      </SellerShell>
    );
  }

  const view = product.data;
  const guidance = STATE_GUIDANCE[view.product.seller_state];
  const canSubmit = Boolean(submitAction && draftId && draft.data);

  return (
    <SellerShell active="product">
      <PageHeader
        eyebrow={`Product Evidence / v${view.product.current_version}`}
        title={view.product.name}
        description="Role-filtered product truth, validation, review, exports, and artifact activity."
        action={
          <StatusPill tone={guidance.tone}>
            {formatState(view.product.seller_state)}
          </StatusPill>
        }
      />

      <section
        className={`${styles.stateBanner} ${toneClass(guidance.tone)}`}
        aria-labelledby="seller-state-heading"
      >
        {guidance.tone === "danger" || guidance.tone === "warning" ? (
          <AlertTriangle aria-hidden="true" />
        ) : guidance.tone === "success" ? (
          <CheckCircle2 aria-hidden="true" />
        ) : (
          <Info aria-hidden="true" />
        )}
        <div>
          <h2 id="seller-state-heading">{guidance.heading}</h2>
          <p>{guidance.message}</p>
        </div>
      </section>

      {submitAcknowledged ? (
        <section className={`${styles.stateBanner} ${styles.toneSuccess}`} role="status">
          <CheckCircle2 aria-hidden="true" />
          <div>
            <h2>Revision submitted</h2>
            <p>The exact revision is now frozen for review. It has not been published.</p>
          </div>
        </section>
      ) : null}

      {submitReview.isError ? (
        <section className={`${styles.stateBanner} ${styles.toneDanger}`} role="alert">
          <AlertTriangle aria-hidden="true" />
          <div>
            <h2>Review submission did not complete</h2>
            <p>
              The draft remains at its last confirmed revision. Reopen the
              confirmation only after checking the current server state.
            </p>
          </div>
        </section>
      ) : null}

      <div className={styles.productToolbar}>
        <div>
          <span>{view.publisher_authority.label}</span>
          <code>{view.product.id}</code>
        </div>
        <div className={styles.versionLinks}>
          {view.version_links.previous ? (
            <Link href={view.version_links.previous}>Previous version</Link>
          ) : null}
          <Link href={view.version_links.current}>Current version</Link>
        </div>
      </div>

      <div className={styles.tabs} role="tablist" aria-label="Product Evidence sections">
        {PRODUCT_TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            id={`seller-tab-${id}`}
            type="button"
            role="tab"
            aria-selected={activeTab === id}
            aria-controls={`seller-panel-${id}`}
            className={activeTab === id ? styles.tabActive : styles.tab}
            onClick={() => setActiveTab(id)}
          >
            <Icon aria-hidden="true" />
            {label}
          </button>
        ))}
      </div>

      <section
        className={styles.tabPanel}
        id={`seller-panel-${activeTab}`}
        role="tabpanel"
        aria-labelledby={`seller-tab-${activeTab}`}
        tabIndex={0}
      >
        {activeTab === "pack" ? <PackTab view={view} /> : null}
        {activeTab === "evidence" ? <EvidenceTab view={view} /> : null}
        {activeTab === "fit" ? (
          <FitTab
            draft={draft.data}
            draftPending={draft.isPending && Boolean(draftId)}
            draftError={draft.isError}
            retryDraft={() => void draft.refetch()}
          />
        ) : null}
        {activeTab === "publish" ? (
          <PublishTab
            view={view}
            draft={draft.data}
            draftPending={draft.isPending && Boolean(draftId)}
            canSubmit={canSubmit}
            openConfirmation={() => setConfirmSubmit(true)}
          />
        ) : null}
        {activeTab === "activity" ? <ActivityTab view={view} /> : null}
      </section>

      {confirmSubmit && draft.data ? (
        <SubmitReviewDialog
          draft={draft.data}
          pending={submitReview.isPending}
          onCancel={() => setConfirmSubmit(false)}
          onConfirm={() => submitReview.mutate()}
        />
      ) : null}
    </SellerShell>
  );
}
