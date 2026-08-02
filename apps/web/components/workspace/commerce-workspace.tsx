"use client";

import {
  Activity,
  ArrowRight,
  BadgeCheck,
  Check,
  ChevronDown,
  Circle,
  CircleAlert,
  Clock3,
  Code2,
  Expand,
  Eye,
  FileCheck2,
  FileSearch,
  FolderKanban,
  Grid2X2,
  Inbox,
  Layers3,
  LoaderCircle,
  LockKeyhole,
  MessageSquare,
  MoreHorizontal,
  Package,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightOpen,
  Paperclip,
  Plug,
  Plus,
  Search,
  SendHorizontal,
  Settings2,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import Link from "next/link";
import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type RefObject,
} from "react";
import { prepareWithSegments, walkLineRanges } from "@chenglou/pretext";

import { WEB_DATA_MODE } from "@/lib/api";
import { WORKSPACE_ACCOUNTS } from "@/components/home/workspace-account";

import { ChatMessageBody } from "./chat-message";
import styles from "./commerce-workspace.module.css";

export type CommerceWorkspaceMode = "sira" | "seil";
export type CommerceContextTab = "run" | "work" | "connectors";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  meta?: string;
};

type Conversation = {
  id: string;
  mode: CommerceWorkspaceMode;
  title: string;
  updatedLabel: string;
  messages: ChatMessage[];
};

type RunStep = {
  label: string;
  detail: string;
  state: "complete" | "current" | "waiting";
};

type Connector = {
  name: string;
  purpose: string;
  status: "Healthy" | "Needs setup" | "Not connected";
  meta: string;
};

const MODE_COPY = {
  sira: {
    accentLabel: "Buying agent",
    emptyPrompt: "What does your company need to buy or change?",
    name: "SIRA",
    privacy: "Private to your company",
  },
  seil: {
    accentLabel: "Selling agent",
    emptyPrompt: "What product or buyer question should we work on?",
    name: "SEIL",
    privacy: "Private to your seller workspace",
  },
} as const;

const SEED_CONVERSATIONS: Record<CommerceWorkspaceMode, Conversation[]> = {
  sira: [
    {
      id: "sira-meeting-intelligence",
      mode: "sira",
      title: "Meeting-intelligence renewal",
      updatedLabel: "2 min",
      messages: [
        {
          id: "sira-user-1",
          role: "user",
          content:
            "We need to decide whether to renew our meeting-intelligence tool or replace it. We have ten consultants and the contract renews on 19 August.",
        },
        {
          id: "sira-assistant-1",
          role: "assistant",
          meta: "Decision plan updated",
          content:
            "## I have started the decision\n\nThe goal is clear: keep client conversations private while making source-linked answers easy for ten consultants.\n\n**What I am checking now**\n\n- your current contract and stack dependencies\n- company requirements that can block an option\n- reuse, resize, renew, and replacement actions\n- the exact approval path if money needs to move\n\nI found **10 supported actions to evaluate**. The live plan and current options are open on the right.",
        },
      ],
    },
    {
      id: "sira-crm-renewal",
      mode: "sira",
      title: "Review CRM renewal and seats",
      updatedLabel: "Yesterday",
      messages: [
        {
          id: "sira-crm-user",
          role: "user",
          content: "Check whether we should renew the CRM at the current seat count.",
        },
        {
          id: "sira-crm-assistant",
          role: "assistant",
          content:
            "I can compare renewal, resize, and replacement. I will first need the contract deadline and the number of active seats.",
        },
      ],
    },
    {
      id: "sira-expense-tools",
      mode: "sira",
      title: "Compare expense tools",
      updatedLabel: "31 Jul",
      messages: [],
    },
  ],
  seil: [
    {
      id: "seil-retention-evidence",
      mode: "seil",
      title: "Fix retention evidence",
      updatedLabel: "Today",
      messages: [
        {
          id: "seil-user-1",
          role: "user",
          content:
            "Help me get Northstar Meeting Notes ready for review. What is still missing?",
        },
        {
          id: "seil-assistant-1",
          role: "assistant",
          meta: "Product Evidence checked",
          content:
            "## One evidence gap is blocking review\n\nYour core Product Evidence is **9 of 12 fields complete**. The current retention claim says 30 days, but its supporting source needs a newer observed date.\n\n**Next best action**\n\n1. Attach the current retention policy.\n2. Confirm the claim still applies to the published product.\n3. Re-run validation.\n\nI opened the exact field and review path on the right.",
        },
      ],
    },
    {
      id: "seil-launch-pack",
      mode: "seil",
      title: "Prepare launch evidence",
      updatedLabel: "Yesterday",
      messages: [],
    },
    {
      id: "seil-fit-questions",
      mode: "seil",
      title: "Review buyer fit questions",
      updatedLabel: "30 Jul",
      messages: [],
    },
  ],
};

