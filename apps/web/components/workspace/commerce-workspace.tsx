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
import { useQuery } from "@tanstack/react-query";
import type { AgentProposalView } from "@sira/api-client";

import {
  buyerDevelopmentHeaders,
  getBrowserApiClient,
  sellerEditorDevelopmentHeaders,
  WEB_DATA_MODE,
} from "@/lib/api";
import { WORKSPACE_ACCOUNTS } from "@/components/home/workspace-account";
import { ProfileSettingsModal } from "@/components/home/profile-preview";

import { ChatMessageBody } from "./chat-message";
import styles from "./commerce-workspace.module.css";

export type CommerceWorkspaceMode = "sira" | "seil";
export type CommerceContextTab = "run" | "work" | "connectors" | "decisions" | "inbox" | "catalog" | "product";

type CatalogProduct = {
  id: string;
  name: string;
  seller: string;
  edition: string;
  price: string;
  billing_unit: string;
  status: string;
  summary: string;
  claims: string[];
  integrations: string[];
  category?: string;
  deployment?: string;
  fit?: string;
  why_company?: string;
  admin_effort?: string;
  evidence_freshness?: string;
  requirement_coverage?: string;
  limitation?: string;
  logo?: string;
  logo_tone?: "blue" | "gold" | "plum" | "teal";
  seats?: string;
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  meta?: string;
  products?: CatalogProduct[];
  toolCalls?: string[];
  proposals?: AgentProposalView[];
};

