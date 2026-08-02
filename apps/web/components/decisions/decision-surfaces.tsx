"use client";

import type {
  DecisionIndexView,
  DecisionRequestView,
  DecisionStage,
  DecisionView,
  OptionFeedbackAction,
  SolutionOption,
} from "@sira/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  BadgeCheck,
  BookOpenText,
  Check,
  ChevronRight,
  CircleAlert,
  Clock3,
  FileCheck2,
  FileText,
  History,
  Inbox,
  Layers3,
  LockKeyhole,
  Menu,
  MessageSquareText,
  MoreHorizontal,
  PanelRightOpen,
  Plus,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";

import rawDecisionFixture from "../../../../fixtures/demo/expected_decision_view.json";
import {
  WEB_DATA_MODE,
  buyerDevelopmentHeaders,
  createIdempotencyKey,
  getBrowserApiClient,
} from "@/lib/api";

import styles from "./decision-surfaces.module.css";

const decisionFixture = rawDecisionFixture as unknown as DecisionView;

const fixtureIndex: DecisionIndexView = {
  active: [
    {
      id: "req_demo",
      intent: "Find meeting intelligence for ten consultants",
      status: "DECISION_READY",
      visibility: "SELECTIVE",
      current_stage: "OPTIONS",
      current_decision_version: 1,
      deadline: "2026-08-19T17:00:00Z",
      href: "/decisions/req_demo/versions/1/options",
      last_checkpoint: "Options evaluated 2 minutes ago",
      owner_role: "DECISION_MAKER",
      blocker: null,
    },
  ],
  history: [
    {
      id: "req_crm_history",
      intent: "Review CRM renewal and seat count",
      status: "COMPLETED",
      visibility: "PRIVATE",
      current_stage: "RESULT",
      current_decision_version: 3,
      deadline: "2026-07-31T17:00:00Z",
      href: "/decisions/req_demo/versions/1/result",
      last_checkpoint: "Result recorded 31 Jul",
      owner_role: "DECISION_MAKER",
      blocker: null,
    },
  ],
  available_actions: [],
};

const stages: Array<{ key: DecisionStage; slug: string; label: string }> = [
  { key: "NEED", slug: "need", label: "Need" },
  { key: "COMPANY_FIT", slug: "company-fit", label: "Company fit" },
  { key: "OPTIONS", slug: "options", label: "Options" },
  { key: "ACTION", slug: "action", label: "Action" },
  { key: "RESULT", slug: "result", label: "Result" },
];

const statusLabels: Record<SolutionOption["status"], string> = {
  SUPPORTED: "Supported",
  SUPPORTED_WITH_EXCEPTION: "Supported with exception",
  NEEDS_CONDITION: "Condition required",
  BLOCKED_BY_COMPANY_REQUIREMENT: "Blocked by company requirement",
  VENDOR_NOT_SUPPORTED: "Vendor says not supported",
  UNAVAILABLE: "Unavailable",
  NEEDS_EVIDENCE: "Needs evidence",
  EVIDENCE_CONFLICT: "Evidence conflict",
  AUTHORITY_REQUIRED: "Authority required",
  RESEARCH_ONLY: "Research only",
};

function useNativeDialog(
  ref: React.RefObject<HTMLDialogElement | null>,
  open: boolean,
) {
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open, ref]);
}