const RUN_STEPS: Record<CommerceWorkspaceMode, RunStep[]> = {
  sira: [
    { label: "Need understood", detail: "Outcome, deadline, and owner captured", state: "complete" },
    { label: "Company fit", detail: "Private rules and stack checked", state: "complete" },
    { label: "Compare actions", detail: "Evaluating 10 supported actions", state: "current" },
    { label: "Authority", detail: "Waiting for an exact plan", state: "waiting" },
    { label: "Verify result", detail: "Starts after execution", state: "waiting" },
  ],
  seil: [
    { label: "Product identity", detail: "Claim and seller scope confirmed", state: "complete" },
    { label: "Claims compiled", detail: "9 of 12 required fields complete", state: "complete" },
    { label: "Evidence check", detail: "Retention source needs attention", state: "current" },
    { label: "Independent review", detail: "Waiting for a valid revision", state: "waiting" },
    { label: "Publish", detail: "Available after approval", state: "waiting" },
  ],
};

const CONNECTORS: Record<CommerceWorkspaceMode, Connector[]> = {
  sira: [
    { name: "Senso", purpose: "Company files and decision evidence", status: "Healthy", meta: "Last sync 8 min ago" },
    { name: "Prava", purpose: "Cardholder authorization and checkout", status: "Needs setup", meta: "Sandbox key detected" },
    { name: "Google Workspace", purpose: "Inventory and team context", status: "Healthy", meta: "Read-only scope" },
    { name: "Slack", purpose: "Safe assignment notifications", status: "Not connected", meta: "Optional" },
  ],
  seil: [
    { name: "Senso", purpose: "Seller sources and evidence sync", status: "Healthy", meta: "4 sources ready" },
    { name: "Help center", purpose: "Published documentation crawl", status: "Healthy", meta: "Checked today" },
    { name: "Merchant", purpose: "Quote, checkout, and fulfillment", status: "Needs setup", meta: "Certification pending" },
    { name: "Slack", purpose: "Review and publication alerts", status: "Not connected", meta: "Optional" },
  ],
};

function cloneSeedConversations() {
  if (WEB_DATA_MODE !== "fixture") {
    return {
      sira: [{ id: "sira-structured", mode: "sira" as const, title: "SIRA workspace", updatedLabel: "Structured", messages: [] }],
      seil: [{ id: "seil-structured", mode: "seil" as const, title: "SEIL workspace", updatedLabel: "Structured", messages: [] }],
    };
  }
  return {
    sira: SEED_CONVERSATIONS.sira.map((conversation) => ({
      ...conversation,
      messages: conversation.messages.map((message) => ({ ...message })),
    })),
    seil: SEED_CONVERSATIONS.seil.map((conversation) => ({
      ...conversation,
      messages: conversation.messages.map((message) => ({ ...message })),
    })),
  };
}

function buildConversationTitle(prompt: string) {
  const words = prompt.replace(/\s+/g, " ").trim().split(" ").slice(0, 7).join(" ");
  return words.length > 46 ? `${words.slice(0, 43).trim()}...` : words || "New chat";
}

function responseFor(mode: CommerceWorkspaceMode, prompt: string) {
  const normalized = prompt.toLowerCase();

  if (mode === "sira") {
    if (normalized.includes("connector") || normalized.includes("senso") || normalized.includes("prava")) {
      return "## Connector status is open\n\nI moved the work panel to **Connectors**. Senso is healthy, while Prava still needs production setup before a live charged purchase can run.\n\nNo purchase or company record was changed.";
    }
    if (normalized.includes("product") || normalized.includes("option") || normalized.includes("compare")) {
      return "## I opened the evaluated options\n\nThe right panel now separates supported actions from company-blocked and seller-unsupported options. Selection remains separate from approval and payment.";
    }
    return "## I added this to the decision workspace\n\nI will use it to refine the need, company fit, and evaluated actions. The structured decision on the right remains the record that governs selection and execution.";
  }

  if (normalized.includes("connector") || normalized.includes("source")) {
    return "## Source connections are open\n\nI moved the work panel to **Connectors**. The evidence sources are healthy; merchant fulfillment still needs setup before an offer can execute.";
  }
  if (normalized.includes("product") || normalized.includes("evidence") || normalized.includes("claim")) {
    return "## I opened Product Evidence\n\nThe right panel shows the current product, publication state, and the exact evidence gap. Private seller material stays in this workspace and is not sent to buyers.";
  }
  return "## I added this to the seller workspace\n\nI will use it to improve the product record, evidence, fit rules, and buyer-ready answers. Only reviewed fields can become published Product Evidence.";
}