type Conversation = {
  id: string;
  mode: CommerceWorkspaceMode;
  title: string;
  updatedLabel: string;
  messages: ChatMessage[];
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

const FIXTURE_CATALOG: CatalogProduct[] = [
  {
    id: "product_fixture_d",
    name: "Northstar Notes",
    seller: "Northstar Labs",
    edition: "Team",
    price: "USD 89",
    billing_unit: "workspace_month",
    status: "Published evidence",
    summary: "Source-linked meeting intelligence for client-facing teams with low administration overhead.",
    claims: [
      "Answers link to exact transcript moments.",
      "A ten-seat workspace can be deployed in one day.",
      "Native Google Workspace, Slack, and Zoom integrations are included.",
      "The Team edition supports up to 50 seats.",
    ],
    integrations: ["google_workspace", "slack", "zoom"],
    category: "Meeting intelligence",
    deployment: "1 day",
    fit: "Best company fit",
    why_company: "Fits a ten-consultant team, keeps client conversations private, and works with the tools already in use.",
    admin_effort: "Low",
    evidence_freshness: "Reviewed 2 days ago",
    requirement_coverage: "4 of 4 key needs",
    limitation: "Advanced governance controls require the Enterprise edition.",
    logo: "N",
    logo_tone: "teal",
    seats: "Up to 50 seats",
  },
  {
    id: "product_fixture_c",
    name: "RelayIQ",
    seller: "Relay Systems",
    edition: "Business",
    price: "USD 99",
    billing_unit: "workspace_month",
    status: "Published evidence",
    summary: "Structured meeting capture and controls for growing teams with a dedicated workspace administrator.",
    claims: [
      "Answers link to exact transcript moments.",
      "A ten-seat workspace typically deploys in three days.",
      "Native Google Workspace, Slack, and Zoom integrations are included.",
      "The Business edition supports up to 100 seats.",
    ],
    integrations: ["google_workspace", "slack", "zoom"],
    category: "Conversation intelligence",
    deployment: "3 days",
    fit: "Supported alternative",
    why_company: "Covers the current stack and privacy needs, but needs a named workspace administrator.",
    admin_effort: "Medium",
    evidence_freshness: "Reviewed 6 days ago",
    requirement_coverage: "4 of 4 key needs",
    limitation: "Ongoing administration is heavier than the preferred operating model.",
    logo: "R",
    logo_tone: "blue",
    seats: "Up to 100 seats",
  },
  {
    id: "product_fixture_b",
    name: "Briefly Cloud",
    seller: "Briefly Software",
    edition: "Team",
    price: "USD 79",
    billing_unit: "workspace_month",
    status: "Published evidence",
    summary: "Fast meeting capture for internal teams that do not need shared external-client workspaces.",
    claims: [
      "Customer content is not used for general model training.",
      "A ten-seat workspace can be deployed in one day.",
      "Native Google Workspace, Slack, and Zoom integrations are included.",
      "Restricted shared client workspaces are not supported.",
    ],
    integrations: ["google_workspace", "slack", "zoom"],
    category: "Meeting assistant",
    deployment: "1 day",
    fit: "Internal teams only",
    why_company: "Low-cost option for internal meetings, but it cannot support the required shared client workspaces.",
    admin_effort: "Low",
    evidence_freshness: "Reviewed 12 days ago",
    requirement_coverage: "3 of 4 key needs",
    limitation: "Restricted shared client workspaces are not supported.",
    logo: "B",
    logo_tone: "plum",
    seats: "Up to 50 seats",
  },
  {
    id: "product_fixture_a",
    name: "MemoFlow",
    seller: "MemoFlow Inc.",
    edition: "Starter",
    price: "USD 49",
    billing_unit: "workspace_month",
    status: "Published evidence",
    summary: "A lightweight and affordable way for small teams to capture searchable meeting notes.",
    claims: [
      "Answers link to exact transcript moments.",
      "A ten-seat workspace can be deployed in one day.",
      "Native Google Workspace, Slack, and Zoom integrations are included.",
      "Customer content may be used for general model improvement.",
    ],
    integrations: ["google_workspace", "slack", "zoom"],
    category: "AI meeting notes",
    deployment: "1 day",
    fit: "Policy mismatch",
    why_company: "Affordable and easy to deploy, but its model-improvement policy conflicts with the client-data requirement.",
    admin_effort: "Low",
    evidence_freshness: "Reviewed 8 days ago",
    requirement_coverage: "2 of 4 key needs",
    limitation: "Customer content may be used for general model improvement.",
    logo: "M",
    logo_tone: "gold",
    seats: "Up to 25 seats",
  },
];

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
            "## I have started the decision\n\nThe goal is clear: keep client conversations private while making source-linked answers easy for ten consultants.\n\n**What I am checking now**\n\n- your current contract and stack dependencies\n- company requirements that can block an option\n- reuse, resize, renew, and replacement actions\n- the exact approval path if money needs to move\n\nI found **4 published products** that could support this need. Open any product to review its evidence, pricing, and stack fit.",
          products: FIXTURE_CATALOG,
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

const CONNECTORS: Record<CommerceWorkspaceMode, Connector[]> = {
  sira: [
    { name: "Business Context", purpose: "Company rules, goals, and buying preferences", status: "Needs setup", meta: "Add company documents or confirm details in chat" },
    { name: "Senso", purpose: "Company files and decision evidence", status: "Needs setup", meta: "Server connection required" },
    { name: "DataHub", purpose: "Structured company and product context", status: "Not connected", meta: "Optional" },
    { name: "Google Workspace", purpose: "Inventory and team context", status: "Not connected", meta: "Optional read-only connection" },
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
    if (normalized.includes("product") || normalized.includes("catalog") || normalized.includes("option") || normalized.includes("compare")) {
      return "## I found four published products\n\nThese products have comparable pricing and published evidence for this need. Open a card to review company fit, deployment, integrations, and supported claims.\n\nThis is a **catalogue preview** only; choosing a product remains separate from approval and purchase.";
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

function fixtureProductsForPrompt(mode: CommerceWorkspaceMode, prompt: string) {
  if (mode !== "sira") return [];
  const normalized = prompt.toLowerCase();
  return ["product", "catalog", "software", "option", "compare", "alternative"].some((term) => normalized.includes(term))
    ? FIXTURE_CATALOG
    : [];
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
  onOpenSettings,
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
  onOpenSettings: () => void;
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
        <button className={contextTab === (mode === "sira" ? "decisions" : "catalog") ? styles.activeNav : undefined} type="button" onClick={() => onOpenContext(mode === "sira" ? "decisions" : "catalog")}>
          {mode === "sira" ? <Layers3 aria-hidden="true" /> : <Package aria-hidden="true" />}
          {mode === "sira" ? "Decisions" : "Products"}
        </button>
        <button className={contextTab === "connectors" ? styles.activeNav : undefined} type="button" onClick={() => onOpenContext("connectors")} aria-pressed={contextTab === "connectors"}>
          <Plug aria-hidden="true" /> Connectors
        </button>
        <button className={contextTab === "inbox" ? styles.activeNav : undefined} type="button" onClick={() => onOpenContext("inbox")}>
          <Inbox aria-hidden="true" /> Inbox
        </button>
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
        <button type="button" onClick={onOpenSettings} aria-label={`Open ${MODE_COPY[mode].name} profile settings`}>
          <span className={styles.avatar}>{account.initials}</span>
          <span>
            <strong>{account.name}</strong>
            <small>{account.roleShort}</small>
          </span>
          <Settings2 aria-hidden="true" />
        </button>
      </div>
    </aside>
  );
}

const TOOL_LABELS: Record<string, string> = {
  search_published_products: "Searched published products",
  get_published_product: "Read published product evidence",
  get_purchase_request: "Read purchase request",
  get_purchase_brief: "Read purchase brief",
  get_stack_snapshot: "Checked company stack",
  get_decision_view: "Read current decision",
  get_decision_ledger: "Read decision ledger",
  get_decision_counterfactuals: "Checked counterfactuals",
  get_purchase_status: "Checked purchase status",
  search_seller_products: "Searched seller products",
  get_seller_product_view: "Inspected product evidence health",
  get_seller_pack_draft: "Read evidence-pack draft",
  get_seller_pack_exports: "Checked published exports",
  get_engagement_requirement_brief: "Read shared buyer requirements",
};

function RunPanel({ mode, running, conversation }: { mode: CommerceWorkspaceMode; running: boolean; conversation: Conversation | null }) {
  const latestAssistant = conversation?.messages.findLast((message) => message.role === "assistant" && Boolean(message.content));
  const latestUser = conversation?.messages.findLast((message) => message.role === "user");
  const toolCalls = latestAssistant?.toolCalls ?? [];
  const hasRun = Boolean(latestAssistant);
  const failed = latestAssistant?.meta === "Could not complete";

  return (
    <div className={styles.contextBody}>
      <section className={styles.runHero}>
        <div className={styles.runEyebrow}>
          <span className={styles.liveDot} />
          {running ? "Agent working" : failed ? "Latest run failed" : hasRun ? "Latest completed run" : "No run yet"}
        </div>
        <h2>{conversation?.title ?? `${MODE_COPY[mode].name} workspace`}</h2>
        <p>{running ? `Processing: ${latestUser?.content ?? "your request"}` : failed ? "The request did not complete and no successful tool activity was recorded." : hasRun ? "This is the activity reported by the latest agent response." : `Send a message to start a real ${MODE_COPY[mode].name} run.`}</p>
      </section>

      <section className={styles.contextSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span>Activity</span>
            <h3>{running ? "Run in progress" : "Tools used"}</h3>
          </div>
          {running ? <LoaderCircle className={styles.spin} aria-label="Running" /> : <Activity aria-hidden="true" />}
        </div>
        <ol className={styles.runSteps}>
          {running ? (
            <li data-state="current">
              <span className={styles.stepIcon}>
                <LoaderCircle aria-hidden="true" />
              </span>
              <div><strong>Agent is processing</strong><small>Exact tool activity appears when the run completes.</small></div>
            </li>
          ) : toolCalls.length ? toolCalls.map((tool) => (
            <li data-state="complete" key={tool}>
              <span className={styles.stepIcon}><Check aria-hidden="true" /></span>
              <div><strong>{TOOL_LABELS[tool] ?? tool.replaceAll("_", " ")}</strong><small>{tool}</small></div>
            </li>
          )) : (
            <li data-state={failed ? "waiting" : hasRun ? "complete" : "waiting"}>
              <span className={styles.stepIcon}>{failed ? <CircleAlert aria-hidden="true" /> : hasRun ? <Check aria-hidden="true" /> : <Circle aria-hidden="true" />}</span>
              <div><strong>{failed ? "Request failed" : hasRun ? "Answered without tools" : "Waiting for a message"}</strong><small>{failed ? "Retry when the backend connection is available." : hasRun ? "The latest response did not call an application tool." : "No agent activity has been recorded."}</small></div>
            </li>
          )}
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

function AgentWorkingState({ mode }: { mode: CommerceWorkspaceMode }) {
  const stages = mode === "sira"
    ? ["Understanding your request", "Checking buyer context and product tools", "Preparing a recommendation"]
    : ["Understanding your product task", "Checking seller evidence and pack tools", "Preparing the next step"];
  const [stage, setStage] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setStage((current) => Math.min(current + 1, stages.length - 1));
    }, 1800);
    return () => window.clearInterval(timer);
  }, [stages.length]);

  return (
    <div className={styles.typingState} role="status" aria-live="polite">
      <span className={styles.thinkingMark} aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      <span>{stages[stage]}</span>
    </div>
  );
}

function SiraWorkPanel() {
  if (WEB_DATA_MODE !== "fixture") {
    return (
      <div className={styles.contextBody}>
        <section className={styles.documentHeader}>
          <span>Decision details</span>
          <h2>No decision selected</h2>
          <p>A real decision will appear here after SIRA has enough context and the backend creates a decision record.</p>
        </section>
        <section className={styles.contextSection}>
          <div className={styles.sectionHeading}><div><span>Current state</span><h3>Continue in chat</h3></div><MessageSquare aria-hidden="true" /></div>
          <p className={styles.sectionCopy}>Describe the outcome, users, deadline, constraints, budget, and approval path. This panel will not invent missing decision data.</p>
        </section>
      </div>
    );
  }
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
  if (WEB_DATA_MODE !== "fixture") {
    return (
      <div className={styles.contextBody}>
        <section className={styles.documentHeader}>
          <span>Product details</span>
          <h2>No product selected</h2>
          <p>Select a seller product returned by SEIL before Product Evidence and pack health appear here.</p>
        </section>
        <section className={styles.contextSection}>
          <div className={styles.sectionHeading}><div><span>Current state</span><h3>Continue in chat</h3></div><MessageSquare aria-hidden="true" /></div>
          <p className={styles.sectionCopy}>Ask SEIL to search your products or inspect an exact product ID. This panel will show only backend-supplied evidence.</p>
        </section>
      </div>
    );
  }
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
  const [connectingPrava, setConnectingPrava] = useState(false);
  const query = useQuery({
    queryKey: ["workspace-connectors", mode],
    enabled: WEB_DATA_MODE === "api" && mode === "sira",
    queryFn: () => getBrowserApiClient().request("workspace_connectors", { headers: buyerDevelopmentHeaders }),
  });
  const connectors: Connector[] = WEB_DATA_MODE === "fixture"
    ? CONNECTORS[mode]
    : mode === "sira"
      ? query.data ?? []
      : [];
  return (
    <div className={styles.contextBody}>
      <section className={styles.documentHeader}>
        <span>{MODE_COPY[mode].name} workspace</span>
        <h2>Connectors</h2>
        <p>Sources and execution services available to this agent workspace.</p>
      </section>

      <section className={styles.connectorList}>
        {connectors.map((connector) => (
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
                {mode === "sira" && connector.name === "Prava" && connector.status !== "Healthy" ? (
                  <button
                    type="button"
                    disabled={connectingPrava}
                    onClick={() => {
                      setConnectingPrava(true);
                      void fetch("/v1/connectors/prava/connect", {
                        method: "POST",
                        headers: { "Content-Type": "application/json", ...buyerDevelopmentHeaders },
                      })
                        .then(async (response) => {
                          if (!response.ok) throw new Error("Prava connection failed");
                          const payload = await response.json() as { authorization_url: string };
                          window.location.assign(payload.authorization_url);
                        })
                        .catch(() => setConnectingPrava(false));
                    }}
                  >
                    {connectingPrava ? "Opening Prava…" : "Connect Prava securely"}
                  </button>
                ) : null}
              </div>
            ) : null}
          </article>
        ))}
        {query.isPending && mode === "sira" ? <p className={styles.sectionCopy}>Loading connector status…</p> : null}
        {query.isError ? <p className={styles.sectionCopy}>Connector status is temporarily unavailable.</p> : null}
        {mode === "seil" && WEB_DATA_MODE === "api" ? <p className={styles.sectionCopy}>Seller connector status is not exposed by the backend yet.</p> : null}
      </section>

      <div className={styles.contextNote}>
        <ShieldCheck aria-hidden="true" />
        <p>A missing connector lowers confidence or blocks only the actions that require it. Manual work remains available when policy permits.</p>
      </div>
    </div>
  );
}

