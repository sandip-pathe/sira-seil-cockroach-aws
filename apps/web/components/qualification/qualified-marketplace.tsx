"use client";

import type { QualificationIntegrityView, QualificationMissionView } from "@sira/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Archive,
  BadgeCheck,
  BookOpen,
  Check,
  CircleAlert,
  Database,
  GitCompareArrows,
  LoaderCircle,
  LockKeyhole,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";

import {
  buyerDevelopmentHeaders,
  createIdempotencyKey,
  getBrowserApiClient,
  sellerEditorDevelopmentHeaders,
} from "@/lib/api";

import styles from "./qualified-marketplace.module.css";

type JsonMap = Record<string, unknown>;

function text(value: unknown, fallback = "—"): string {
  return typeof value === "string" && value ? value : fallback;
}

function number(value: unknown): number {
  return typeof value === "number" ? value : 0;
}

function array(value: unknown): JsonMap[] {
  return Array.isArray(value)
    ? value.filter((item): item is JsonMap => typeof item === "object" && item !== null)
    : [];
}

function map(value: unknown): JsonMap {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as JsonMap)
    : {};
}

function shortHash(value: unknown): string {
  const rendered = text(value);
  return rendered.length > 24 ? `${rendered.slice(0, 14)}…${rendered.slice(-8)}` : rendered;
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "The request could not be completed. Reload and try again.";
}

function StateBadge({ value }: { value: string }) {
  const normalized = value.toUpperCase();
  const stateClass = normalized === "PASS" || normalized === "COMPLETED" || normalized === "INTRODUCED"
    ? styles.statePass
    : normalized === "FAIL" || normalized === "FAILED" || normalized === "STALE"
      ? styles.stateFail
      : "";
  return <span className={`${styles.stateBadge} ${stateClass}`}>{value.replaceAll("_", " ")}</span>;
}

function MarketplaceShell({ children }: { children: ReactNode }) {
  return (
    <main className={styles.page}>
      <div className={styles.shell}>
        <nav className={styles.nav} aria-label="Marketplace navigation">
          <Link className={styles.brand} href="/sira">
            <span className={styles.brandMark}>S+S</span>
            SIRA / SEIL
          </Link>
          <div className={styles.navLinks}>
            <Link className={styles.navLink} href="/home">Workspace</Link>
            <Link className={styles.navLink} href="/seil">Seller desk</Link>
            <Link className={styles.navLink} href="/sira">New mission</Link>
          </div>
        </nav>
        {children}
      </div>
    </main>
  );
}

function LoadingPanel() {
  return (
    <div
      className={styles.skeleton}
      role="status"
      aria-label="Loading current marketplace state"
    />
  );
}

function ErrorPanel({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <div className={styles.error} role="alert">
      <strong>Current state is unavailable.</strong> {errorMessage(error)}
      {retry ? (
        <div className={styles.buttonRow}>
          <button className={styles.secondaryButton} type="button" onClick={retry}>
            <RefreshCw size={15} /> Retry
          </button>
        </div>
      ) : null}
    </div>
  );
}