function formatDeadline(value?: string | null) {
  if (!value) return "No deadline";
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

function FixtureBanner() {
  return (
    <div className={styles.fixtureBanner} role="status">
      <Sparkles aria-hidden="true" />
      <span><strong>Development fixture</strong> — this preview does not contact vendors, approve, pay, or change company records.</span>
    </div>
  );
}

function ApiErrorBanner({ retry }: { retry: () => void }) {
  return (
    <div className={styles.errorBanner} role="alert">
      <CircleAlert aria-hidden="true" />
      <span><strong>Backend not connected.</strong> Start the local API and PostgreSQL, then retry. No action was recorded.</span>
      <button type="button" onClick={retry}>Retry</button>
    </div>
  );
}

function RouteMismatchBanner({ message }: { message: string }) {
  return (
    <div className={styles.versionBanner} role="alert">
      <CircleAlert aria-hidden="true" />
      <span><strong>Decision version unavailable.</strong> {message}</span>
      <Link href="/decisions">Back to decisions</Link>
    </div>
  );
}

function WorkspaceRail({ active = "decisions" }: { active?: "decisions" | "inbox" }) {
  return (
    <aside className={styles.rail} aria-label="SIRA navigation">
      <div className={styles.railTop}>
        <Link className={styles.workspaceMark} href="/home" aria-label="Switch workspace">
          <span className={styles.siraGlyph}>S</span>
          <span><strong>SIRA</strong><small>Northstar Advisory</small></span>
        </Link>
        <Link className={styles.newDecisionButton} href="/decisions/new">
          <Plus aria-hidden="true" /> New decision
        </Link>
        <nav className={styles.primaryNav} aria-label="Primary">
          <Link className={active === "decisions" ? styles.activeNav : ""} href="/decisions">
            <Layers3 aria-hidden="true" /> Decisions
          </Link>
          <Link className={active === "inbox" ? styles.activeNav : ""} href="/inbox">
            <Inbox aria-hidden="true" /> Inbox <span>3</span>
          </Link>
        </nav>
        <div className={styles.railDivider} />
        <p className={styles.railLabel}>Recent</p>
        <Link className={styles.recentDecision} href="/decisions/req_demo/versions/1/options">
          <span className={styles.recentDot} />
          <span><strong>Meeting-intelligence renewal</strong><small>Options ready</small></span>
        </Link>
      </div>
      <div className={styles.railFooter}>
        <Link href="/home"><LockKeyhole aria-hidden="true" /> Private company workspace</Link>
        <button type="button" aria-label="Open account menu">
          <span className={styles.avatar}>AS</span>
          <span><strong>Asha Singh</strong><small>Decision maker</small></span>
          <MoreHorizontal aria-hidden="true" />
        </button>
      </div>
    </aside>
  );
}

function MobileRailDialog({ open, close }: { open: boolean; close: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useNativeDialog(ref, open);
  return (
    <dialog className={styles.mobileDialog} ref={ref} onClose={close}>
      <div className={styles.mobileDialogHead}>
        <strong>SIRA</strong>
        <button type="button" aria-label="Close navigation" onClick={close}><X aria-hidden="true" /></button>
      </div>
      <nav>
        <Link href="/home" onClick={close}>Workspace home</Link>
        <Link href="/decisions" onClick={close}>Decisions</Link>
        <Link href="/decisions/new" onClick={close}>New decision</Link>
        <Link href="/inbox" onClick={close}>Inbox</Link>
      </nav>
    </dialog>
  );
}

function DecisionRow({ item }: { item: DecisionRequestView }) {
  return (
    <Link className={styles.decisionRow} href={item.href}>
      <span className={styles.rowState} data-state={item.current_stage.toLowerCase()}>{item.current_stage.replace("_", " ")}</span>
      <span className={styles.rowTitle}><strong>{item.intent}</strong><small>{item.last_checkpoint}</small></span>
      <span className={styles.rowMeta}><small>Owner</small>{item.owner_role.replaceAll("_", " ")}</span>
      <span className={styles.rowMeta}><small>Deadline</small>{formatDeadline(item.deadline)}</span>
      <span className={item.blocker ? styles.blocker : styles.ready}>{item.blocker ?? "Ready"}</span>
      <ChevronRight aria-hidden="true" />
    </Link>
  );
}

export function DecisionIndex() {
  const [mobileRail, setMobileRail] = useState(false);
  const query = useQuery({
    queryKey: ["decision-index"],
    enabled: WEB_DATA_MODE === "api",
    queryFn: () => getBrowserApiClient().request("list_decision_requests", { headers: buyerDevelopmentHeaders }),
  });
  const data = WEB_DATA_MODE === "fixture" ? fixtureIndex : query.data;

  return (
    <div className={styles.appShell}>
      <WorkspaceRail />
      <MobileRailDialog open={mobileRail} close={() => setMobileRail(false)} />
      <main className={styles.indexMain}>
        {WEB_DATA_MODE === "fixture" ? <FixtureBanner /> : null}
        {query.isError ? <ApiErrorBanner retry={() => void query.refetch()} /> : null}
        <header className={styles.indexHeader}>
          <button className={styles.mobileMenuButton} type="button" aria-label="Open navigation" onClick={() => setMobileRail(true)}><Menu aria-hidden="true" /></button>
          <div><p>SIRA workspace</p><h1>Decisions</h1><span>Active work first, with every previous version kept for audit.</span></div>
          <Link className={styles.primaryButton} href="/decisions/new"><Plus aria-hidden="true" /> New decision</Link>
        </header>
        <section className={styles.indexSection} aria-labelledby="active-heading">
          <div className={styles.sectionTitle}><div><p>Active</p><h2 id="active-heading">Needs your attention</h2></div><span>{data?.active.length ?? 0}</span></div>
          {query.isPending && WEB_DATA_MODE === "api" ? <div className={styles.skeletonList} aria-label="Loading decisions"><i /><i /></div> : null}
          {data?.active.length ? data.active.map((item) => <DecisionRow item={item} key={item.id} />) : !query.isPending ? <div className={styles.emptyState}><FileText aria-hidden="true" /><h3>No active decisions</h3><p>Start with the software outcome you need. SIRA will keep the private company context and decision record separate.</p><Link href="/decisions/new">Create a decision</Link></div> : null}
        </section>
        <section className={styles.indexSection} aria-labelledby="history-heading">
          <div className={styles.sectionTitle}><div><p>History</p><h2 id="history-heading">Recorded outcomes</h2></div><History aria-hidden="true" /></div>
          {data?.history.map((item) => <DecisionRow item={item} key={item.id} />)}
        </section>
      </main>
    </div>
  );
}

export function NewDecision() {
  const router = useRouter();
  const [mobileRail, setMobileRail] = useState(false);
  const [intent, setIntent] = useState("Review our meeting-intelligence renewal and decide whether to renew, resize, or replace it.");
  const [outcome, setOutcome] = useState("Keep client conversations private and give consultants reliable source-linked answers with low administration effort.");
  const [deadline, setDeadline] = useState("2026-08-19T17:00");
  const [visibility, setVisibility] = useState<"PRIVATE" | "SELECTIVE" | "OPEN_RFP">("SELECTIVE");
  const [safeError, setSafeError] = useState("");

  const createMutation = useMutation({
    mutationFn: async () => {
      const client = getBrowserApiClient();
      const created = await client.request("create_decision_request", {
        body: { intent, desired_outcome: outcome || null, deadline: deadline ? new Date(deadline).toISOString() : null, visibility },
        idempotencyKey: createIdempotencyKey("create-decision"),
        headers: buyerDevelopmentHeaders,
      });
      await client.request("discover_decision_request", {
        pathParams: { request_id: created.id },
        idempotencyKey: createIdempotencyKey(`discover-${created.id}`),
        headers: buyerDevelopmentHeaders,
      });
      return created;
    },
    onSuccess: (created) => router.push(`/decisions/${created.id}/versions/1/need`),
    onError: () => setSafeError("The decision was not created. Check the local API and try again; no partial request is being shown as saved."),
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setSafeError("");
    if (WEB_DATA_MODE === "fixture") {
      router.push("/decisions/req_demo/versions/1/options");
      return;
    }
    createMutation.mutate();
  };

  return (
    <div className={styles.appShell}>
      <WorkspaceRail />
      <MobileRailDialog open={mobileRail} close={() => setMobileRail(false)} />
      <main className={styles.newMain}>
        {WEB_DATA_MODE === "fixture" ? <FixtureBanner /> : null}
        <header className={styles.objectHeader}>
          <button className={styles.mobileMenuButton} type="button" aria-label="Open navigation" onClick={() => setMobileRail(true)}><Menu aria-hidden="true" /></button>
          <div><p>Private decision</p><h1>What decision are you working through?</h1><span>Only ask for context that can change eligibility, ranking, disclosure, or execution.</span></div>
          <span className={styles.privacyBadge}><LockKeyhole aria-hidden="true" /> Private to your company</span>
        </header>
        <div className={styles.newGrid}>
          <form className={styles.briefForm} onSubmit={submit}>
            <div className={styles.formIntro}><MessageSquareText aria-hidden="true" /><div><strong>Guided intake</strong><p>The connected first build uses a short structured brief. Conversation capture will feed these same versioned fields when its API contract is enabled.</p></div></div>
            <label><span>Decision</span><small>What are you deciding?</small><textarea value={intent} onChange={(event) => setIntent(event.target.value)} required rows={4} /></label>
            <label><span>Desired outcome</span><small>What must improve for the company?</small><textarea value={outcome} onChange={(event) => setOutcome(event.target.value)} rows={4} /></label>
            <div className={styles.formRow}>
              <label><span>Decision deadline</span><input type="datetime-local" value={deadline} onChange={(event) => setDeadline(event.target.value)} /></label>
              <fieldset><legend>Visibility</legend>{(["PRIVATE", "SELECTIVE", "OPEN_RFP"] as const).map((item) => <label key={item}><input type="radio" name="visibility" value={item} checked={visibility === item} onChange={() => setVisibility(item)} /> {item === "OPEN_RFP" ? "Open RFP" : item.charAt(0) + item.slice(1).toLowerCase()}</label>)}</fieldset>
            </div>
            {safeError ? <p className={styles.inlineError} role="alert">{safeError}</p> : null}
            <div className={styles.formActions}><Link href="/decisions">Cancel</Link><button className={styles.primaryButton} type="submit" disabled={!intent.trim() || createMutation.isPending}>{WEB_DATA_MODE === "fixture" ? "Open deterministic demo" : createMutation.isPending ? "Creating…" : "Create decision"}<ArrowRight aria-hidden="true" /></button></div>
          </form>
          <aside className={styles.briefPreview} aria-label="Purchase brief preview">
            <p>Live Purchase Brief</p>
            <h2>{intent || "Untitled decision"}</h2>
            <dl>
              <div><dt>Outcome</dt><dd>{outcome || "Not supplied"}</dd></div>
              <div><dt>Deadline</dt><dd>{deadline ? formatDeadline(new Date(deadline).toISOString()) : "Not supplied"}</dd></div>
              <div><dt>Visibility</dt><dd>{visibility === "OPEN_RFP" ? "Open RFP" : visibility.charAt(0) + visibility.slice(1).toLowerCase()}</dd></div>
              <div><dt>Authority</dt><dd>Decision maker selects; budget owner approves; cardholder authorizes a charge.</dd></div>
            </dl>
            <div className={styles.boundaryNote}><ShieldCheck aria-hidden="true" /><p><strong>Nothing is sent to a seller yet.</strong> Selective outreach requires a separate sanitized Requirement Brief preview and confirmation.</p></div>
          </aside>
        </div>
      </main>
    </div>
  );
}

function DecisionPath({ view, requestId, version, currentSlug }: { view: DecisionView; requestId: string; version: string; currentSlug: string }) {
  const stateByStage = new Map(view.workflow.stage_history.map((item) => [item.stage, item.status]));
  return (
    <nav className={styles.decisionPath} aria-label="Decision stages">
      {stages.map((stage, index) => {
        const status = stateByStage.get(stage.key) ?? "NOT_STARTED";
        return (
          <Link key={stage.key} href={`/decisions/${requestId}/versions/${version}/${stage.slug}`} aria-current={currentSlug === stage.slug ? "page" : undefined} data-status={status.toLowerCase()}>
            <span>{status === "COMPLETED" ? <Check aria-hidden="true" /> : String(index + 1).padStart(2, "0")}</span>
            <strong>{stage.label}</strong>
            <small>{status.replaceAll("_", " ").toLowerCase()}</small>
          </Link>
        );
      })}
    </nav>
  );
}

function ConversationPanel({ compact = false }: { compact?: boolean }) {
  return (
    <section className={compact ? styles.conversationCompact : styles.conversationPanel} aria-label="Decision conversation preview">
      <header><div><p>Decision context</p><h2>Conversation</h2></div><span><LockKeyhole aria-hidden="true" /> Private</span></header>
      <div className={styles.conversationMessages}>
        <article><strong>You</strong><p>Should we renew Cairn Notes for ten consultants, resize it, or replace it?</p></article>
        <article className={styles.siraMessage}><strong>SIRA</strong><p>I found the current contract and the company rules that change this decision. Client privacy and source-linked answers are decisive.</p><div><span>3 confirmed facts used</span><button type="button">Review sources</button></div></article>
        <article><strong>You</strong><p>Keep the change easy for a small operations team.</p></article>
        <article className={styles.siraMessage}><strong>SIRA</strong><p>That is reflected in the current Purchase Brief. The structured result remains authoritative.</p></article>
      </div>
      <div className={styles.disabledComposer}><textarea aria-label="Decision conversation unavailable" disabled placeholder="Conversation input needs the message and capture contract" /><span>Context Q&amp;A is preview-only in this build.</span></div>
    </section>
  );
}

function NeedStage({ view }: { view: DecisionView }) {
  return (
    <section className={styles.stageSection}>
      <div className={styles.stageIntro}><p>01 · Need</p><h2>{view.request.intent}</h2><span>Define the outcome, deadline, stakeholders, and only the missing information that can change the decision.</span></div>
      <div className={styles.factGrid}>
        <article><span>Desired outcome</span><strong>Private, source-linked meeting intelligence with low administration effort</strong><small>Confirmed in Purchase Brief v1</small></article>
        <article><span>Current approach</span><strong>Cairn Notes · 10 consultant seats</strong><small>Contract and Company stack</small></article>
        <article><span>Decision by</span><strong>19 Aug 2026</strong><small>Before cancellation deadline</small></article>
        <article><span>Owners</span><strong>Operations · Budget owner · Cardholder</strong><small>Separate decision, approval, and payment authority</small></article>
      </div>
      <div className={styles.questionCard}><BookOpenText aria-hidden="true" /><div><p>Material clarification</p><h3>No unanswered question blocks evaluation</h3><span>If the user count, client-data treatment, or deadline changes, create a new Purchase Brief version before reevaluating.</span></div><button type="button" disabled>All material inputs present</button></div>
    </section>
  );
}

function CompanyFitStage({ view }: { view: DecisionView }) {
  return (
    <section className={styles.stageSection}>
      <div className={styles.stageIntro}><p>02 · Company fit</p><h2>Company facts and Decision rules</h2><span>Private company context stays separate from the sanitized Requirement Brief.</span></div>
      <div className={styles.twoColumnStage}>
        <div className={styles.structuredCard}>
          <div className={styles.cardHead}><div><p>Confirmed company facts</p><h3>{view.company_context.facts_used.length} facts used</h3></div><span>Profile v{view.company_context.company_profile_version}</span></div>
          <ul className={styles.companyFacts}>{view.company_context.facts_used.map((fact) => <li key={fact.fact_id}><span className={styles.factIcon}><Check aria-hidden="true" /></span><span><strong>{fact.display_name.replaceAll(".", " · ")}</strong><small>{fact.provenance_label} · {fact.sensitivity}</small></span><b>{fact.display_value}</b></li>)}</ul>
        </div>
        <aside className={styles.sideStack}>
          <div className={styles.boundaryCard}><LockKeyhole aria-hidden="true" /><p>Disclosure preview</p><h3>Only the minimum Requirement Brief crosses sides</h3><span>Company identity, hidden budget, employee names, competing offers, and unrestricted Stack data remain absent.</span><button type="button">Preview sanitized brief</button></div>
          <div className={styles.calibrationCard}><p>Calibration check</p><h3>Known examples behave as expected</h3><ul><li><Check aria-hidden="true" /> Known failure is blocked</li><li><Check aria-hidden="true" /> Incumbent remains eligible</li><li><Check aria-hidden="true" /> Expected qualifier passes</li></ul><button type="button" disabled>Run requires API contract</button></div>
        </aside>
      </div>
    </section>
  );
}

function OptionStatus({ status }: { status: SolutionOption["status"] }) {
  return <span className={styles.optionStatus} data-status={status.toLowerCase()}>{statusLabels[status]}</span>;
}

function OptionsStage({
  view,
  onLedger,
  onSelect,
  onFeedback,
  pendingFeedback,
}: {
  view: DecisionView;
  onLedger: () => void;
  onSelect: (option: SolutionOption) => void;
  onFeedback: (option: SolutionOption, action: OptionFeedbackAction) => void;
  pendingFeedback: boolean;
}) {
  const visible = view.solution_options.slice(0, 6);
  return (
    <section className={styles.stageSection}>
      <div className={styles.optionsHeading}>
        <div className={styles.stageIntro}><p>03 · Options</p><h2>Best supported action among evaluated options</h2><span>{view.coverage.statement}</span></div>
        <div className={styles.stabilityBox}><BadgeCheck aria-hidden="true" /><span><small>Decision stability</small><strong>{view.rank_stability.status.toLowerCase()}</strong><p>{view.rank_stability.summary}</p></span><button type="button" onClick={onLedger}>What could change?</button></div>
      </div>
      {view.decision_outcome === "NO_ELIGIBLE_SUPPORTED_ACTION" ? (
        <div className={styles.noEligible}><CircleAlert aria-hidden="true" /><h3>No eligible supported action</h3><p>{view.coverage.evaluated_solution_plan_count} evaluated; {view.coverage.excluded_count} excluded. Review named blockers and evidence/category limits before changing requirements.</p><button type="button" onClick={onLedger}>Open safe next actions</button></div>
      ) : (
        <div className={styles.optionTableWrap}>
          <table className={styles.optionTable}>
            <caption className="sr-only">Evaluated software actions</caption>
            <thead><tr><th>Action</th><th>Support status</th><th>Comparable cost</th><th>Company-stack change</th><th>Next action</th></tr></thead>
            <tbody>{visible.map((option, index) => <tr key={option.id} className={index === 0 ? styles.recommendedRow : ""}>
              <td><span className={styles.rank}>{index + 1}</span><div><strong>{option.label}</strong><small>{option.action_type.replaceAll("_", " ").toLowerCase()}{index === 0 ? " · Recommended" : ""}</small></div></td>
              <td><OptionStatus status={option.status} /><small>{option.reason}</small></td>
              <td><strong>{option.default_comparison.cost.currency} {option.default_comparison.cost.amount}</strong><small>{option.default_comparison.cost.horizon_days}-day horizon</small></td>
              <td><span>{option.default_comparison.stack_change}</span></td>
              <td><div className={styles.rowActions}>{index === 0 && option.status === "SUPPORTED" ? <button type="button" className={styles.selectButton} onClick={() => onSelect(option)}>Select plan</button> : <button type="button" onClick={() => onLedger()}>Review</button>}<details><summary aria-label={`More actions for ${option.label}`}><MoreHorizontal aria-hidden="true" /></summary><div><button type="button" disabled={pendingFeedback || WEB_DATA_MODE === "fixture"} onClick={() => onFeedback(option, "KEEP_FOR_COMPARISON")}>Keep for comparison</button><button type="button" disabled={pendingFeedback || WEB_DATA_MODE === "fixture"} onClick={() => onFeedback(option, "NEED_EVIDENCE")}>Need evidence</button><button type="button" disabled={pendingFeedback || WEB_DATA_MODE === "fixture"} onClick={() => onFeedback(option, "ELIMINATE")}>Eliminate</button></div></details></div></td>
            </tr>)}</tbody>
          </table>
        </div>
      )}
      <div className={styles.matrixNote}><ShieldCheck aria-hidden="true" /><span><strong>Seller-published Product Evidence; evaluated by SIRA against your company requirements.</strong> Raw score math, evidence coverage, provenance, and the counterfactual stay in the Decision Ledger.</span><button type="button" onClick={onLedger}>Open ledger</button></div>
    </section>
  );
}

function ActionStage({ view }: { view: DecisionView }) {
  const plan = view.selected_action_plan;
  const steps = plan?.execution_steps ?? [];
  return (
    <section className={styles.stageSection}>
      <div className={styles.stageIntro}><p>04 · Action</p><h2>{plan ? "Execute the selected action safely" : "Select an action plan first"}</h2><span>Review, required authority, execution or assignment, and verification remain separate.</span></div>
      {!plan ? <div className={styles.emptyStage}><FileCheck2 aria-hidden="true" /><h3>No plan is selected in this version</h3><p>Return to Options and select the exact plan/version/hash. A fixture preview never creates approval or payment authority.</p><Link className={styles.primaryButton} href="/decisions/req_demo/versions/1/options">Review options</Link></div> : <div className={styles.executionGrid}><ol className={styles.executionTimeline}>{steps.map((step, index) => <li key={step.id} data-status={step.status.toLowerCase()}><span>{step.status === "COMPLETED" ? <Check aria-hidden="true" /> : index + 1}</span><div><strong>{step.type.replaceAll("_", " ").toLowerCase()}</strong><small>{step.owner_role.replaceAll("_", " ")} · {step.status.replaceAll("_", " ")}</small>{step.blocker ? <p>{step.blocker}</p> : null}</div>{step.available_action ? <button type="button">{step.available_action.label}</button> : null}</li>)}</ol><aside className={styles.authorityPanel}><p>Authority</p><dl><div><dt>Plan selection</dt><dd>{plan.selected_by_role.replaceAll("_", " ")}</dd></div><div><dt>Approval</dt><dd>{view.approval?.status ?? "Not requested"}</dd></div><div><dt>Payment</dt><dd>{view.payment?.status ?? "Not required"}</dd></div><div><dt>Fulfillment</dt><dd>{view.fulfillment?.status ?? "Not started"}</dd></div></dl></aside></div>}
    </section>
  );
}

function ResultStage({ view }: { view: DecisionView }) {
  return (
    <section className={styles.stageSection}>
      <div className={styles.stageIntro}><p>05 · Result</p><h2>Verified outcome and artifacts</h2><span>Payment success, fulfillment, deployment, and outcome are never collapsed into one green state.</span></div>
      {view.result_artifacts.length ? <div className={styles.artifactGrid}>{view.result_artifacts.map((artifact) => <article key={artifact.id}><FileCheck2 aria-hidden="true" /><span><small>{artifact.type.replaceAll("_", " ")}</small><strong>{artifact.safe_label}</strong><p>{artifact.verification_state.replaceAll("_", " ").toLowerCase()} · owned by {artifact.owner_role.replaceAll("_", " ").toLowerCase()}</p></span></article>)}</div> : <div className={styles.emptyStage}><Clock3 aria-hidden="true" /><h3>No verified result yet</h3><p>The selected action has not produced the required action-specific artifacts. No completion is inferred from workflow status alone.</p></div>}
      <div className={styles.resultStates}><article><small>Payment</small><strong>{view.payment?.status ?? "Not required"}</strong><p>A receipt appears only when money moved.</p></article><article><small>Fulfillment</small><strong>{view.fulfillment?.status ?? "Not started"}</strong><p>Entitlement is verified separately from charge.</p></article><article><small>Company stack</small><strong>{view.stack_change?.status ?? "No change applied"}</strong><p>{view.stack_change?.summary ?? "The current Stack remains unchanged."}</p></article><article><small>Outcome</small><strong>Checkpoint not reached</strong><p>Adoption and business outcome need their own evidence.</p></article></div>
    </section>
  );
}

function StageCanvas(props: {
  stage: string;
  view: DecisionView;
  onLedger: () => void;
  onSelect: (option: SolutionOption) => void;
  onFeedback: (option: SolutionOption, action: OptionFeedbackAction) => void;
  pendingFeedback: boolean;
}) {
  if (props.stage === "need") return <NeedStage view={props.view} />;
  if (props.stage === "company-fit") return <CompanyFitStage view={props.view} />;
  if (props.stage === "action") return <ActionStage view={props.view} />;
  if (props.stage === "result") return <ResultStage view={props.view} />;
  return <OptionsStage view={props.view} onLedger={props.onLedger} onSelect={props.onSelect} onFeedback={props.onFeedback} pendingFeedback={props.pendingFeedback} />;
}

function LedgerDialog({ open, close, view }: { open: boolean; close: () => void; view: DecisionView }) {
  const ref = useRef<HTMLDialogElement>(null);
  useNativeDialog(ref, open);
  const leading = view.solution_options[0];
  return (
    <dialog className={styles.ledgerDialog} ref={ref} onClose={close}>
      <div className={styles.ledgerHead}><div><p>Decision Ledger</p><h2>Why this action</h2><span>Decision v{view.request.decision_version} · {view.evaluation.pipeline_version}</span></div><button type="button" aria-label="Close Decision Ledger" onClick={close}><X aria-hidden="true" /></button></div>
      <div className={styles.ledgerContent}>
        <section><p>Why this action</p><h3>{leading?.label ?? "No supported action"}</h3><span>{leading?.reason ?? "The evaluated universe did not produce a supported action."}</span><dl><div><dt>Stability</dt><dd>{view.rank_stability.status}</dd></div><div><dt>Evaluated plans</dt><dd>{view.coverage.evaluated_solution_plan_count}</dd></div><div><dt>Company stack</dt><dd>{leading?.default_comparison.stack_change ?? "Unchanged"}</dd></div></dl></section>
        <section><p>Evidence</p><h3>{leading?.evidence.length ?? 0} evidence records on the recommended plan</h3><span>Publisher authority identifies who stands behind a package; it does not mean every claim was independently verified.</span>{leading?.evidence.map((item) => <div className={styles.ledgerItem} key={item.id}><FileCheck2 aria-hidden="true" /><span><strong>{item.label}</strong><small>{item.publisher_authority.replaceAll("_", " ")} · {item.verification_state}</small></span></div>)}</section>
        <section><p>What could change</p><h3>Named evidence frontier</h3>{view.rank_stability.evidence_frontier.length ? view.rank_stability.evidence_frontier.map((item) => <div className={styles.frontierItem} key={`${item.criterion_id}-${item.reason_code}`}><CircleAlert aria-hidden="true" /><span><strong>{item.reason_code.replaceAll("_", " ")}</strong><small>{item.permitted_resolution}</small></span></div>) : <span>No current evidence item can reverse first place within supported bounds.</span>}</section>
        <section><p>Audit &amp; math</p><h3>Exact frozen references</h3><code>{view.evaluation.decision_hash}</code><dl><div><dt>Evaluation</dt><dd>{view.evaluation.id}</dd></div><div><dt>Engine</dt><dd>{view.evaluation.engine_version}</dd></div><div><dt>Company profile</dt><dd>v{view.company_context.company_profile_version}</dd></div></dl></section>
      </div>
    </dialog>
  );
}

function SelectPlanDialog({ option, close, confirm, pending }: { option: SolutionOption | null; close: () => void; confirm: () => void; pending: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  useNativeDialog(ref, Boolean(option));
  return (
    <dialog className={styles.confirmDialog} ref={ref} onClose={close}>
      {option ? <div><span className={styles.confirmIcon}><FileCheck2 aria-hidden="true" /></span><p>Exact plan selection</p><h2>Select this action plan?</h2><span>This creates a new immutable Decision version. It does not approve, pay, or execute.</span><dl><div><dt>Action</dt><dd>{option.label}</dd></div><div><dt>Comparable cost</dt><dd>{option.default_comparison.cost.currency} {option.default_comparison.cost.amount}</dd></div><div><dt>Stack change</dt><dd>{option.default_comparison.stack_change}</dd></div></dl>{WEB_DATA_MODE === "fixture" ? <p className={styles.fixtureDialogNote}>Development fixture: selection is disabled because no backend record can be created.</p> : null}<footer><button type="button" onClick={close}>Cancel</button><button className={styles.primaryButton} type="button" disabled={pending || WEB_DATA_MODE === "fixture"} onClick={confirm}>{pending ? "Selecting…" : "Select exact plan"}</button></footer></div> : null}
    </dialog>
  );
}

export function DecisionRoom({ requestId, version, stage }: { requestId: string; version: string; stage: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [mobileRail, setMobileRail] = useState(false);
  const [mobileChat, setMobileChat] = useState(false);
  const [ledgerOpen, setLedgerOpen] = useState(false);
  const [selectedOption, setSelectedOption] = useState<SolutionOption | null>(null);
  const [toast, setToast] = useState("");
  const mobileChatRef = useRef<HTMLDialogElement>(null);

  useNativeDialog(mobileChatRef, mobileChat);

  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(""), 3600);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const query = useQuery({
    queryKey: ["decision-view", requestId],
    enabled: WEB_DATA_MODE === "api",
    queryFn: () => getBrowserApiClient().request("get_decision_room", { pathParams: { request_id: requestId }, headers: buyerDevelopmentHeaders }),
  });
  const loadedView = WEB_DATA_MODE === "fixture"
    ? requestId === decisionFixture.request.id
      ? decisionFixture
      : undefined
    : query.data;
  const versionMismatch = Boolean(
    loadedView && String(loadedView.request.decision_version) !== version,
  );
  const fixtureRequestMissing = WEB_DATA_MODE === "fixture" && !loadedView;
  const view = versionMismatch ? undefined : loadedView;

  const feedbackMutation = useMutation({
    mutationFn: ({ option, action }: { option: SolutionOption; action: OptionFeedbackAction }) => getBrowserApiClient().request("record_solution_option_feedback", {
      pathParams: { request_id: requestId, solution_plan_id: option.id },
      body: { action, reason: `Recorded from the ${stage} stage` },
      idempotencyKey: createIdempotencyKey(`${action}-${option.id}`),
      headers: buyerDevelopmentHeaders,
    }),
    onSuccess: () => setToast("Feedback recorded. The current Decision version and ranking were not silently changed."),
    onError: () => setToast("Feedback was not recorded. The current Decision remains unchanged."),
  });

  const selectMutation = useMutation({
    mutationFn: async (option: SolutionOption) => {
      if (!view) throw new Error("Decision not loaded");
      const action = view.workflow.available_actions.find((item) => item.id === "SELECT_PLAN");
      const decisionId = action?.href.match(/\/v1\/decisions\/([^/]+)\/plan-selections/)?.[1];
      if (!decisionId) throw new Error("Server did not provide a selectable decision action");
      return getBrowserApiClient().request("select_action_plan", {
        pathParams: { decision_id: decisionId },
        body: { decision_hash: view.evaluation.decision_hash, decision_version: view.request.decision_version, solution_plan_id: option.id },
        idempotencyKey: createIdempotencyKey(`select-${view.evaluation.decision_hash}-${option.id}`),
        headers: buyerDevelopmentHeaders,
      });
    },
    onSuccess: (result) => {
      setSelectedOption(null);
      void queryClient.invalidateQueries({ queryKey: ["decision-view", requestId] });
      router.push(`/decisions/${requestId}/versions/${result.decision_version}/action`);
    },
    onError: () => setToast("The plan was not selected. No approval, payment, or action run was created."),
  });

  const activeStage = stages.some((item) => item.slug === stage) ? stage : "options";
  const title = view?.request.intent ?? "Decision Room";

  return (
    <div className={styles.appShell}>
      <WorkspaceRail />
      <MobileRailDialog open={mobileRail} close={() => setMobileRail(false)} />
      {view ? <LedgerDialog open={ledgerOpen} close={() => setLedgerOpen(false)} view={view} /> : null}
      <SelectPlanDialog option={selectedOption} close={() => setSelectedOption(null)} confirm={() => selectedOption && selectMutation.mutate(selectedOption)} pending={selectMutation.isPending} />
      <dialog className={styles.chatDialog} ref={mobileChatRef} onClose={() => setMobileChat(false)}><div className={styles.mobileDialogHead}><strong>Decision conversation</strong><button type="button" aria-label="Close conversation" onClick={() => setMobileChat(false)}><X aria-hidden="true" /></button></div><ConversationPanel compact /></dialog>
      <main className={styles.roomMain}>
        {WEB_DATA_MODE === "fixture" ? <FixtureBanner /> : null}
        {query.isError ? <ApiErrorBanner retry={() => void query.refetch()} /> : null}
        {versionMismatch ? <RouteMismatchBanner message={`The server returned v${loadedView?.request.decision_version}; it was not substituted for requested v${version}.`} /> : null}
        {fixtureRequestMissing ? <RouteMismatchBanner message="No deterministic fixture exists for this request identifier." /> : null}
        <header className={styles.roomHeader}>
          <button className={styles.mobileMenuButton} type="button" aria-label="Open navigation" onClick={() => setMobileRail(true)}><Menu aria-hidden="true" /></button>
          <div className={styles.roomTitle}><p>Decision v{view?.request.decision_version ?? version} · {view?.request.decision_state.toLowerCase() ?? "loading"}</p><h1>{title}</h1></div>
          <div className={styles.roomHeaderActions}><span className={styles.privacyBadge}><LockKeyhole aria-hidden="true" /> Private</span><button type="button" onClick={() => setMobileChat(true)}><MessageSquareText aria-hidden="true" /> Chat</button><button type="button" onClick={() => setLedgerOpen(true)}><PanelRightOpen aria-hidden="true" /> Details</button></div>
        </header>
        {view ? <DecisionPath view={view} requestId={requestId} version={String(view.request.decision_version)} currentSlug={activeStage} /> : <div className={styles.pathSkeleton} />}
        <div className={styles.roomBody}>
          <ConversationPanel />
          <div className={styles.structuredCanvas} id="main-content">
            {query.isPending && WEB_DATA_MODE === "api" ? <div className={styles.canvasLoading}><i /><i /><i /></div> : null}
            {view ? <StageCanvas stage={activeStage} view={view} onLedger={() => setLedgerOpen(true)} onSelect={setSelectedOption} onFeedback={(option, action) => feedbackMutation.mutate({ option, action })} pendingFeedback={feedbackMutation.isPending} /> : query.isError ? <div className={styles.emptyStage}><CircleAlert aria-hidden="true" /><h2>Decision unavailable</h2><p>The last verified state cannot be loaded. Retry after the local API is available.</p></div> : versionMismatch || fixtureRequestMissing ? <div className={styles.emptyStage}><CircleAlert aria-hidden="true" /><h2>Nothing was substituted</h2><p>The requested immutable decision record is not available in this data mode.</p></div> : null}
          </div>
        </div>
      </main>
      <div className={toast ? styles.toastVisible : styles.toast} role="status">{toast}</div>
    </div>
  );
}