function DecisionsPanel({ onStart }: { onStart: () => void }) {
  const query = useQuery({
    queryKey: ["decision-index"],
    enabled: WEB_DATA_MODE === "api",
    queryFn: () => getBrowserApiClient().request("list_decision_requests", { headers: buyerDevelopmentHeaders }),
  });
  const decisions = WEB_DATA_MODE === "api"
    ? [...(query.data?.active ?? []), ...(query.data?.history ?? [])]
    : [];
  return (
    <div className={styles.contextBody}>
      <section className={styles.documentHeader}>
        <span>SIRA workspace</span>
        <h2>Decisions</h2>
        <p>Buying work starts in chat. SIRA keeps asking for material context and turns it into structured decision state.</p>
      </section>
      {decisions.length ? (
        <section className={styles.contextSection}>
          <div className={styles.sectionHeading}><div><span>Backend records</span><h3>{decisions.length} decision{decisions.length === 1 ? "" : "s"}</h3></div><Layers3 aria-hidden="true" /></div>
          <div className={styles.decisionMiniList}>
            {decisions.slice(0, 5).map((decision) => <Link href={decision.href} key={decision.id}><span>{decision.current_stage.replaceAll("_", " ")}</span><strong>{decision.intent}</strong><ArrowRight aria-hidden="true" /></Link>)}
          </div>
          <Link className={styles.fullViewLink} href="/sira/decisions">View all decisions <ArrowRight aria-hidden="true" /></Link>
        </section>
      ) : (
        <section className={styles.contextSection}>
          <div className={styles.sectionHeading}><div><span>Current</span><h3>{query.isPending ? "Loading decisions" : "No decisions yet"}</h3></div><MessageSquare aria-hidden="true" /></div>
          <p className={styles.sectionCopy}>{query.isError ? "Decision records are temporarily unavailable." : "Describe what you need, who will use it, and when. SIRA will create a decision only after confirmation."}</p>
          {!query.isPending ? <button className={styles.fullViewLink} type="button" onClick={onStart}>Start in chat <ArrowRight aria-hidden="true" /></button> : null}
        </section>
      )}
    </div>
  );
}