function useIsCompact() {
  const [compact, setCompact] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(max-width: 767px)");
    const sync = () => setCompact(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  return compact;
}

function usePretextMessages(
  rootRef: RefObject<HTMLElement | null>,
  version: string,
) {
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    let cancelled = false;
    let resizeObserver: ResizeObserver | undefined;

    const start = async () => {
      await document.fonts.ready;
      if (cancelled) return;

      const elements = Array.from(
        root.querySelectorAll<HTMLElement>("[data-pretext-message]"),
      );

      const relayout = () => {
        for (const element of elements) {
          const width = element.getBoundingClientRect().width;
          if (width <= 0) continue;
          const computed = getComputedStyle(element);
          const lineHeight = Number.parseFloat(computed.lineHeight) || 28;
          const prepared = prepareWithSegments(
            element.textContent ?? "",
            computed.font,
          );
          let lineCount = 0;
          walkLineRanges(prepared, width, () => {
            lineCount += 1;
          });
          element.style.setProperty(
            "--measured-text-height",
            `${Math.ceil(lineCount * lineHeight)}px`,
          );
        }
      };

      resizeObserver = new ResizeObserver(relayout);
      resizeObserver.observe(root);
      relayout();
    };

    void start();
    return () => {
      cancelled = true;
      resizeObserver?.disconnect();
    };
  }, [rootRef, version]);
}

function Sidebar({
  mode,
  modeLocked,
  contextTab,
  conversations,
  selectedConversationId,
  onModeChange,
  onNewChat,
  onSelectConversation,
  onClose,
  onOpenContext,
}: {
  mode: CommerceWorkspaceMode;
  modeLocked: boolean;
  contextTab: CommerceContextTab;
  conversations: Conversation[];
  selectedConversationId: string;
  onModeChange: (mode: CommerceWorkspaceMode) => void;
  onNewChat: () => void;
  onSelectConversation: (id: string) => void;
  onClose: () => void;
  onOpenContext: (tab: CommerceContextTab) => void;
}) {
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const visibleConversations = conversations.filter((conversation) =>
    conversation.title.toLowerCase().includes(searchQuery.trim().toLowerCase()),
  );
  const account = WORKSPACE_ACCOUNTS[mode];

  return (
    <aside className={styles.sidebar} aria-label={`${MODE_COPY[mode].name} navigation`}>
      <div className={styles.sidebarHeader}>
        <div className={styles.brandRow}>
          <button className={styles.brand} type="button" onClick={() => onOpenContext("run")}>
            <span>
              <strong>{MODE_COPY[mode].name}</strong>
              <small>{MODE_COPY[mode].accentLabel}</small>
            </span>
          </button>
          <div className={styles.sidebarHeaderActions}>
            <button type="button" aria-label="Search chats" title="Search chats" aria-expanded={searchOpen} onClick={() => setSearchOpen((current) => !current)}>
              <Search aria-hidden="true" />
            </button>
            <button type="button" aria-label="Hide sidebar" title="Hide sidebar" onClick={onClose}>
              <PanelLeftClose aria-hidden="true" />
            </button>
          </div>
        </div>

        {searchOpen ? (
          <label className={styles.chatSearch}>
            <span className="sr-only">Search recent chats</span>
            <Search aria-hidden="true" />
            <input autoFocus type="search" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Search chats" />
          </label>
        ) : null}

        {!modeLocked ? (
          <div className={styles.modeSwitcher} aria-label="Choose agent">
            {(["sira", "seil"] as const).map((item) => (
              <button
                className={mode === item ? styles.activeMode : undefined}
                key={item}
                onClick={() => onModeChange(item)}
                type="button"
              >
                {item.toUpperCase()}
              </button>
            ))}
          </div>
        ) : null}

        <button className={styles.newChatButton} type="button" onClick={onNewChat}>
          <Plus aria-hidden="true" />
          New chat
        </button>
      </div>

      <nav className={styles.sidebarNav} aria-label="Workspace">
        <button className={contextTab === "run" ? styles.activeNav : undefined} type="button" onClick={() => onOpenContext("run")} aria-pressed={contextTab === "run"}>
          <MessageSquare aria-hidden="true" /> Chats
        </button>
        <Link href={mode === "sira" ? "/sira/decisions" : "/seil/products/search"}>
          {mode === "sira" ? <Layers3 aria-hidden="true" /> : <Package aria-hidden="true" />}
          {mode === "sira" ? "Decisions" : "Products"}
        </Link>
        <button className={contextTab === "connectors" ? styles.activeNav : undefined} type="button" onClick={() => onOpenContext("connectors")} aria-pressed={contextTab === "connectors"}>
          <Plug aria-hidden="true" /> Connectors
        </button>
        <Link href={`/${mode}/inbox`}>
          <Inbox aria-hidden="true" /> Inbox
          <span>{mode === "sira" ? 2 : 1}</span>
        </Link>
      </nav>

      <div className={styles.sidebarDivider} />

      <div className={styles.recentsHeader}>
        <span>Recents</span>
        <Settings2 aria-hidden="true" />
      </div>
      <div className={styles.recentList}>
        {visibleConversations.map((conversation) => (
          <button
            className={conversation.id === selectedConversationId ? styles.activeRecent : undefined}
            key={conversation.id}
            onClick={() => onSelectConversation(conversation.id)}
            type="button"
          >
            <span>
              <strong>{conversation.title}</strong>
              <small>{conversation.updatedLabel}</small>
            </span>
            <MoreHorizontal aria-hidden="true" />
          </button>
        ))}
        {!visibleConversations.length ? <p className={styles.emptyRecents}>No chats match that search.</p> : null}
      </div>

      <div className={styles.sidebarFooter}>
        <Link href={`/${mode}/settings/profile`} aria-label={`Open ${MODE_COPY[mode].name} profile settings`}>
          <span className={styles.avatar}>{account.initials}</span>
          <span>
            <strong>{account.name}</strong>
            <small>{account.roleShort}</small>
          </span>
          <Settings2 aria-hidden="true" />
        </Link>
      </div>
    </aside>
  );
}