export function QualificationHome() {
  const router = useRouter();
  const [company, setCompany] = useState("Northstar Labs");
  const [category, setCategory] = useState("meeting intelligence");
  const [goal, setGoal] = useState(
    "Select an EU-hosted meeting intelligence platform for our 40-person sales team.",
  );
  const [budget, setBudget] = useState("25000");
  const [selectedContext, setSelectedContext] = useState<string[]>([]);
  const contextInitialized = useRef(false);
  const context = useQuery({
    queryKey: ["company-context", "active"],
    queryFn: () => getBrowserApiClient().request("qualification_list_company_context", {
      headers: buyerDevelopmentHeaders,
      query: { include_retired: false },
    }),
  });
  useEffect(() => {
    if (!contextInitialized.current && context.data) {
      setSelectedContext(context.data.items.map((item) => text(item.id)).filter(Boolean));
      contextInitialized.current = true;
    }
  }, [context.data]);

  const create = useMutation({
    mutationFn: () => getBrowserApiClient().request("qualification_create_mission", {
      headers: buyerDevelopmentHeaders,
      idempotencyKey: createIdempotencyKey("qualification-mission"),
      body: {
        buyer_context: { company, annual_budget: budget, decision_owner: "Revenue operations" },
        company_context_item_ids: selectedContext,
        requirement_brief: {
          category,
          goal,
          seller_visible_requirements: {
            hosting_region: "EU",
            seat_count: 40,
            buying_stage: "qualified evaluation",
          },
          criteria: [
            {
              id: "data_residency",
              label: "EU data residency",
              requirement: "Customer data must remain in the European Union.",
              priority: "MUST",
            },
            {
              id: "sales_workflow",
              label: "Sales workflow fit",
              requirement: "The product must support a 40-person sales team.",
              priority: "SHOULD",
            },
          ],
        },
        procurement_policy: {
          human_approval: true,
          maximum_annual_cost: budget,
          evidence_required: true,
        },
      },
    }),
    onSuccess: (result) => router.push(`/sira/missions/${result.resource_id}`),
  });

  return (
    <MarketplaceShell>
      <div className={styles.hero}>
        <section>
          <p className={styles.eyebrow}><Sparkles size={15} /> Qualified agent marketplace</p>
          <h1 className={styles.title}>Buying decisions that stay true while agents work.</h1>
          <p className={styles.lead}>
            SIRA qualifies the market. SEIL answers with seller-owned evidence. CockroachDB makes
            stale, duplicated, or lost decisions structurally impossible.
          </p>
          <div className={styles.proofRail}>
            <div className={styles.proofItem}>
              <span className={styles.proofIcon}><Database size={17} /></span>
              <div><strong>One serializable decision state</strong><span>Evidence versions, retries, consent, and effects share a durable transaction story.</span></div>
            </div>
            <div className={styles.proofItem}>
              <span className={styles.proofIcon}><GitCompareArrows size={17} /></span>
              <div><strong>Stale work replaces itself</strong><span>If evidence changes mid-run, the old attempt cannot finalize and one replacement starts.</span></div>
            </div>
            <div className={styles.proofItem}>
              <span className={styles.proofIcon}><LockKeyhole size={17} /></span>
              <div><strong>Disclosure by contract</strong><span>The seller receives only the buyer-approved requirement projection—never private context.</span></div>
            </div>
          </div>
        </section>

        <div className={`${styles.card} ${styles.formCard}`}>
          <div className={styles.formHead}>
            <h2>Start a buying mission</h2>
            <span className={styles.stepBadge}>Human authored</span>
          </div>
          <div className={styles.field}>
            <label htmlFor="company">Company</label>
            <input id="company" value={company} onChange={(event) => setCompany(event.target.value)} required maxLength={120} />
          </div>
          <div className={styles.field}>
            <div className={styles.fieldLabelRow}>
              <label>Company memory</label>
              <Link className={styles.inlineLink} href="/sira/company-memory">Manage</Link>
            </div>
            {context.isLoading ? <span className={styles.fieldHint}>Loading durable context...</span> : null}
            {context.data?.items.length === 0 ? (
              <span className={styles.fieldHint}>No saved context yet. The mission can still use its private one-time brief.</span>
            ) : (
              <div className={styles.contextPicker}>
                {context.data?.items.map((item) => {
                  const id = text(item.id);
                  return (
                    <label className={styles.contextChoice} key={id}>
                      <input
                        type="checkbox"
                        checked={selectedContext.includes(id)}
                        onChange={(event) => setSelectedContext((current) => event.target.checked
                          ? [...current, id]
                          : current.filter((value) => value !== id))}
                      />
                      <span><strong>{text(item.label)}</strong><small>{text(item.kind)} · v{number(item.current_version)}</small></span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>
          <div className={styles.field}>
            <label htmlFor="category">Category</label>
            <input id="category" value={category} onChange={(event) => setCategory(event.target.value)} required minLength={2} maxLength={80} />
          </div>
          <div className={styles.field}>
            <label htmlFor="goal">What must the purchase achieve?</label>
            <textarea id="goal" value={goal} onChange={(event) => setGoal(event.target.value)} required minLength={10} maxLength={2000} />
            <span className={styles.fieldHint}>Private context remains inside the buyer tenant.</span>
          </div>
          <div className={styles.field}>
            <label htmlFor="budget">Annual budget (USD)</label>
            <input id="budget" inputMode="numeric" value={budget} onChange={(event) => setBudget(event.target.value.replace(/[^0-9]/g, ""))} required />
          </div>
          {create.error ? <ErrorPanel error={create.error} /> : null}
          <button
            className={`${styles.button} ${styles.fullButton}`}
            type="button"
            disabled={create.isPending || !company || category.length < 2 || goal.length < 10 || !budget}
            onClick={() => create.mutate()}
          >
            {create.isPending ? <LoaderCircle size={17} aria-hidden /> : <Sparkles size={17} />}
            {create.isPending ? "Committing mission…" : "Commit mission to CockroachDB"}
          </button>
        </div>
      </div>
    </MarketplaceShell>
  );
}

export function CompanyContextManager() {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<"REQUIREMENT" | "CONSTRAINT" | "STACK" | "POLICY" | "PREFERENCE" | "NOTE">("CONSTRAINT");
  const [label, setLabel] = useState("");
  const [statement, setStatement] = useState("");
  const [editing, setEditing] = useState<JsonMap | null>(null);
  const context = useQuery({
    queryKey: ["company-context", "all"],
    queryFn: () => getBrowserApiClient().request("qualification_list_company_context", {
      headers: buyerDevelopmentHeaders,
      query: { include_retired: true },
    }),
  });
  const save = useMutation({
    mutationFn: () => editing
      ? getBrowserApiClient().request("qualification_update_company_context", {
          pathParams: { item_id: text(editing.id) },
          headers: { ...buyerDevelopmentHeaders, "If-Match": text(editing.etag) },
          idempotencyKey: createIdempotencyKey("company-context-update"),
          body: {
            label,
            payload: { statement },
            change_reason: "Buyer corrected durable company context",
          },
        })
      : getBrowserApiClient().request("qualification_create_company_context", {
          headers: buyerDevelopmentHeaders,
          idempotencyKey: createIdempotencyKey("company-context-create"),
          body: {
            kind,
            label,
            payload: { statement },
            change_reason: "Buyer added durable company context",
          },
        }),
    onSuccess: async () => {
      setLabel("");
      setStatement("");
      setEditing(null);
      await queryClient.invalidateQueries({ queryKey: ["company-context"] });
    },
  });
  const retire = useMutation({
    mutationFn: (item: JsonMap) => getBrowserApiClient().request(
      "qualification_retire_company_context",
      {
        pathParams: { item_id: text(item.id) },
        headers: { ...buyerDevelopmentHeaders, "If-Match": text(item.etag) },
        idempotencyKey: createIdempotencyKey("company-context-retire"),
      },
    ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["company-context"] }),
  });

  const beginEdit = (item: JsonMap) => {
    setEditing(item);
    setKind(text(item.kind, "NOTE") as typeof kind);
    setLabel(text(item.label));
    setStatement(text(map(item.payload).statement));
  };

  return (
    <MarketplaceShell>
      <section className={styles.contextHero}>
        <p className={styles.eyebrow}><BookOpen size={15} /> Versioned company context</p>
        <h1 className={styles.sectionTitle}>Company memory you can inspect and correct.</h1>
        <p className={styles.lead}>Structured buyer facts remain private, immutable by version, and explicitly pinned into each mission. Retiring a fact never rewrites prior decisions.</p>
      </section>
      <div className={styles.contextLayout}>
        <section className={`${styles.card} ${styles.formCard}`}>
          <div className={styles.formHead}>
            <h2>{editing ? "Publish a correction" : "Add company context"}</h2>
            <span className={styles.stepBadge}>{editing ? `v${number(editing.current_version) + 1}` : "New"}</span>
          </div>
          <div className={styles.field}>
            <label htmlFor="context-kind">Type</label>
            <select id="context-kind" value={kind} disabled={Boolean(editing)} onChange={(event) => setKind(event.target.value as typeof kind)}>
              {(["REQUIREMENT", "CONSTRAINT", "STACK", "POLICY", "PREFERENCE", "NOTE"] as const).map((value) => <option key={value}>{value}</option>)}
            </select>
          </div>
          <div className={styles.field}>
            <label htmlFor="context-label">Label</label>
            <input id="context-label" value={label} maxLength={160} onChange={(event) => setLabel(event.target.value)} placeholder="EU data residency" />
          </div>
          <div className={styles.field}>
            <label htmlFor="context-statement">Authoritative statement</label>
            <textarea id="context-statement" value={statement} maxLength={2000} onChange={(event) => setStatement(event.target.value)} placeholder="Customer data must remain inside the European Union." />
          </div>
          {save.error ? <ErrorPanel error={save.error} /> : null}
          <div className={styles.buttonRow}>
            <button className={styles.button} type="button" disabled={save.isPending || label.length < 2 || statement.length < 2} onClick={() => save.mutate()}>
              <Plus size={16} /> {editing ? "Publish correction" : "Save context"}
            </button>
            {editing ? <button className={styles.secondaryButton} type="button" onClick={() => { setEditing(null); setLabel(""); setStatement(""); }}>Cancel</button> : null}
          </div>
        </section>
        <section className={styles.contextStack} aria-live="polite">
          {context.isLoading ? <LoadingPanel /> : null}
          {context.error ? <ErrorPanel error={context.error} retry={() => context.refetch()} /> : null}
          {context.data?.items.length === 0 ? <div className={styles.empty}><BookOpen size={22} /><strong>No durable context yet.</strong><span>Add the first reusable buyer fact.</span></div> : null}
          {context.data?.items.map((item) => (
            <article className={`${styles.panel} ${styles.contextCard}`} key={text(item.id)}>
              <div className={styles.contextCardHead}>
                <div><span className={styles.pill}>{text(item.kind)}</span><h2>{text(item.label)}</h2></div>
                <StateBadge value={text(item.state)} />
              </div>
              <p>{text(map(item.payload).statement, "Structured context payload")}</p>
              <div className={styles.contextMeta}><span>Version {number(item.current_version)}</span><code>{shortHash(item.current_hash)}</code></div>
              {text(item.state) === "ACTIVE" ? (
                <div className={styles.buttonRow}>
                  <button className={styles.secondaryButton} type="button" onClick={() => beginEdit(item)}>Correct</button>
                  <button className={styles.secondaryButton} type="button" disabled={retire.isPending} onClick={() => retire.mutate(item)}><Archive size={15} /> Retire</button>
                </div>
              ) : null}
            </article>
          ))}
        </section>
      </div>
    </MarketplaceShell>
  );
}

function useMission(missionId: string) {
  return useQuery({
    queryKey: ["qualification-mission", missionId],
    queryFn: () => getBrowserApiClient().request("qualification_get_mission", {
      pathParams: { mission_id: missionId },
      headers: buyerDevelopmentHeaders,
    }),
    refetchInterval: (query) => {
      const state = text((query.state.data as QualificationMissionView | undefined)?.mission.state);
      return ["READY", "RUNNING"].includes(state) ? 2500 : false;
    },
  });
}

function MissionTimeline({ view }: { view: QualificationMissionView }) {
  const attempts = view.attempts;
  return (
    <ul className={styles.timeline}>
      <li className={styles.timelineItem}>
        <span className={styles.timelineDot}><Check size={13} /></span>
        <div><strong>Inputs committed</strong><span>Buyer context, requirement brief, and procurement policy are independently hashed.</span></div>
      </li>
      {attempts.length === 0 ? (
        <li className={styles.timelineItem}>
          <span className={styles.timelineDot}><LoaderCircle size={13} /></span>
          <div><strong>Awaiting worker</strong><span>The durable outbox event is ready for SQS dispatch.</span></div>
        </li>
      ) : attempts.map((attempt, index) => (
        <li className={styles.timelineItem} key={text(attempt.id, String(index))}>
          <span className={styles.timelineDot}>{text(attempt.state) === "STALE" ? <RefreshCw size={13} /> : <Check size={13} />}</span>
          <div>
            <strong>Attempt {index + 1}: {text(attempt.state).replaceAll("_", " ")}</strong>
            <span>Generation {number(attempt.generation)} · {array(attempt.dependencies).length} frozen dependencies · {array(attempt.checkpoints).length} checkpoints</span>
          </div>
        </li>
      ))}
      {view.decision ? (
        <li className={styles.timelineItem}>
          <span className={styles.timelineDot}><BadgeCheck size={13} /></span>
          <div><strong>Decision committed</strong><span>Bound to {shortHash(view.decision.input_digest)}.</span></div>
        </li>
      ) : null}
    </ul>
  );
}

export function MissionRoom({ missionId }: { missionId: string }) {
  const queryClient = useQueryClient();
  const query = useMission(missionId);
  const decision = query.data?.decision;
  const approve = useMutation({
    mutationFn: (action: "APPROVE" | "REJECT") => {
      if (!decision) throw new Error("No current decision is available.");
      return getBrowserApiClient().request("qualification_decide_approval", {
        pathParams: { decision_id: text(decision.id) },
        headers: { ...buyerDevelopmentHeaders, "If-Match": text(decision.etag) },
        idempotencyKey: createIdempotencyKey(`qualification-${action.toLowerCase()}`),
        body: {
          action,
          reason: action === "APPROVE"
            ? "The current evidence, constraints, and policy checks are acceptable."
            : "The buyer is not proceeding with this recommendation.",
        },
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["qualification-mission", missionId] }),
  });

  return (
    <MarketplaceShell>
      <header className={styles.workspaceHeader}>
        <div>
          <p className={styles.kicker}>SIRA buying mission</p>
          <h1>{query.data ? text(map(query.data.mission.requirement_brief).goal, "Qualification mission") : "Qualification mission"}</h1>
          <p>Every agent conclusion below is advisory until a verified human approves its exact decision digest.</p>
        </div>
        {query.data ? <StateBadge value={text(query.data.mission.state)} /> : null}
      </header>

      {query.isLoading ? <LoadingPanel /> : query.error ? <ErrorPanel error={query.error} retry={() => query.refetch()} /> : query.data ? (
        <div className={styles.dashboard}>
          <div className={styles.stack}>
            <section className={styles.panel}>
              <div className={styles.panelHead}>
                <h2>Durable execution</h2>
                <span className={styles.mono}>{shortHash(query.data.mission.trace_id)}</span>
              </div>
              <MissionTimeline view={query.data} />
            </section>

            {decision ? (
              <section className={styles.decisionHero}>
                <p className={styles.kicker}><BadgeCheck size={14} /> Bedrock recommendation · advisory</p>
                <h2>{text(decision.recommended_product_id)}</h2>
                <p>{text(map(decision.payload).summary)}</p>
                <div className={styles.criteriaGrid}>
                  {array(map(decision.payload).criteria).map((criterion, index) => (
                    <div className={styles.criterion} key={`${text(criterion.criterion)}-${index}`}>
                      <Check size={17} color="var(--success)" />
                      <div><strong>{text(criterion.criterion)}</strong><span>{text(criterion.result)}{criterion.rationale ? ` · ${text(criterion.rationale)}` : ""}</span></div>
                    </div>
                  ))}
                </div>
                <p className={styles.mono}>Decision {shortHash(decision.decision_digest)} · Input {shortHash(decision.input_digest)}</p>
                {text(decision.approval_state) === "PENDING" ? (
                  <div className={styles.buttonRow}>
                    <button className={styles.button} type="button" disabled={approve.isPending} onClick={() => approve.mutate("APPROVE")}>
                      <ShieldCheck size={16} /> Approve exact decision
                    </button>
                    <button className={styles.dangerButton} type="button" disabled={approve.isPending} onClick={() => approve.mutate("REJECT")}>
                      Reject
                    </button>
                  </div>
                ) : <StateBadge value={text(decision.approval_state)} />}
                {approve.error ? <ErrorPanel error={approve.error} /> : null}
              </section>
            ) : (
              <div className={styles.notice}>The worker will retrieve current candidates through CockroachDB Distributed Vector Indexing, inspect every pinned bundle with Bedrock, and return here.</div>
            )}
          </div>

          <aside className={styles.stack}>
            <section className={styles.panel}>
              <div className={styles.panelHead}><h3>Integrity now</h3><StateBadge value={text(query.data.integrity.verdict, "PENDING")} /></div>
              <div className={styles.statGrid}>
                <div className={styles.stat}><strong>{query.data.attempts.length}</strong><span>attempts</span></div>
                <div className={styles.stat}><strong>{query.data.attempts.filter((item) => text(item.state) === "STALE").length}</strong><span>invalidated</span></div>
                <div className={styles.stat}><strong>{query.data.decision ? 1 : 0}</strong><span>current decisions</span></div>
              </div>
              <div className={styles.buttonRow}>
                <Link className={styles.secondaryButton} href={`/integrity/${missionId}`}>Inspect proof <ArrowRight size={15} /></Link>
                {query.data.engagement ? <Link className={styles.button} href={`/matches/${text(query.data.engagement.id)}`}>Open match</Link> : null}
              </div>
            </section>
            <section className={styles.panel}>
              <h3>Input bindings</h3>
              <p className={styles.mono}>Buyer {shortHash(query.data.mission.buyer_context_hash)}</p>
              <p className={styles.mono}>Brief {shortHash(query.data.mission.requirement_brief_hash)}</p>
              <p className={styles.mono}>Policy {shortHash(query.data.mission.procurement_policy_hash)}</p>
            </section>
          </aside>
        </div>
      ) : null}
    </MarketplaceShell>
  );
}

function useEngagement(engagementId: string, seller: boolean) {
  return useQuery({
    queryKey: ["qualification-engagement", engagementId, seller ? "seller" : "buyer"],
    queryFn: () => getBrowserApiClient().request("qualification_get_engagement", {
      pathParams: { engagement_id: engagementId },
      headers: seller ? sellerEditorDevelopmentHeaders : buyerDevelopmentHeaders,
    }),
  });
}

export function SellerOpportunity({ engagementId }: { engagementId: string }) {
  const queryClient = useQueryClient();
  const query = useEngagement(engagementId, true);
  const engagement = query.data?.engagement;
  const respond = useMutation({
    mutationFn: (response: "FIT" | "ANTI_FIT" | "NEEDS_INFO") => getBrowserApiClient().request("qualification_record_seller_response", {
      pathParams: { engagement_id: engagementId },
      headers: { ...sellerEditorDevelopmentHeaders, "If-Match": text(engagement?.etag) },
      idempotencyKey: createIdempotencyKey(`seller-${response.toLowerCase()}`),
      body: { response, cited_evidence_ids: [], message: response === "FIT" ? "Our current published Product Bundle supports this requirement." : "A seller specialist should clarify this requirement." },
    }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["qualification-engagement", engagementId] }),
  });

  return (
    <MarketplaceShell>
      <header className={styles.workspaceHeader}>
        <div><p className={styles.kicker} style={{ color: "var(--seil)" }}>SEIL qualified opportunity</p><h1>A buyer agent found a plausible fit.</h1><p>Answer against seller-owned evidence. The buyer’s private context was not disclosed.</p></div>
        {engagement ? <StateBadge value={text(engagement.state)} /> : null}
      </header>
      {query.isLoading ? <LoadingPanel /> : query.error ? <ErrorPanel error={query.error} retry={() => query.refetch()} /> : query.data ? (
        <div className={styles.dashboard}>
          <div className={styles.stack}>
            <section className={styles.panel}>
              <div className={styles.panelHead}><h2>Buyer-approved requirement</h2><LockKeyhole size={18} color="var(--seil)" /></div>
              <div className={styles.disclosure}>
                <h3>Minimum disclosure projection</h3>
                {Object.entries(map(engagement?.buyer_safe_requirement)).map(([key, value]) => <p key={key}><strong>{key.replaceAll("_", " ")}</strong>: {String(value)}</p>)}
                <p className={styles.mono}>Projection {shortHash(engagement?.buyer_safe_hash)}</p>
              </div>
            </section>
            <section className={styles.panel}>
              <h2>Does your current evidence fit?</h2>
              <p className={styles.muted}>SEIL may recommend a response, but a verified seller human owns this statement.</p>
              <div className={styles.buttonRow}>
                <button className={styles.button} type="button" onClick={() => respond.mutate("FIT")} disabled={respond.isPending}>Fit</button>
                <button className={styles.secondaryButton} type="button" onClick={() => respond.mutate("NEEDS_INFO")} disabled={respond.isPending}>Needs information</button>
                <button className={styles.dangerButton} type="button" onClick={() => respond.mutate("ANTI_FIT")} disabled={respond.isPending}>Anti-fit</button>
              </div>
              {respond.error ? <ErrorPanel error={respond.error} /> : null}
              {query.data.seller_response ? <div className={styles.notice}>Response recorded: <strong>{text(query.data.seller_response.response)}</strong>. The buyer now sees the same committed response.</div> : null}
            </section>
          </div>
          <aside className={styles.stack}>
            <section className={styles.panel}><h3>Evidence boundary</h3><p className={styles.muted}>Only evidence inside the active Product Bundle can be cited. Updating that bundle invalidates any in-flight buyer decision.</p><p className={styles.mono}>Input {shortHash(engagement?.input_digest)}</p></section>
            <Link className={styles.secondaryButton} href={`/seil/products/${text(engagement?.product_id)}/evidence`}>Manage Product Evidence <ArrowRight size={15} /></Link>
          </aside>
        </div>
      ) : null}
    </MarketplaceShell>
  );
}

export function MatchRoom({ engagementId }: { engagementId: string }) {
  const queryClient = useQueryClient();
  const query = useEngagement(engagementId, false);
  const engagement = query.data?.engagement;
  const sharedFields = { buyer_email: "buyer@example.test", seller_email: "seller@example.test" };
  const consent = useMutation({
    mutationFn: () => getBrowserApiClient().request("qualification_record_consent", {
      pathParams: { engagement_id: engagementId },
      headers: { ...buyerDevelopmentHeaders, "If-Match": text(engagement?.etag) },
      idempotencyKey: createIdempotencyKey("buyer-consent"),
      body: { shared_fields: sharedFields },
    }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["qualification-engagement", engagementId] }),
  });
  const introduce = useMutation({
    mutationFn: () => getBrowserApiClient().request("qualification_create_introduction", {
      pathParams: { engagement_id: engagementId },
      headers: { ...buyerDevelopmentHeaders, "If-Match": text(engagement?.etag) },
      idempotencyKey: createIdempotencyKey("qualified-introduction"),
      body: { shared_fields: sharedFields },
    }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["qualification-engagement", engagementId] }),
  });
  const consents = query.data?.consents ?? [];
  const buyerConsent = consents.some((item) => text(item.party) === "BUYER" && text(item.state) === "GRANTED");
  const sellerConsent = consents.some((item) => text(item.party) === "SELLER" && text(item.state) === "GRANTED");

  return (
    <MarketplaceShell>
      <header className={styles.workspaceHeader}>
        <div><p className={styles.kicker}>Bilateral match room</p><h1>Proof first. Introduction second.</h1><p>The match stays bound to one approved decision and both humans must approve the identical disclosure set.</p></div>
        {engagement ? <StateBadge value={text(engagement.state)} /> : null}
      </header>
      {query.isLoading ? <LoadingPanel /> : query.error ? <ErrorPanel error={query.error} retry={() => query.refetch()} /> : query.data ? (
        <div className={styles.stack}>
          <div className={styles.split}>
            <section className={styles.panel}><p className={styles.kicker}>Buyer</p><h2>Requirement owner</h2><p className={styles.muted}>Organization {text(engagement?.buyer_organization_id)}</p><StateBadge value={buyerConsent ? "CONSENT GRANTED" : "CONSENT PENDING"} /></section>
            <section className={styles.panel}><p className={styles.kicker} style={{ color: "var(--seil)" }}>Seller</p><h2>{text(engagement?.product_id)}</h2><p className={styles.muted}>Organization {text(engagement?.seller_organization_id)}</p><StateBadge value={sellerConsent ? "CONSENT GRANTED" : "CONSENT PENDING"} /></section>
          </div>
          <section className={styles.panel}>
            <div className={styles.panelHead}><h2>Exact disclosure agreement</h2><ShieldCheck size={20} /></div>
            <div className={styles.disclosure}><p><strong>Buyer contact:</strong> buyer@example.test</p><p><strong>Seller contact:</strong> seller@example.test</p><p className={styles.mono}>Both consent records must hash to this identical field set.</p></div>
            <div className={styles.buttonRow}>
              {!buyerConsent ? <button className={styles.secondaryButton} type="button" onClick={() => consent.mutate()} disabled={consent.isPending}>Grant buyer consent</button> : null}
              {buyerConsent && sellerConsent && !query.data.introduction ? <button className={styles.button} type="button" onClick={() => introduce.mutate()} disabled={introduce.isPending}><BadgeCheck size={16} /> Create qualified introduction</button> : null}
              {!sellerConsent ? <Link className={styles.secondaryButton} href={`/seil/opportunities/${engagementId}`}>Open seller side</Link> : null}
            </div>
            {consent.error ? <ErrorPanel error={consent.error} /> : null}
            {introduce.error ? <ErrorPanel error={introduce.error} /> : null}
          </section>
          {query.data.introduction ? <div className={styles.receipt}><strong>Qualified introduction committed</strong><span className={styles.receiptCode}>{JSON.stringify(query.data.introduction.receipt, null, 2)}</span></div> : null}
        </div>
      ) : null}
    </MarketplaceShell>
  );
}

export function IntegrityRoom({ missionId }: { missionId: string }) {
  const query = useQuery({
    queryKey: ["qualification-integrity", missionId],
    queryFn: () => getBrowserApiClient().request("qualification_get_integrity", {
      pathParams: { mission_id: missionId },
      headers: buyerDevelopmentHeaders,
    }),
  });
  return (
    <MarketplaceShell>
      <header className={styles.workspaceHeader}>
        <div><p className={styles.kicker}>CockroachDB integrity inspector</p><h1>Don’t trust the UI. Verify the invariants.</h1><p>This projection is calculated from current mission, attempt, dependency, decision, and effect rows.</p></div>
        {query.data ? <StateBadge value={query.data.verdict} /> : null}
      </header>
      {query.isLoading ? <LoadingPanel /> : query.error ? <ErrorPanel error={query.error} retry={() => query.refetch()} /> : query.data ? <IntegrityContent value={query.data} /> : null}
    </MarketplaceShell>
  );
}

function IntegrityContent({ value }: { value: QualificationIntegrityView }) {
  return (
    <div className={styles.dashboard}>
      <section className={styles.panel}>
        <div className={styles.panelHead}><h2>Five-check verdict</h2><Database size={20} color="var(--sira)" /></div>
        <div className={styles.checkGrid}>
          {value.checks.map((check, index) => {
            const status = text(check.status, "PENDING");
            return <div className={styles.check} key={`${text(check.name)}-${index}`}>{status === "PASS" ? <Check size={18} color="var(--success)" /> : <CircleAlert size={18} color={status === "FAIL" ? "var(--danger)" : "var(--warning)"} />}<div><strong>{text(check.name).replaceAll("_", " ")}</strong><span>{text(check.detail)}</span></div></div>;
          })}
        </div>
      </section>
      <aside className={styles.stack}>
        <section className={styles.panel}><h3>Independent proof path</h3><p className={styles.muted}>The same mission can be inspected through CockroachDB’s managed MCP server during judging, using a scoped read-only identity.</p><p className={styles.mono}>Mission {value.mission_id}</p><p className={styles.mono}>Checked {value.checked_at}</p></section>
        <Link className={styles.secondaryButton} href={`/sira/missions/${value.mission_id}`}>Return to mission <ArrowRight size={15} /></Link>
      </aside>
    </div>
  );
}