function InboxPanel({ mode }: { mode: CommerceWorkspaceMode }) {
  const query = useQuery({
    queryKey: ["workspace-inbox", mode, WEB_DATA_MODE],
    enabled: WEB_DATA_MODE === "api",
    queryFn: async () => {
      if (mode === "sira") {
        const result = await getBrowserApiClient().request("list_decision_requests", { headers: buyerDevelopmentHeaders });
        return result.active.map((item) => ({
          href: item.href,
          id: item.id,
          label: item.current_stage.replaceAll("_", " "),
          title: item.intent,
        }));
      }
      const result = await getBrowserApiClient().request("seller_evidence_search_products", {
        headers: sellerEditorDevelopmentHeaders,
        query: {},
      });
      return result.results
        .filter((item) => !["PUBLISHED", "SUPERSEDED"].includes(item.state))
        .map((item) => ({
          href: `/seil/product-evidence/${encodeURIComponent(item.id)}`,
          id: item.id,
          label: item.state.replaceAll("_", " "),
          title: item.name,
        }));
    },
  });
  const items = query.data ?? [];
  return (
    <div className={styles.contextBody}>
      <section className={styles.documentHeader}><span>Assigned work</span><h2>Inbox</h2><p>Requests that need your review or approval appear here without leaving the workspace.</p></section>
      <section className={styles.contextSection}>
        <div className={styles.sectionHeading}><div><span>{items.length ? "Needs attention" : "Up to date"}</span><h3>{query.isPending ? "Loading assigned work" : `${items.length} assigned item${items.length === 1 ? "" : "s"}`}</h3></div><Inbox aria-hidden="true" /></div>
        {items.length ? <div className={styles.decisionMiniList}>{items.map((item) => <Link href={item.href} key={item.id}><span>{item.label}</span><strong>{item.title}</strong><ArrowRight aria-hidden="true" /></Link>)}</div> : <p className={styles.sectionCopy}>{query.isError ? "Assigned work is temporarily unavailable." : "New work appears here only when a real workflow record requires attention."}</p>}
      </section>
    </div>
  );
}