function RunPanel({ mode, running }: { mode: CommerceWorkspaceMode; running: boolean }) {
  const steps = RUN_STEPS[mode];
  const completeCount = steps.filter((step) => step.state === "complete").length;

  return (
    <div className={styles.contextBody}>
      <section className={styles.runHero}>
        <div className={styles.runEyebrow}>
          <span className={styles.liveDot} />
          {WEB_DATA_MODE === "fixture" ? (running ? "Preview response" : "Sample agent run") : (running ? "Agent working" : "Current agent run")}
        </div>
        <h2>{mode === "sira" ? "Meeting-intelligence decision" : "Product Evidence review"}</h2>
        <p>
          {mode === "sira"
            ? "SIRA is checking company fit before it recommends an exact action."
            : "SEIL is checking the seller record before it can enter independent review."}
        </p>
        <div className={styles.progressTrack} aria-label={`${completeCount} of ${steps.length} steps completed`}>
          <span style={{ width: `${((completeCount + (running ? 0.5 : 1)) / steps.length) * 100}%` }} />
        </div>
        <div className={styles.runMeta}>
          <span>{completeCount} complete</span>
          <span>{steps.length - completeCount} remaining</span>
        </div>
      </section>

      <section className={styles.contextSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span>Plan</span>
            <h3>What the agent is doing</h3>
          </div>
          {running ? <LoaderCircle className={styles.spin} aria-label="Running" /> : <Activity aria-hidden="true" />}
        </div>
        <ol className={styles.runSteps}>
          {steps.map((step) => (
            <li data-state={step.state} key={step.label}>
              <span className={styles.stepIcon}>
                {step.state === "complete" ? <Check aria-hidden="true" /> : step.state === "current" ? <LoaderCircle aria-hidden="true" /> : <Circle aria-hidden="true" />}
              </span>
              <div>
                <strong>{step.label}</strong>
                <small>{step.detail}</small>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className={styles.contextSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span>Boundary</span>
            <h3>{MODE_COPY[mode].privacy}</h3>
          </div>
          <LockKeyhole aria-hidden="true" />
        </div>
        <p className={styles.sectionCopy}>
          {mode === "sira"
            ? "Nothing is sent to a seller unless you choose Ask vendor and confirm the sanitized brief."
            : "Private sources and draft claims stay seller-private. Buyers receive only reviewed, published fields."}
        </p>
      </section>
    </div>
  );
}

function SiraWorkPanel() {
  return (
    <div className={styles.contextBody}>
      <section className={styles.documentHeader}>
        <span>Decision v1</span>
        <h2>Meeting-intelligence renewal</h2>
        <p>Best supported action among the 10 options evaluated for Northstar Advisory.</p>
        <div className={styles.documentMeta}>
          <span><Clock3 aria-hidden="true" /> Due 19 Aug</span>
          <span><ShieldCheck aria-hidden="true" /> Selective</span>
        </div>
      </section>

      <section className={styles.pathSection} aria-label="Decision path">
        {["Need", "Company fit", "Options", "Action", "Result"].map((stage, index) => (
          <div data-state={index < 2 ? "complete" : index === 2 ? "current" : "waiting"} key={stage}>
            <span>{index < 2 ? <Check aria-hidden="true" /> : index + 1}</span>
            <small>{stage}</small>
          </div>
        ))}
      </section>

      <section className={styles.contextSection}>
        <div className={styles.sectionHeading}>
          <div><span>Options</span><h3>Current comparison</h3></div>
          <Grid2X2 aria-hidden="true" />
        </div>
        <div className={styles.optionList}>
          <article data-tone="supported">
            <div><strong>Replace with Northstar Meeting Notes</strong><span>Recommended</span></div>
            <p>Supported for the company context, with low stack risk.</p>
            <dl><div><dt>Cost</dt><dd>$89 / month</dd></div><div><dt>Action</dt><dd>Replace</dd></div></dl>
          </article>
          <article>
            <div><strong>CurrentCall Workspace</strong><span>Runner-up</span></div>
            <p>Supported, but needs more administration effort.</p>
            <dl><div><dt>Cost</dt><dd>$62 / month</dd></div><div><dt>Action</dt><dd>Buy</dd></div></dl>
          </article>
          <article data-tone="blocked">
            <div><strong>Briefly Capture</strong><span>Blocked</span></div>
            <p>Fails a private company requirement. The seller did not block it.</p>
            <dl><div><dt>Cost</dt><dd>$49 / month</dd></div><div><dt>Action</dt><dd>Do not select</dd></div></dl>
          </article>
        </div>
      </section>

      <Link className={styles.fullViewLink} href="/decisions/req_demo/versions/1/options">
        Open full decision <ArrowRight aria-hidden="true" />
      </Link>
    </div>
  );
}

function SeilWorkPanel() {
  return (
    <div className={styles.contextBody}>
      <section className={styles.documentHeader}>
        <span>Seller workspace</span>
        <h2>Northstar Meeting Notes</h2>
        <p>Structured Product Evidence that buyers can evaluate and reuse.</p>
        <div className={styles.documentMeta}>
          <span><FileCheck2 aria-hidden="true" /> Seller draft</span>
          <span><BadgeCheck aria-hidden="true" /> Compiled by Seilnsara</span>
        </div>
      </section>

      <section className={styles.healthSection}>
        <div className={styles.healthScore}><strong>75%</strong><span>Pack health</span></div>
        <dl>
          <div><dt>Complete</dt><dd>9</dd></div>
          <div><dt>Required</dt><dd>12</dd></div>
          <div><dt>Stale</dt><dd>1</dd></div>
          <div><dt>Conflict</dt><dd>1</dd></div>
        </dl>
      </section>

      <section className={styles.contextSection}>
        <div className={styles.sectionHeading}>
          <div><span>Needs attention</span><h3>Evidence and review</h3></div>
          <FileSearch aria-hidden="true" />
        </div>
        <div className={styles.evidenceList}>
          <article data-tone="warning">
            <CircleAlert aria-hidden="true" />
            <div><strong>Data retention</strong><p>Confirm the 30-day value with current supporting evidence.</p></div>
          </article>
          <article>
            <Check aria-hidden="true" />
            <div><strong>Customer data training</strong><p>Claim and source are current.</p></div>
          </article>
          <article>
            <Check aria-hidden="true" />
            <div><strong>Supported regions</strong><p>United States and Canada confirmed.</p></div>
          </article>
        </div>
      </section>

      <section className={styles.contextSection}>
        <div className={styles.sectionHeading}>
          <div><span>Publication</span><h3>Next authorized step</h3></div>
          <FolderKanban aria-hidden="true" />
        </div>
        <p className={styles.sectionCopy}>Resolve the validation gap before freezing revision 3 for independent review.</p>
      </section>

      <Link className={styles.fullViewLink} href="/seil/product-evidence/product_fixture_d">
        Open Product Evidence <ArrowRight aria-hidden="true" />
      </Link>
    </div>
  );
}

function ConnectorsPanel({ mode }: { mode: CommerceWorkspaceMode }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  return (
    <div className={styles.contextBody}>
      <section className={styles.documentHeader}>
        <span>{MODE_COPY[mode].name} workspace</span>
        <h2>Connectors</h2>
        <p>Sources and execution services available to this agent workspace.</p>
      </section>

      <section className={styles.connectorList}>
        {CONNECTORS[mode].map((connector) => (
          <article data-status={connector.status.toLowerCase().replace(" ", "-")} key={connector.name}>
            <button type="button" onClick={() => setExpanded((current) => current === connector.name ? null : connector.name)}>
              <span className={styles.connectorIcon}><Plug aria-hidden="true" /></span>
              <span className={styles.connectorCopy}>
                <strong>{connector.name}</strong>
                <small>{connector.purpose}</small>
              </span>
              <span className={styles.connectorStatus}>{connector.status}</span>
              <ChevronDown className={expanded === connector.name ? styles.rotated : undefined} aria-hidden="true" />
            </button>
            {expanded === connector.name ? (
              <div className={styles.connectorDetail}>
                <span>{connector.meta}</span>
                <p>Connector credentials are never displayed in the browser. Setup and recovery use the server-authorized flow.</p>
              </div>
            ) : null}
          </article>
        ))}
      </section>

      <div className={styles.contextNote}>
        <ShieldCheck aria-hidden="true" />
        <p>A missing connector lowers confidence or blocks only the actions that require it. Manual work remains available when policy permits.</p>
      </div>
    </div>
  );
}

function ContextPanel({
  mode,
  tab,
  running,
  expanded,
  onTabChange,
  onClose,
  onToggleExpanded,
}: {
  mode: CommerceWorkspaceMode;
  tab: CommerceContextTab;
  running: boolean;
  expanded: boolean;
  onTabChange: (tab: CommerceContextTab) => void;
  onClose: () => void;
  onToggleExpanded: () => void;
}) {
  return (
    <aside className={`${styles.contextPanel} ${expanded ? styles.contextPanelExpanded : ""}`} aria-label="Workspace details">
      <header className={styles.contextHeader}>
        <div className={styles.contextHeaderTools}>
          <button className={tab === "work" ? styles.activeTool : undefined} type="button" onClick={() => onTabChange("work")} aria-label="Show detailed view">
            <Eye aria-hidden="true" />
          </button>
          <button className={tab === "run" ? styles.activeTool : undefined} type="button" onClick={() => onTabChange("run")} aria-label="Show agent run">
            <Code2 aria-hidden="true" />
          </button>
        </div>
        <div className={styles.contextTitle}>
          {tab === "run" ? "Agent run" : tab === "work" ? (mode === "sira" ? "Decision details" : "Product details") : "Connectors"}
        </div>
        <div className={styles.contextHeaderActions}>
          <button type="button" onClick={onToggleExpanded} aria-label={expanded ? "Restore panel width" : "Expand panel"} title={expanded ? "Restore panel width" : "Expand panel"}>
            <Expand aria-hidden="true" />
          </button>
          <button type="button" onClick={onClose} aria-label="Close details" title="Close details">
            <X aria-hidden="true" />
          </button>
        </div>
      </header>

      <div className={styles.contextTabs} role="tablist" aria-label="Detail views">
        <button aria-selected={tab === "run"} onClick={() => onTabChange("run")} role="tab" type="button">Agent run</button>
        <button aria-selected={tab === "work"} onClick={() => onTabChange("work")} role="tab" type="button">{mode === "sira" ? "Decision" : "Product"}</button>
        <button aria-selected={tab === "connectors"} onClick={() => onTabChange("connectors")} role="tab" type="button">Connectors</button>
      </div>

      <div className={styles.contextScroller}>
        {WEB_DATA_MODE !== "fixture" ? (
          <div className={styles.contextBody}>
            <section className={styles.documentHeader}>
              <span>Structured workspace</span>
              <h2>Agent messaging is not connected here yet</h2>
              <p>Use the server-backed {mode === "sira" ? "Decision" : "Product Evidence"} screen. This shell will not substitute sample agent output in API mode.</p>
            </section>
            <Link className={styles.fullViewLink} href={mode === "sira" ? "/sira/decisions" : "/seil/products/search"}>
              Open {mode === "sira" ? "SIRA decisions" : "SEIL products"} <ArrowRight aria-hidden="true" />
            </Link>
          </div>
        ) : null}
        {WEB_DATA_MODE === "fixture" && tab === "run" ? <RunPanel mode={mode} running={running} /> : null}
        {WEB_DATA_MODE === "fixture" && tab === "work" && mode === "sira" ? <SiraWorkPanel /> : null}
        {WEB_DATA_MODE === "fixture" && tab === "work" && mode === "seil" ? <SeilWorkPanel /> : null}
        {WEB_DATA_MODE === "fixture" && tab === "connectors" ? <ConnectorsPanel mode={mode} /> : null}
      </div>
    </aside>
  );
}

export function CommerceWorkspace({
  initialMode = "sira",
  initialContextTab = "run",
  modeLocked = false,
}: {
  initialMode?: CommerceWorkspaceMode;
  initialContextTab?: CommerceContextTab;
  modeLocked?: boolean;
}) {
  const [mode, setMode] = useState<CommerceWorkspaceMode>(initialMode);
  const [conversations, setConversations] = useState(cloneSeedConversations);
  const [selectedByMode, setSelectedByMode] = useState<Record<CommerceWorkspaceMode, string>>({
    sira: SEED_CONVERSATIONS.sira[0].id,
    seil: SEED_CONVERSATIONS.seil[0].id,
  });
  const [composer, setComposer] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [contextOpen, setContextOpen] = useState(true);
  const [contextTab, setContextTab] = useState<CommerceContextTab>(initialContextTab);
  const [contextExpanded, setContextExpanded] = useState(false);
  const [running, setRunning] = useState(false);
  const compact = useIsCompact();
  const messageRootRef = useRef<HTMLDivElement>(null);
  const messageViewportRef = useRef<HTMLDivElement>(null);
  const messageBottomRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const responseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const modeConversations = conversations[mode];
  const selectedConversation =
    modeConversations.find((conversation) => conversation.id === selectedByMode[mode]) ??
    modeConversations[0];
  const messages = selectedConversation?.messages ?? [];
  const messageVersion = `${mode}:${selectedConversation?.id ?? "new"}:${messages.map((message) => `${message.id}:${message.content.length}`).join("|")}`;

  usePretextMessages(messageRootRef, messageVersion);

  useEffect(() => {
    if (shouldAutoScrollRef.current) {
      messageBottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [messageVersion]);

  const previousCompactRef = useRef(false);
  useEffect(() => {
    if (compact && !previousCompactRef.current) {
      setSidebarOpen(false);
      setContextOpen(false);
      setContextExpanded(false);
    }
    previousCompactRef.current = compact;
  }, [compact]);

  useEffect(() => () => {
    if (responseTimerRef.current) clearTimeout(responseTimerRef.current);
  }, []);

  function updateConversation(
    targetMode: CommerceWorkspaceMode,
    conversationId: string,
    update: (conversation: Conversation) => Conversation,
  ) {
    setConversations((current) => ({
      ...current,
      [targetMode]: current[targetMode].map((conversation) =>
        conversation.id === conversationId ? update(conversation) : conversation,
      ),
    }));
  }

  function switchMode(nextMode: CommerceWorkspaceMode) {
    if (modeLocked || nextMode === mode) return;
    setMode(nextMode);
    setComposer("");
    setRunning(false);
    setContextTab("run");
    setContextOpen(true);
    if (compact) setSidebarOpen(false);
  }

  function createNewChat() {
    const id = `${mode}-${crypto.randomUUID()}`;
    const conversation: Conversation = {
      id,
      mode,
      title: "New chat",
      updatedLabel: "Now",
      messages: [],
    };
    setConversations((current) => ({ ...current, [mode]: [conversation, ...current[mode]] }));
    setSelectedByMode((current) => ({ ...current, [mode]: id }));
    setComposer("");
    setContextTab("run");
    setRunning(false);
    if (compact) setSidebarOpen(false);
  }

  function selectConversation(id: string) {
    setSelectedByMode((current) => ({ ...current, [mode]: id }));
    setComposer("");
    setRunning(false);
    if (compact) setSidebarOpen(false);
  }

  function openContext(tab: CommerceContextTab) {
    setContextTab(tab);
    setContextOpen(true);
    if (compact) setSidebarOpen(false);
  }

  function submitMessage(value = composer.trim()) {
    if (WEB_DATA_MODE !== "fixture" || !value || running || !selectedConversation) return;
    const targetMode = mode;
    const conversationId = selectedConversation.id;
    const userMessage: ChatMessage = {
      id: `user-${crypto.randomUUID()}`,
      role: "user",
      content: value,
    };
    const assistantId = `assistant-${crypto.randomUUID()}`;
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      meta: `${MODE_COPY[targetMode].name} is working`,
    };

    updateConversation(targetMode, conversationId, (conversation) => ({
      ...conversation,
      title: conversation.title === "New chat" ? buildConversationTitle(value) : conversation.title,
      updatedLabel: "Now",
      messages: [...conversation.messages, userMessage, assistantMessage],
    }));
    setComposer("");
    setRunning(true);
    setContextTab("run");
    setContextOpen(true);

    responseTimerRef.current = setTimeout(() => {
      const response = responseFor(targetMode, value);
      updateConversation(targetMode, conversationId, (conversation) => ({
        ...conversation,
        messages: conversation.messages.map((message) =>
          message.id === assistantId
            ? { ...message, content: response, meta: "Preview updated" }
            : message,
        ),
      }));
      if (targetMode === mode) setRunning(false);
      responseTimerRef.current = null;
    }, 850);
  }

  function stopResponse() {
    if (responseTimerRef.current) clearTimeout(responseTimerRef.current);
    responseTimerRef.current = null;
    if (selectedConversation) {
      updateConversation(mode, selectedConversation.id, (conversation) => ({
        ...conversation,
        messages: conversation.messages.map((message, index, all) =>
          index === all.length - 1 && message.role === "assistant" && !message.content
            ? { ...message, content: "Paused. Continue whenever you are ready.", meta: "Agent paused" }
            : message,
        ),
      }));
    }
    setRunning(false);
  }

  function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    submitMessage(`Selected source for preview: ${file.name}. File contents were not uploaded.`);
    event.target.value = "";
  }

  const shellClass = [
    styles.workspace,
    !sidebarOpen ? styles.sidebarClosed : "",
    !contextOpen ? styles.contextClosed : "",
    contextExpanded && contextOpen ? styles.contextExpanded : "",
  ].filter(Boolean).join(" ");

  return (
    <main className={shellClass} data-mode={mode}>
      <a className={styles.skipLink} href="#chat-thread">Skip to conversation</a>

      {sidebarOpen ? (
        <Sidebar
          mode={mode}
          modeLocked={modeLocked}
          contextTab={contextTab}
          conversations={modeConversations}
          selectedConversationId={selectedConversation?.id ?? ""}
          onModeChange={switchMode}
          onNewChat={createNewChat}
          onSelectConversation={selectConversation}
          onClose={() => setSidebarOpen(false)}
          onOpenContext={openContext}
        />
      ) : null}

      <section className={styles.chatPanel} aria-label={`${MODE_COPY[mode].name} conversation`}>
        <header className={styles.chatHeader}>
          <div className={styles.chatHeaderLeft}>
            {!sidebarOpen ? (
              <button type="button" onClick={() => { setSidebarOpen(true); if (compact) setContextOpen(false); }} aria-label="Open sidebar" title="Open sidebar">
                <PanelLeftOpen aria-hidden="true" />
              </button>
            ) : null}
            <div>
              <strong>{selectedConversation?.title ?? "New chat"}</strong>
              <small><span /> {WEB_DATA_MODE === "fixture" ? "Development preview · sample workflow" : `${MODE_COPY[mode].name} ${MODE_COPY[mode].accentLabel.toLowerCase()}`}</small>
            </div>
          </div>
          <div className={styles.chatHeaderActions}>
            <span className={styles.privacyHeader}><LockKeyhole aria-hidden="true" /> {MODE_COPY[mode].privacy}</span>
            <button type="button" onClick={() => { setContextOpen(true); if (compact) setSidebarOpen(false); }} aria-label="Open work panel" title="Open work panel">
              <PanelRightOpen aria-hidden="true" />
            </button>
          </div>
        </header>

        <div
          className={styles.messageViewport}
          id="chat-thread"
          ref={messageViewportRef}
          onScroll={() => {
            const viewport = messageViewportRef.current;
            if (!viewport) return;
            shouldAutoScrollRef.current = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight < 96;
          }}
        >
          <div className={styles.messageColumn} ref={messageRootRef}>
            {messages.length === 0 ? (
              <div className={styles.emptyConversation}>
                <strong className={styles.emptyWordmark}>{MODE_COPY[mode].name}</strong>
                <h1>{MODE_COPY[mode].emptyPrompt}</h1>
                <p>
                  {mode === "sira"
                    ? "Describe the outcome, deadline, or tool you are deciding about."
                    : "Describe the product evidence, buyer question, or selling task."}
                </p>
                <div className={styles.promptSuggestions}>
                  {(mode === "sira"
                    ? ["Compare our current tool", "Review a renewal", "Show connector status"]
                    : ["Check Product Evidence", "Prepare for review", "Show source connectors"]
                  ).map((suggestion) => (
                    <button key={suggestion} type="button" onClick={() => setComposer(suggestion)}>{suggestion}</button>
                  ))}
                </div>
              </div>
            ) : null}

            {messages.map((message) => (
              message.role === "user" ? (
                <article className={styles.userMessage} key={message.id}>
                  <div className={styles.userBubble}>
                    <ChatMessageBody content={message.content} tone="user" />
                  </div>
                </article>
              ) : (
                <article className={styles.assistantMessage} key={message.id}>
                  {message.meta ? <p className={styles.messageMeta}><Sparkles aria-hidden="true" /> {message.meta}</p> : null}
                  {message.content ? <ChatMessageBody content={message.content} /> : (
                    <div className={styles.typingState} role="status"><LoaderCircle className={styles.spin} aria-hidden="true" /> Working through the current context...</div>
                  )}
                </article>
              )
            ))}
            <div ref={messageBottomRef} />
          </div>
        </div>

        <div className={styles.composerDock}>
          <div className={styles.composer}>
            <textarea
              aria-label={`Message ${MODE_COPY[mode].name}`}
              disabled={WEB_DATA_MODE !== "fixture"}
              onChange={(event) => setComposer(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  if (running) stopResponse();
                  else submitMessage();
                }
              }}
              placeholder={WEB_DATA_MODE === "fixture" ? "Write a message..." : "Agent messaging is not connected on this screen"}
              rows={1}
              value={composer}
            />
            <div className={styles.composerToolbar}>
              <div>
                <input className={styles.hiddenFileInput} ref={fileInputRef} type="file" onChange={handleFile} />
                <button type="button" disabled={WEB_DATA_MODE !== "fixture"} onClick={() => fileInputRef.current?.click()} aria-label={WEB_DATA_MODE === "fixture" ? "Choose a source filename for preview" : "Source upload unavailable"} title={WEB_DATA_MODE === "fixture" ? "Preview a source selection" : "Source upload unavailable"}>
                  <Paperclip aria-hidden="true" />
                </button>
              </div>
              <div className={styles.composerActions}>
                {modeLocked ? (
                  <span className={styles.lockedAgent}>{MODE_COPY[mode].name}</span>
                ) : (
                  <label>
                    <span className="sr-only">Choose agent</span>
                    <select value={mode} onChange={(event) => switchMode(event.target.value as CommerceWorkspaceMode)}>
                      <option value="sira">SIRA</option>
                      <option value="seil">SEIL</option>
                    </select>
                    <ChevronDown aria-hidden="true" />
                  </label>
                )}
                <button
                  className={styles.sendButton}
                  type="button"
                  onClick={running ? stopResponse : () => submitMessage()}
                  disabled={WEB_DATA_MODE !== "fixture" || (!running && !composer.trim())}
                  aria-label={running ? "Pause agent" : "Send message"}
                >
                  {running ? <X aria-hidden="true" /> : <SendHorizontal aria-hidden="true" />}
                </button>
              </div>
            </div>
          </div>
          <p className={styles.composerBoundary}>{WEB_DATA_MODE === "fixture" ? `Development preview · no message or file leaves this browser. ${MODE_COPY[mode].privacy}.` : `${MODE_COPY[mode].privacy}. Agent messaging is not connected on this screen.`}</p>
        </div>
      </section>

      {contextOpen ? (
        <ContextPanel
          mode={mode}
          tab={contextTab}
          running={running}
          expanded={contextExpanded}
          onTabChange={setContextTab}
          onClose={() => { setContextOpen(false); setContextExpanded(false); }}
          onToggleExpanded={() => setContextExpanded((current) => !current)}
        />
      ) : null}

      {(compact && (sidebarOpen || contextOpen)) ? (
        <button
          className={styles.mobileScrim}
          type="button"
          aria-label="Close open panel"
          onClick={() => { setSidebarOpen(false); setContextOpen(false); }}
        />
      ) : null}
    </main>
  );
}