function ProductLogo({ product, large = false }: { product: CatalogProduct; large?: boolean }) {
  const fallback = product.name
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <span
      className={`${styles.productLogo} ${large ? styles.productLogoLarge : ""}`}
      data-tone={product.logo_tone ?? "teal"}
      aria-hidden="true"
    >
      {product.logo ?? fallback}
    </span>
  );
}

function ProductCard({
  product,
  onSelect,
  compact = false,
}: {
  product: CatalogProduct;
  onSelect: (product: CatalogProduct) => void;
  compact?: boolean;
}) {
  return (
    <article className={`${styles.productCard} ${compact ? styles.productCardCompact : ""}`}>
      <button type="button" onClick={() => onSelect(product)} aria-label={`Open ${product.name} details`}>
        <div className={styles.productCardBrand}>
          <ProductLogo product={product} />
          <div>
            <span>{product.seller}</span>
            <small>{product.category ?? "Business software"}</small>
          </div>
          <BadgeCheck aria-label="Published evidence" />
        </div>
        <h3>{product.name}</h3>
        <p>{product.summary}</p>
        <div className={styles.productCompanyReason}>
          <span>Why it fits your company</span>
          <p>{product.why_company ?? "Company fit has not been evaluated yet."}</p>
        </div>
        <div className={styles.productCardFacts}>
          <span>{product.requirement_coverage ?? product.edition}</span>
          <span>{product.deployment ?? "Deployment varies"}</span>
          <span>{product.admin_effort ? `${product.admin_effort} admin effort` : "Admin effort unknown"}</span>
        </div>
        <footer>
          <div><strong>{product.price}</strong><span> / {product.billing_unit.replaceAll("_", " ")}</span></div>
          <span className={styles.productCardAction}>View details <ArrowRight aria-hidden="true" /></span>
        </footer>
      </button>
    </article>
  );
}

function CatalogPanel({ products, onSelect }: { products: CatalogProduct[]; onSelect: (product: CatalogProduct) => void }) {
  return (
    <div className={styles.contextBody}>
      <section className={styles.documentHeader}><span>Published Product Evidence</span><h2>Product catalogue</h2><p>Browse B2B software with comparable pricing, deployment, and fit details. Open a product to inspect its published facts.</p></section>
      <section className={styles.catalogGrid}>
        {products.map((product) => <ProductCard key={product.id} product={product} onSelect={onSelect} />)}
        {!products.length ? <p className={styles.sectionCopy}>Ask SIRA to show products. Catalogue results will appear in this pane and in the conversation.</p> : null}
      </section>
    </div>
  );
}

function ProductPanel({ product, onBack }: { product: CatalogProduct | null; onBack: () => void }) {
  if (!product) return <CatalogPanel products={[]} onSelect={() => undefined} />;
  return (
    <div className={styles.contextBody}>
      <button className={styles.fullViewLink} type="button" onClick={onBack}>Back to catalogue</button>
      <section className={styles.productHero}>
        <div className={styles.productHeroBrand}>
          <ProductLogo product={product} large />
          <div><span>{product.seller}</span><small>{product.category ?? "Business software"}</small></div>
          <span className={styles.productEvidenceBadge}><BadgeCheck aria-hidden="true" /> {product.status}</span>
        </div>
        <h2>{product.name}</h2>
        <p>{product.summary}</p>
        <div className={styles.productPrice}><strong>{product.price}</strong><span>per {product.billing_unit.replaceAll("_", " ")}</span></div>
        <dl className={styles.productSpecs}>
          <div><dt>Edition</dt><dd>{product.edition}</dd></div>
          <div><dt>Company fit</dt><dd>{product.fit ?? "Not evaluated"}</dd></div>
          <div><dt>Deployment</dt><dd>{product.deployment ?? "Varies"}</dd></div>
          <div><dt>Capacity</dt><dd>{product.seats ?? "Contact seller"}</dd></div>
          <div><dt>Requirements</dt><dd>{product.requirement_coverage ?? "Not evaluated"}</dd></div>
          <div><dt>Admin effort</dt><dd>{product.admin_effort ?? "Unknown"}</dd></div>
          <div><dt>Evidence freshness</dt><dd>{product.evidence_freshness ?? "Unknown"}</dd></div>
        </dl>
      </section>
      <section className={styles.contextSection}><div className={styles.sectionHeading}><div><span>Company context</span><h3>Why it makes sense</h3></div><Layers3 aria-hidden="true" /></div><p className={styles.sectionCopy}>{product.why_company ?? "Company fit has not been evaluated yet."}</p>{product.limitation ? <p className={styles.productLimitation}><strong>Important limitation</strong>{product.limitation}</p> : null}</section>
      <section className={styles.contextSection}><div className={styles.sectionHeading}><div><span>Evidence</span><h3>Published claims</h3></div><FileCheck2 aria-hidden="true" /></div><ul>{product.claims.map((claim) => <li key={claim}>{claim}</li>)}</ul></section>
      <section className={styles.contextSection}><div className={styles.sectionHeading}><div><span>Stack fit</span><h3>Native integrations</h3></div><Plug aria-hidden="true" /></div><div className={styles.integrationTags}>{product.integrations.map((item) => <span key={item}>{item.replaceAll("_", " ")}</span>)}</div></section>
    </div>
  );
}

function ContextPanel({
  mode,
  conversation,
  tab,
  running,
  expanded,
  onTabChange,
  onClose,
  onToggleExpanded,
  products,
  selectedProduct,
  onSelectProduct,
  onStartChat,
}: {
  mode: CommerceWorkspaceMode;
  conversation: Conversation | null;
  tab: CommerceContextTab;
  running: boolean;
  expanded: boolean;
  onTabChange: (tab: CommerceContextTab) => void;
  onClose: () => void;
  onToggleExpanded: () => void;
  products: CatalogProduct[];
  selectedProduct: CatalogProduct | null;
  onSelectProduct: (product: CatalogProduct) => void;
  onStartChat: () => void;
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
          {tab === "run" ? "Agent run" : tab === "decisions" ? "Decisions" : tab === "inbox" ? "Inbox" : tab === "catalog" ? "Catalogue" : tab === "product" ? "Product details" : tab === "work" ? (mode === "sira" ? "Decision details" : "Product details") : "Connectors"}
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
        <button aria-selected={tab === (mode === "sira" ? "decisions" : "catalog")} onClick={() => onTabChange(mode === "sira" ? "decisions" : "catalog")} role="tab" type="button">{mode === "sira" ? "Decisions" : "Products"}</button>
        <button aria-selected={tab === "connectors"} onClick={() => onTabChange("connectors")} role="tab" type="button">Connectors</button>
      </div>

      <div className={styles.contextScroller}>
        {tab === "run" ? <RunPanel mode={mode} running={running} conversation={conversation} /> : null}
        {tab === "work" && mode === "sira" ? <SiraWorkPanel /> : null}
        {tab === "work" && mode === "seil" ? <SeilWorkPanel /> : null}
        {tab === "decisions" ? <DecisionsPanel onStart={onStartChat} /> : null}
        {tab === "inbox" ? <InboxPanel mode={mode} /> : null}
        {tab === "catalog" ? <CatalogPanel products={products} onSelect={onSelectProduct} /> : null}
        {tab === "product" ? <ProductPanel product={selectedProduct} onBack={() => onTabChange("catalog")} /> : null}
        {tab === "connectors" ? <ConnectorsPanel mode={mode} /> : null}
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
  const [confirmingProposal, setConfirmingProposal] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [catalogProducts, setCatalogProducts] = useState<CatalogProduct[]>(() => WEB_DATA_MODE === "fixture" ? FIXTURE_CATALOG : []);
  const [selectedProduct, setSelectedProduct] = useState<CatalogProduct | null>(null);
  const conversationsQuery = useQuery({
    queryKey: ["workspace-conversations", mode],
    enabled: WEB_DATA_MODE === "api",
    queryFn: () => getBrowserApiClient().request("workspace_conversations", {
      headers: mode === "seil" ? sellerEditorDevelopmentHeaders : buyerDevelopmentHeaders,
      query: { mode },
    }),
  });
  const compact = useIsCompact();
  const messageRootRef = useRef<HTMLDivElement>(null);
  const messageViewportRef = useRef<HTMLDivElement>(null);
  const messageBottomRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const responseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const responseAbortRef = useRef<AbortController | null>(null);

  const modeConversations = conversations[mode];
  const selectedConversation =
    modeConversations.find((conversation) => conversation.id === selectedByMode[mode]) ??
    modeConversations[0];
  const messages = selectedConversation?.messages ?? [];
  const messageVersion = `${mode}:${selectedConversation?.id ?? "new"}:${messages.map((message) => `${message.id}:${message.content.length}`).join("|")}`;

  usePretextMessages(messageRootRef, messageVersion);

  useEffect(() => {
    if (WEB_DATA_MODE !== "api" || !conversationsQuery.data) return;
    const restored: Conversation[] = conversationsQuery.data.map((conversation) => ({
      id: conversation.id,
      mode: conversation.mode,
      title: conversation.title,
      updatedLabel: "Saved",
      messages: conversation.messages.map((message) => ({
        id: `${message.role}-${crypto.randomUUID()}`,
        role: message.role,
        content: message.content,
        toolCalls: message.tool_calls,
        proposals: message.proposals,
      })),
    }));
    const next = restored.length ? restored : [{
      id: `${mode}-new-${crypto.randomUUID()}`,
      mode,
      title: "New chat",
      updatedLabel: "Now",
      messages: [],
    }];
    setConversations((current) => ({ ...current, [mode]: next }));
    setSelectedByMode((current) => ({
      ...current,
      [mode]: next.some((item) => item.id === current[mode]) ? current[mode] : next[0].id,
    }));
  }, [conversationsQuery.data, mode]);

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
    responseAbortRef.current?.abort();
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

  async function submitMessage(value = composer.trim()) {
    if (!value || running || !selectedConversation) return;
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

    if (WEB_DATA_MODE === "fixture") {
      responseTimerRef.current = setTimeout(() => {
        const response = responseFor(targetMode, value);
        const products = fixtureProductsForPrompt(targetMode, value);
        if (products.length) setCatalogProducts(products);
        updateConversation(targetMode, conversationId, (conversation) => ({
          ...conversation,
          messages: conversation.messages.map((message) => message.id === assistantId ? { ...message, content: response, meta: "Preview updated", products } : message),
        }));
        if (targetMode === mode) setRunning(false);
        responseTimerRef.current = null;
      }, 850);
      return;
    }

    const controller = new AbortController();
    responseAbortRef.current = controller;
    try {
      const history = selectedConversation.messages.slice(-12).map(({ role, content }) => ({ role, content }));
      const payload = await getBrowserApiClient().request("workspace_chat", {
        headers: {
          ...(targetMode === "seil"
            ? sellerEditorDevelopmentHeaders
            : buyerDevelopmentHeaders),
        },
        body: {
          conversation_id: conversationId.startsWith("wc_") ? conversationId : undefined,
          mode: targetMode,
          message: value,
          history,
        },
        signal: controller.signal,
      });
      const panel = payload.panel as CommerceContextTab;
      const products = payload.products ?? [];
      if (products.length) setCatalogProducts(products);
      updateConversation(targetMode, conversationId, (conversation) => ({
        ...conversation,
        id: payload.conversation_id,
        messages: conversation.messages.map((message) => message.id === assistantId ? { ...message, content: payload.message ?? "I need a little more context.", meta: "Context updated", products, toolCalls: payload.tool_calls ?? [], proposals: payload.proposals ?? [] } : message),
      }));
      setSelectedByMode((current) => ({ ...current, [targetMode]: payload.conversation_id }));
      if (panel) openContext(panel);
    } catch (error) {
      if (!controller.signal.aborted) {
        updateConversation(targetMode, conversationId, (conversation) => ({
          ...conversation,
          messages: conversation.messages.map((message) => message.id === assistantId ? { ...message, content: error instanceof Error ? error.message : "SIRA is temporarily unavailable.", meta: "Could not complete" } : message),
        }));
      }
    } finally {
      if (responseAbortRef.current === controller) responseAbortRef.current = null;
      if (targetMode === mode) setRunning(false);
    }
  }

  async function confirmProposal(messageId: string, proposal: AgentProposalView) {
    if (proposal.proposal_type !== "PURCHASE_REQUEST" || confirmingProposal) return;
    const intent = proposal.payload.intent;
    if (typeof intent !== "string" || intent.trim().length < 10) return;
    const visibility = proposal.payload.visibility === "PRIVATE" ? "PRIVATE" : "SELECTIVE";
    setConfirmingProposal(proposal.proposal_hash);
    try {
      const created = await getBrowserApiClient().request("create_decision_request", {
        headers: buyerDevelopmentHeaders,
        idempotencyKey: `agent-proposal-${proposal.proposal_hash.replace("sha256:", "")}`,
        body: { intent: intent.trim(), visibility },
      });
      await getBrowserApiClient().request("discover_decision_request", {
        headers: buyerDevelopmentHeaders,
        pathParams: { request_id: created.id },
        idempotencyKey: `discover-${created.id}`,
      });
      if (selectedConversation) {
        updateConversation("sira", selectedConversation.id, (conversation) => ({
          ...conversation,
          messages: conversation.messages.map((message) => message.id === messageId ? {
            ...message,
            meta: "Decision created",
            proposals: message.proposals?.filter((item) => item.proposal_hash !== proposal.proposal_hash),
          } : message),
        }));
      }
      setContextTab("decisions");
      setContextOpen(true);
    } catch (error) {
      if (selectedConversation) {
        updateConversation("sira", selectedConversation.id, (conversation) => ({
          ...conversation,
          messages: conversation.messages.map((message) => message.id === messageId ? {
            ...message,
            meta: error instanceof Error ? error.message : "Could not create decision",
          } : message),
        }));
      }
    } finally {
      setConfirmingProposal(null);
    }
  }

  function stopResponse() {
    responseAbortRef.current?.abort();
    responseAbortRef.current = null;
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
    openContext("connectors");
    setComposer(`I want to add ${file.name} as company context. Which connector should I use?`);
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
          onOpenSettings={() => setSettingsOpen(true)}
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
                  {message.meta && message.content ? <p className={styles.messageMeta}><Sparkles aria-hidden="true" /> {message.meta}</p> : null}
                  {message.content ? <ChatMessageBody content={message.content} /> : (
                    <AgentWorkingState mode={mode} />
                  )}
                  {message.products?.length ? (
                    <div className={styles.messageProductShelf} aria-label="Matching products">
                      {message.products.map((product) => <ProductCard key={product.id} product={product} compact onSelect={(selected) => { setSelectedProduct(selected); openContext("product"); }} />)}
                    </div>
                  ) : null}
                  {message.proposals?.map((proposal) => (
                    <section className={styles.proposalCard} key={proposal.proposal_hash}>
                      <div>
                        <span>Requires your confirmation</span>
                        <strong>{proposal.proposal_type === "PURCHASE_REQUEST" ? "Create this buying decision" : proposal.proposal_type.replaceAll("_", " ")}</strong>
                        {typeof proposal.payload.intent === "string" ? <p>{proposal.payload.intent}</p> : null}
                      </div>
                      <button
                        type="button"
                        disabled={proposal.proposal_type !== "PURCHASE_REQUEST" || confirmingProposal !== null}
                        onClick={() => void confirmProposal(message.id, proposal)}
                      >
                        {confirmingProposal === proposal.proposal_hash ? "Creating…" : "Confirm and create"}
                        <ArrowRight aria-hidden="true" />
                      </button>
                    </section>
                  ))}
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
              onChange={(event) => setComposer(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  if (running) stopResponse();
                  else submitMessage();
                }
              }}
              placeholder="Write a message..."
              rows={1}
              value={composer}
            />
            <div className={styles.composerToolbar}>
              <div>
                {WEB_DATA_MODE === "fixture" ? (
                  <>
                    <input className={styles.hiddenFileInput} ref={fileInputRef} type="file" onChange={handleFile} />
                    <button type="button" onClick={() => fileInputRef.current?.click()} aria-label="Preview company context attachment" title="Preview company context attachment">
                      <Paperclip aria-hidden="true" />
                    </button>
                  </>
                ) : null}
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
                  disabled={!running && !composer.trim()}
                  aria-label={running ? "Pause agent" : "Send message"}
                >
                  {running ? <X aria-hidden="true" /> : <SendHorizontal aria-hidden="true" />}
                </button>
              </div>
            </div>
          </div>
          <p className={styles.composerBoundary}>
            <LockKeyhole aria-hidden="true" />
            {MODE_COPY[mode].privacy}. Agent suggestions are advisory; approvals and purchases use server-owned workflows.
          </p>
        </div>
      </section>

      {contextOpen ? (
        <ContextPanel
          mode={mode}
          conversation={selectedConversation}
          tab={contextTab}
          running={running}
          expanded={contextExpanded}
          onTabChange={setContextTab}
          onClose={() => { setContextOpen(false); setContextExpanded(false); }}
          onToggleExpanded={() => setContextExpanded((current) => !current)}
          products={catalogProducts}
          selectedProduct={selectedProduct}
          onSelectProduct={(product) => { setSelectedProduct(product); setContextTab("product"); }}
          onStartChat={() => { setContextOpen(false); setComposer("What do you want to buy today? "); }}
        />
      ) : null}

      {settingsOpen ? <ProfileSettingsModal workspace={mode} onClose={() => setSettingsOpen(false)} /> : null}

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
