"use client";

import {
  ArrowRight,
  BadgeCheck,
  Check,
  ChevronDown,
  CircleAlert,
  Clock3,
  Expand,
  FileCheck2,
  FileSearch,
  FolderKanban,
  Grid2X2,
  Inbox,
  Info,
  Layers3,
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
import Image from "next/image";
import { useEffect, useRef, useState, type ChangeEvent, type RefObject } from "react";
import { prepareWithSegments, walkLineRanges } from "@chenglou/pretext";
import { useQuery } from "@tanstack/react-query";
import type {
  AgentProposalView,
  AttentionView,
  CatalogProductView,
  MissionArtifactView,
  MissionEventView,
  MissionSummaryView,
} from "@sira/api-client";

import {
  buyerDevelopmentHeaders,
  getBrowserApiClient,
  sellerEditorDevelopmentHeaders,
  WEB_DATA_MODE,
} from "@/lib/api";
import { ProfileSettingsModal } from "@/components/home/profile-preview";
import { useFirebaseAuth } from "@/components/auth/firebase-auth-provider";
import { DecisionWorkspacePanel } from "@/components/decisions/decision-surfaces";

import { ChatMessageBody } from "./chat-message";
import styles from "./commerce-workspace.module.css";

export type CommerceWorkspaceMode = "sira" | "seil";
export type CommerceContextTab =
  | "work"
  | "connectors"
  | "decisions"
  | "inbox"
  | "catalog"
  | "product"
  | "artifact"
  | "run";

type ActiveDecision = {
  requestId: string;
  version: number;
  stage: string;
};

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
  website?: string;
  source_refs?: { [key: string]: unknown }[];
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  meta?: string;
  products?: CatalogProduct[];
  toolCalls?: string[];
  proposals?: AgentProposalView[];
  mission?: MissionSummaryView;
  events?: MissionEventView[];
  artifacts?: MissionArtifactView[];
  attention?: AttentionView;
  openTasks?: { [key: string]: unknown }[];
  handoffs?: { [key: string]: unknown }[];
  retryText?: string;
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
    summary:
      "Source-linked meeting intelligence for client-facing teams with low administration overhead.",
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
    why_company:
      "Fits a ten-consultant team, keeps client conversations private, and works with the tools already in use.",
    admin_effort: "Low",
    evidence_freshness: "Reviewed 2 days ago",
    requirement_coverage: "4 of 4 key needs",
    limitation: "Advanced governance controls require the Enterprise edition.",
    logo: "/products/northstar-notes.svg",
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
    summary:
      "Structured meeting capture and controls for growing teams with a dedicated workspace administrator.",
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
    why_company:
      "Covers the current stack and privacy needs, but needs a named workspace administrator.",
    admin_effort: "Medium",
    evidence_freshness: "Reviewed 6 days ago",
    requirement_coverage: "4 of 4 key needs",
    limitation: "Ongoing administration is heavier than the preferred operating model.",
    logo: "/products/relayiq.svg",
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
    summary:
      "Fast meeting capture for internal teams that do not need shared external-client workspaces.",
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
    why_company:
      "Low-cost option for internal meetings, but it cannot support the required shared client workspaces.",
    admin_effort: "Low",
    evidence_freshness: "Reviewed 12 days ago",
    requirement_coverage: "3 of 4 key needs",
    limitation: "Restricted shared client workspaces are not supported.",
    logo: "/products/briefly-cloud.svg",
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
    summary:
      "A lightweight and affordable way for small teams to capture searchable meeting notes.",
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
    why_company:
      "Affordable and easy to deploy, but its model-improvement policy conflicts with the client-data requirement.",
    admin_effort: "Low",
    evidence_freshness: "Reviewed 8 days ago",
    requirement_coverage: "2 of 4 key needs",
    limitation: "Customer content may be used for general model improvement.",
    logo: "/products/minute-flow.svg",
    logo_tone: "gold",
    seats: "Up to 25 seats",
  },
];

const REAL_PRODUCT_BRANDS: Record<string, Partial<CatalogProduct>> = {
  product_fixture_d: {
    name: "Fathom",
    seller: "Fathom",
    edition: "Team",
    price: "USD 19",
    billing_unit: "seat_month",
    status: "Vendor evidence",
    summary: "Meeting recording, AI notes, action items, and team CRM sync.",
    claims: [
      "Team plans include shared recordings and AI summaries.",
      "CRM sync supports HubSpot, Salesforce, and Close.",
      "A 14-day Team trial is publicly offered.",
    ],
    integrations: ["hubspot", "salesforce", "close", "zoom", "google_meet", "teams"],
    category: "Meeting intelligence",
    deployment: "Trial available",
    fit: "Strong candidate",
    why_company: "Within budget for ten seats, with native HubSpot sync and a runnable team trial.",
    admin_effort: "Low",
    evidence_freshness: "Official pricing checked 5 Aug 2026",
    requirement_coverage: "Notes, actions, HubSpot",
    limitation: "Security and retention controls vary by plan and need trial verification.",
    logo: "/products/fathom.svg",
    website: "https://fathom.video/pricing",
  },
  product_fixture_c: {
    name: "Fireflies.ai",
    seller: "Fireflies.ai",
    edition: "Business",
    price: "USD 29",
    billing_unit: "seat_month_annual",
    status: "Vendor evidence",
    summary: "AI meeting notes, action items, search, coaching, and CRM synchronization.",
    claims: [
      "Business includes HubSpot and Salesforce CRM sync.",
      "Business includes AI coaching and team interaction metrics.",
      "Advanced AI notes and action items are supported.",
    ],
    integrations: ["hubspot", "salesforce", "slack", "zapier"],
    category: "Conversation intelligence",
    deployment: "Trial evaluation",
    fit: "Strong alternative",
    why_company: "Meets the budget and HubSpot requirement, with deeper coaching than the brief requires.",
    admin_effort: "Medium",
    evidence_freshness: "Official product material checked 5 Aug 2026",
    requirement_coverage: "Notes, actions, HubSpot",
    limitation: "HubSpot sync requires the Business tier.",
    logo: "/products/fireflies.svg",
    website: "https://fireflies.ai/pricing",
  },
  product_fixture_b: {
    name: "Otter.ai",
    seller: "Otter.ai",
    edition: "Enterprise",
    price: "Quote required",
    billing_unit: "workspace",
    status: "Vendor evidence",
    summary: "Live transcription, meeting summaries, action items, and enterprise CRM autofill.",
    claims: [
      "HubSpot can be installed for an Enterprise workspace.",
      "Admins can map insights to HubSpot custom fields.",
      "CRM Autofill can sync meeting conversations into HubSpot.",
    ],
    integrations: ["hubspot", "zoom", "google_meet", "teams"],
    category: "Meeting assistant",
    deployment: "Sales-assisted",
    fit: "Needs price evidence",
    why_company: "The HubSpot workflow fits, but a live quote is required before it can pass budget.",
    admin_effort: "Medium",
    evidence_freshness: "Official help center checked 5 Aug 2026",
    requirement_coverage: "Notes, actions, HubSpot",
    limitation: "Current public pricing is insufficient for a budget decision.",
    logo: "/products/otter.svg",
    website: "https://otter.ai/pricing",
  },
  product_fixture_a: {
    name: "tl;dv",
    seller: "tl;dv",
    edition: "Business",
    price: "Verify current price",
    billing_unit: "seat_month",
    status: "Research evidence",
    summary: "Multilingual meeting recording, AI notes, and sales workflow integrations.",
    claims: [
      "Supports Zoom, Google Meet, and Microsoft Teams.",
      "Offers CRM-oriented workflows and HubSpot integration.",
      "Current plan eligibility requires live revalidation.",
    ],
    integrations: ["hubspot", "zoom", "google_meet", "teams"],
    category: "Meeting intelligence",
    deployment: "Self-serve evaluation",
    fit: "Evidence incomplete",
    why_company: "Functionally relevant, but current price and exact HubSpot plan eligibility need verification.",
    admin_effort: "Low",
    evidence_freshness: "Requires live price revalidation",
    requirement_coverage: "Notes, actions, HubSpot",
    limitation: "Do not rank as purchase-ready until pricing is revalidated.",
    logo: "/products/tldv.svg",
    website: "https://tldv.io/pricing/",
  },
};

const PRODUCT_LOGOS: Record<string, string> = Object.fromEntries(
  Object.entries(REAL_PRODUCT_BRANDS).flatMap(([id, product]) =>
    product.logo ? [[id, product.logo]] : [],
  ),
);

function withProductBrand(product: CatalogProduct | CatalogProductView): CatalogProduct {
  const brand = REAL_PRODUCT_BRANDS[product.id];
  return {
    ...product,
    ...(brand ?? {}),
    logo: brand?.logo ?? product.logo ?? PRODUCT_LOGOS[product.id],
    website: brand?.website ?? product.website ?? undefined,
    evidence_freshness:
      brand?.evidence_freshness ?? product.evidence_freshness ?? undefined,
    source_refs: brand?.source_refs ?? product.source_refs ?? undefined,
  };
}

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
          products: FIXTURE_CATALOG.map(withProductBrand),
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
          content: "Help me get Northstar Meeting Notes ready for review. What is still missing?",
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
    {
      name: "Business Context",
      purpose: "Company rules, goals, and buying preferences",
      status: "Needs setup",
      meta: "Add company documents or confirm details in chat",
    },
    {
      name: "Senso",
      purpose: "Company files and decision evidence",
      status: "Needs setup",
      meta: "Server connection required",
    },
    {
      name: "DataHub",
      purpose: "Structured company and product context",
      status: "Not connected",
      meta: "Optional",
    },
    {
      name: "Google Workspace",
      purpose: "Inventory and team context",
      status: "Not connected",
      meta: "Optional read-only connection",
    },
  ],
  seil: [
    {
      name: "Senso",
      purpose: "Seller sources and evidence sync",
      status: "Healthy",
      meta: "4 sources ready",
    },
    {
      name: "Help center",
      purpose: "Published documentation crawl",
      status: "Healthy",
      meta: "Checked today",
    },
    {
      name: "Merchant",
      purpose: "Quote, checkout, and fulfillment",
      status: "Needs setup",
      meta: "Certification pending",
    },
    {
      name: "Slack",
      purpose: "Review and publication alerts",
      status: "Not connected",
      meta: "Optional",
    },
  ],
};

function cloneSeedConversations() {
  if (WEB_DATA_MODE !== "fixture") {
    return {
      sira: [
        {
          id: "sira-structured",
          mode: "sira" as const,
          title: "SIRA workspace",
          updatedLabel: "Structured",
          messages: [],
        },
      ],
      seil: [
        {
          id: "seil-structured",
          mode: "seil" as const,
          title: "SEIL workspace",
          updatedLabel: "Structured",
          messages: [],
        },
      ],
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
  return words.length > 46 ? `${words.slice(0, 43).trim()}...` : words || "New mission";
}

function responseFor(mode: CommerceWorkspaceMode, prompt: string) {
  const normalized = prompt.toLowerCase();

  if (mode === "sira") {
    if (
      normalized.includes("connector") ||
      normalized.includes("senso") ||
      normalized.includes("prava")
    ) {
      return "## Connector status is open\n\nI moved the work panel to **Connectors**. Senso is healthy, while Prava still needs production setup before a live charged purchase can run.\n\nNo purchase or company record was changed.";
    }
    if (
      normalized.includes("product") ||
      normalized.includes("catalog") ||
      normalized.includes("option") ||
      normalized.includes("compare")
    ) {
      return "## I found four published products\n\nThese products have comparable pricing and published evidence for this need. Open a card to review company fit, deployment, integrations, and supported claims.\n\nThis is a **catalogue preview** only; choosing a product remains separate from approval and purchase.";
    }
    return "## I added this to the decision workspace\n\nI will use it to refine the need, company fit, and evaluated actions. The structured decision on the right remains the record that governs selection and execution.";
  }

  if (normalized.includes("connector") || normalized.includes("source")) {
    return "## Source connections are open\n\nI moved the work panel to **Connectors**. The evidence sources are healthy; merchant fulfillment still needs setup before an offer can execute.";
  }
  if (
    normalized.includes("product") ||
    normalized.includes("evidence") ||
    normalized.includes("claim")
  ) {
    return "## I opened Product Evidence\n\nThe right panel shows the current product, publication state, and the exact evidence gap. Private seller material stays in this workspace and is not sent to buyers.";
  }
  return "## I added this to the seller workspace\n\nI will use it to improve the product record, evidence, fit rules, and buyer-ready answers. Only reviewed fields can become published Product Evidence.";
}

function fixtureProductsForPrompt(mode: CommerceWorkspaceMode, prompt: string) {
  if (mode !== "sira") return [];
  const normalized = prompt.toLowerCase();
  return ["product", "catalog", "software", "option", "compare", "alternative"].some((term) =>
    normalized.includes(term),
  )
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

function usePretextMessages(rootRef: RefObject<HTMLElement | null>, version: string) {
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    let cancelled = false;
    let resizeObserver: ResizeObserver | undefined;

    const start = async () => {
      await document.fonts.ready;
      if (cancelled) return;

      const elements = Array.from(root.querySelectorAll<HTMLElement>("[data-pretext-message]"));

      const relayout = () => {
        for (const element of elements) {
          const width = element.getBoundingClientRect().width;
          if (width <= 0) continue;
          const computed = getComputedStyle(element);
          const lineHeight = Number.parseFloat(computed.lineHeight) || 28;
          const prepared = prepareWithSegments(element.textContent ?? "", computed.font);
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
  onCloseContext,
  onOpenContext,
  onOpenSettings,
  account,
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
  onCloseContext: () => void;
  onOpenContext: (tab: CommerceContextTab) => void;
  onOpenSettings: () => void;
  account: { initials: string; name: string; detail: string };
}) {
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const visibleConversations = conversations.filter((conversation) =>
    conversation.title.toLowerCase().includes(searchQuery.trim().toLowerCase()),
  );
  return (
    <aside className={styles.sidebar} aria-label={`${MODE_COPY[mode].name} navigation`}>
      <div className={styles.sidebarHeader}>
        <div className={styles.brandRow}>
          <button className={styles.brand} type="button" onClick={onCloseContext}>
            <span>
              <strong>{MODE_COPY[mode].name}</strong>
              <small>{MODE_COPY[mode].accentLabel}</small>
            </span>
          </button>
          <div className={styles.sidebarHeaderActions}>
            <button
              type="button"
              aria-label="Search chats"
              title="Search chats"
              aria-expanded={searchOpen}
              onClick={() => setSearchOpen((current) => !current)}
            >
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
            <input
              autoFocus
              type="search"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search chats"
            />
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
          New mission
        </button>
      </div>

      <nav className={styles.sidebarNav} aria-label="Workspace">
        <button type="button" onClick={onCloseContext}>
          <FolderKanban aria-hidden="true" /> Missions
        </button>
        <button
          className={
            contextTab === (mode === "sira" ? "decisions" : "catalog")
              ? styles.activeNav
              : undefined
          }
          type="button"
          onClick={() => onOpenContext(mode === "sira" ? "decisions" : "catalog")}
        >
          {mode === "sira" ? <Layers3 aria-hidden="true" /> : <Package aria-hidden="true" />}
          {mode === "sira" ? "Decisions" : "Products"}
        </button>
        <button
          className={contextTab === "connectors" ? styles.activeNav : undefined}
          type="button"
          onClick={() => onOpenContext("connectors")}
          aria-pressed={contextTab === "connectors"}
        >
          <Plug aria-hidden="true" /> Connectors
        </button>
        <button
          className={contextTab === "inbox" ? styles.activeNav : undefined}
          type="button"
          onClick={() => onOpenContext("inbox")}
        >
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
        {!visibleConversations.length ? (
          <p className={styles.emptyRecents}>No chats match that search.</p>
        ) : null}
      </div>

      <div className={styles.sidebarFooter}>
        <button
          type="button"
          onClick={onOpenSettings}
          aria-label={`Open ${MODE_COPY[mode].name} profile settings`}
        >
          <span className={styles.avatar}>{account.initials}</span>
          <span>
            <strong>{account.name}</strong>
            <small>{account.detail}</small>
          </span>
          <Settings2 aria-hidden="true" />
        </button>
      </div>
    </aside>
  );
}

function AgentWorkingState({ mode }: { mode: CommerceWorkspaceMode }) {
  const stages =
    mode === "sira"
      ? [
          "Understanding your request",
          "Checking buyer context and product tools",
          "Preparing a recommendation",
        ]
      : [
          "Understanding your product task",
          "Checking seller evidence and pack tools",
          "Preparing the next step",
        ];
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
      <span>Thinking…</span>
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
          <p>
            A real decision will appear here after SIRA has enough context and the backend creates a
            decision record.
          </p>
        </section>
        <section className={styles.contextSection}>
          <div className={styles.sectionHeading}>
            <div>
              <span>Current state</span>
              <h3>Continue in chat</h3>
            </div>
            <MessageSquare aria-hidden="true" />
          </div>
          <p className={styles.sectionCopy}>
            Describe the outcome, users, deadline, constraints, budget, and approval path. This
            panel will not invent missing decision data.
          </p>
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
          <span>
            <Clock3 aria-hidden="true" /> Due 19 Aug
          </span>
          <span>
            <ShieldCheck aria-hidden="true" /> Selective
          </span>
        </div>
      </section>

      <section className={styles.pathSection} aria-label="Decision path">
        {["Need", "Company fit", "Options", "Action", "Result"].map((stage, index) => (
          <div
            data-state={index < 2 ? "complete" : index === 2 ? "current" : "waiting"}
            key={stage}
          >
            <span>{index < 2 ? <Check aria-hidden="true" /> : index + 1}</span>
            <small>{stage}</small>
          </div>
        ))}
      </section>

      <section className={styles.contextSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span>Options</span>
            <h3>Current comparison</h3>
          </div>
          <Grid2X2 aria-hidden="true" />
        </div>
        <div className={styles.optionList}>
          <article data-tone="supported">
            <div>
              <strong>Replace with Northstar Meeting Notes</strong>
              <span>Recommended</span>
            </div>
            <p>Supported for the company context, with low stack risk.</p>
            <dl>
              <div>
                <dt>Cost</dt>
                <dd>$89 / month</dd>
              </div>
              <div>
                <dt>Action</dt>
                <dd>Replace</dd>
              </div>
            </dl>
          </article>
          <article>
            <div>
              <strong>CurrentCall Workspace</strong>
              <span>Runner-up</span>
            </div>
            <p>Supported, but needs more administration effort.</p>
            <dl>
              <div>
                <dt>Cost</dt>
                <dd>$62 / month</dd>
              </div>
              <div>
                <dt>Action</dt>
                <dd>Buy</dd>
              </div>
            </dl>
          </article>
          <article data-tone="blocked">
            <div>
              <strong>Briefly Capture</strong>
              <span>Blocked</span>
            </div>
            <p>Fails a private company requirement. The seller did not block it.</p>
            <dl>
              <div>
                <dt>Cost</dt>
                <dd>$49 / month</dd>
              </div>
              <div>
                <dt>Action</dt>
                <dd>Do not select</dd>
              </div>
            </dl>
          </article>
        </div>
      </section>
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
          <p>
            Select a seller product returned by SEIL before Product Evidence and pack health appear
            here.
          </p>
        </section>
        <section className={styles.contextSection}>
          <div className={styles.sectionHeading}>
            <div>
              <span>Current state</span>
              <h3>Continue in chat</h3>
            </div>
            <MessageSquare aria-hidden="true" />
          </div>
          <p className={styles.sectionCopy}>
            Ask SEIL to search your products or inspect an exact product ID. This panel will show
            only backend-supplied evidence.
          </p>
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
          <span>
            <FileCheck2 aria-hidden="true" /> Seller draft
          </span>
          <span>
            <BadgeCheck aria-hidden="true" /> Compiled by Seilnsara
          </span>
        </div>
      </section>

      <section className={styles.healthSection}>
        <div className={styles.healthScore}>
          <strong>75%</strong>
          <span>Pack health</span>
        </div>
        <dl>
          <div>
            <dt>Complete</dt>
            <dd>9</dd>
          </div>
          <div>
            <dt>Required</dt>
            <dd>12</dd>
          </div>
          <div>
            <dt>Stale</dt>
            <dd>1</dd>
          </div>
          <div>
            <dt>Conflict</dt>
            <dd>1</dd>
          </div>
        </dl>
      </section>

      <section className={styles.contextSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span>Needs attention</span>
            <h3>Evidence and review</h3>
          </div>
          <FileSearch aria-hidden="true" />
        </div>
        <div className={styles.evidenceList}>
          <article data-tone="warning">
            <CircleAlert aria-hidden="true" />
            <div>
              <strong>Data retention</strong>
              <p>Confirm the 30-day value with current supporting evidence.</p>
            </div>
          </article>
          <article>
            <Check aria-hidden="true" />
            <div>
              <strong>Customer data training</strong>
              <p>Claim and source are current.</p>
            </div>
          </article>
          <article>
            <Check aria-hidden="true" />
            <div>
              <strong>Supported regions</strong>
              <p>United States and Canada confirmed.</p>
            </div>
          </article>
        </div>
      </section>

      <section className={styles.contextSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span>Publication</span>
            <h3>Next authorized step</h3>
          </div>
          <FolderKanban aria-hidden="true" />
        </div>
        <p className={styles.sectionCopy}>
          Resolve the validation gap before freezing revision 3 for independent review.
        </p>
      </section>
    </div>
  );
}

function ConnectorsPanel({ mode }: { mode: CommerceWorkspaceMode }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ["workspace-connectors", mode],
    enabled: WEB_DATA_MODE === "api",
    queryFn: () =>
      getBrowserApiClient().request("workspace_connectors", {
        headers: mode === "seil" ? sellerEditorDevelopmentHeaders : buyerDevelopmentHeaders,
      }),
  });
  const capabilityQuery = useQuery({
    queryKey: ["workspace-capabilities", mode],
    enabled: WEB_DATA_MODE === "api",
    queryFn: () =>
      getBrowserApiClient().request("workspace_capabilities", {
        headers: mode === "seil" ? sellerEditorDevelopmentHeaders : buyerDevelopmentHeaders,
      }),
  });
  const connectors: Connector[] =
    WEB_DATA_MODE === "fixture" ? CONNECTORS[mode] : (query.data ?? []);
  return (
    <div className={styles.contextBody}>
      <section className={styles.documentHeader}>
        <span>{MODE_COPY[mode].name} workspace</span>
        <h2>Connectors</h2>
        <p>Sources and execution services available to this agent workspace.</p>
      </section>

      <section className={styles.connectorList}>
        {capabilityQuery.data?.map((capability) => (
          <article
            data-status={capability.status === "ready" ? "healthy" : "needs-setup"}
            key={capability.id}
          >
            <button type="button" onClick={() => setExpanded((current) => current === capability.id ? null : capability.id)}>
              <span className={styles.connectorIcon}><Sparkles aria-hidden="true" /></span>
              <span className={styles.connectorCopy}><strong>{capability.label}</strong><small>{capability.reason_code.replaceAll("_", " ")}</small></span>
              <span className={styles.connectorStatus}>{capability.status}</span>
              <ChevronDown className={expanded === capability.id ? styles.rotated : undefined} aria-hidden="true" />
            </button>
            {expanded === capability.id && capability.remediation ? (
              <div className={styles.connectorDetail}><span>{capability.remediation}</span></div>
            ) : null}
          </article>
        ))}
        {connectors.map((connector) => (
          <article
            data-status={connector.status.toLowerCase().replace(" ", "-")}
            key={connector.name}
          >
            <button
              type="button"
              onClick={() =>
                setExpanded((current) => (current === connector.name ? null : connector.name))
              }
            >
              <span className={styles.connectorIcon}>
                <Plug aria-hidden="true" />
              </span>
              <span className={styles.connectorCopy}>
                <strong>{connector.name}</strong>
                <small>{connector.purpose}</small>
              </span>
              <span className={styles.connectorStatus}>{connector.status}</span>
              <ChevronDown
                className={expanded === connector.name ? styles.rotated : undefined}
                aria-hidden="true"
              />
            </button>
            {expanded === connector.name ? (
              <div className={styles.connectorDetail}>
                <span>{connector.meta}</span>
                <p>
                  Connector credentials are never displayed in the browser. Setup and recovery use
                  the server-authorized flow.
                </p>
              </div>
            ) : null}
          </article>
        ))}
        {query.isPending ? (
          <p className={styles.sectionCopy}>Loading connector status…</p>
        ) : null}
        {query.isError ? (
          <p className={styles.sectionCopy}>Connector status is temporarily unavailable.</p>
        ) : null}
      </section>

      <div className={styles.contextNote}>
        <ShieldCheck aria-hidden="true" />
        <p>
          A missing connector lowers confidence or blocks only the actions that require it. Manual
          work remains available when policy permits.
        </p>
      </div>
    </div>
  );
}

function DecisionsPanel({ onStart, onSelect }: { onStart: () => void; onSelect: (decision: ActiveDecision) => void }) {
  const query = useQuery({
    queryKey: ["decision-index"],
    enabled: WEB_DATA_MODE === "api",
    queryFn: () =>
      getBrowserApiClient().request("list_decision_requests", { headers: buyerDevelopmentHeaders }),
  });
  const decisions =
    WEB_DATA_MODE === "api" ? [...(query.data?.active ?? []), ...(query.data?.history ?? [])] : [];
  return (
    <div className={styles.contextBody}>
      <section className={styles.documentHeader}>
        <span>SIRA workspace</span>
        <h2>Decisions</h2>
        <p>
          Buying work starts in chat. SIRA keeps asking for material context and turns it into
          structured decision state.
        </p>
      </section>
      {decisions.length ? (
        <section className={styles.contextSection}>
          <div className={styles.sectionHeading}>
            <div>
              <span>Backend records</span>
              <h3>
                {decisions.length} decision{decisions.length === 1 ? "" : "s"}
              </h3>
            </div>
            <Layers3 aria-hidden="true" />
          </div>
          <div className={styles.decisionMiniList}>
            {decisions.map((decision) => (
              <article key={decision.id}>
                <span>{decision.current_stage.replaceAll("_", " ")}</span>
                <strong>{decision.intent}</strong>
              </article>
            ))}
          </div>
        </section>
      ) : (
        <section className={styles.contextSection}>
          <div className={styles.sectionHeading}>
            <div>
              <span>Current</span>
              <h3>{query.isPending ? "Loading decisions" : "No decisions yet"}</h3>
            </div>
            <MessageSquare aria-hidden="true" />
          </div>
          <p className={styles.sectionCopy}>
            {query.isError
              ? "Decision records are temporarily unavailable."
              : "Describe what you need, who will use it, and when. SIRA will create a decision only after confirmation."}
          </p>
          {!query.isPending ? (
            <button className={styles.fullViewLink} type="button" onClick={onStart}>
              Start in chat <ArrowRight aria-hidden="true" />
            </button>
          ) : null}
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
        const result = await getBrowserApiClient().request("list_decision_requests", {
          headers: buyerDevelopmentHeaders,
        });
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
      <section className={styles.documentHeader}>
        <span>Assigned work</span>
        <h2>Inbox</h2>
        <p>Requests that need your review or approval appear here without leaving the workspace.</p>
      </section>
      <section className={styles.contextSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span>{items.length ? "Needs attention" : "Up to date"}</span>
            <h3>
              {query.isPending
                ? "Loading assigned work"
                : `${items.length} assigned item${items.length === 1 ? "" : "s"}`}
            </h3>
          </div>
          <Inbox aria-hidden="true" />
        </div>
        {items.length ? (
          <div className={styles.decisionMiniList}>
            {items.map((item) => (
              <article key={item.id}>
                <span>{item.label}</span>
                <strong>{item.title}</strong>
              </article>
            ))}
          </div>
        ) : (
          <p className={styles.sectionCopy}>
            {query.isError
              ? "Assigned work is temporarily unavailable."
              : "New work appears here only when a real workflow record requires attention."}
          </p>
        )}
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
      {product.logo?.startsWith("/") ? (
        <Image alt="" height={large ? 58 : 42} src={product.logo} width={large ? 58 : 42} />
      ) : (
        (product.logo ?? fallback)
      )}
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
      <button
        type="button"
        onClick={() => onSelect(product)}
        aria-label={`Open ${product.name} details`}
      >
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
          <span>
            {product.admin_effort ? `${product.admin_effort} admin effort` : "Admin effort unknown"}
          </span>
        </div>
        <footer>
          <div>
            <strong>{product.price}</strong>
            <span> / {product.billing_unit.replaceAll("_", " ")}</span>
          </div>
          <span className={styles.productCardAction}>
            View details <ArrowRight aria-hidden="true" />
          </span>
        </footer>
      </button>
    </article>
  );
}

function CatalogPanel({
  products,
  onSelect,
}: {
  products: CatalogProduct[];
  onSelect: (product: CatalogProduct) => void;
}) {
  return (
    <div className={styles.contextBody}>
      <section className={styles.documentHeader}>
        <span>Published Product Evidence</span>
        <h2>Product catalogue</h2>
        <p>
          Browse B2B software with comparable pricing, deployment, and fit details. Open a product
          to inspect its published facts.
        </p>
      </section>
      <section className={styles.catalogGrid}>
        {products.map((product) => (
          <ProductCard key={product.id} product={product} onSelect={onSelect} />
        ))}
        {!products.length ? (
          <p className={styles.sectionCopy}>
            Ask SIRA to show products. Catalogue results will appear in this pane and in the
            mission stream.
          </p>
        ) : null}
      </section>
    </div>
  );
}

function SellerProductsPanel({
  onSelect,
  researchArtifacts = [],
  onSelectArtifact,
}: {
  onSelect: (product: CatalogProduct) => void;
  researchArtifacts?: MissionArtifactView[];
  onSelectArtifact?: (artifact: MissionArtifactView) => void;
}) {
  const query = useQuery({
    queryKey: ["seil-products", WEB_DATA_MODE],
    enabled: WEB_DATA_MODE === "api",
    queryFn: () =>
      getBrowserApiClient().request("seller_evidence_search_products", {
        headers: sellerEditorDevelopmentHeaders,
        query: {},
      }),
  });
  const products: CatalogProduct[] = (query.data?.results ?? []).map((item) => ({
    id: item.id,
    name: item.name,
    seller: item.publisher_authority === "SELLER_SEALED" ? "Seller confirmed" : "Platform compiled",
    edition: item.state.replaceAll("_", " "),
    price: "Evidence packet",
    billing_unit: "current state",
    status: item.state.replaceAll("_", " "),
    summary: item.public_summary,
    claims: [],
    integrations: [],
    category: item.category,
  }));
  const drafts = researchArtifacts.filter((artifact) => artifact.kind === "seller_evidence");

  return (
    <div className={styles.contextBody}>
      <section className={styles.documentHeader}>
        <span>Seller workspace</span>
        <h2>Product Evidence</h2>
        <p>Claim, strengthen, review, and publish evidence packets without leaving the mission.</p>
      </section>
      <section className={styles.contextSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span>{products.length || drafts.length ? "Evidence workspace" : "Cold start"}</span>
            <h3>{query.isPending ? "Loading evidence" : `${products.length} registered · ${drafts.length} research draft${drafts.length === 1 ? "" : "s"}`}</h3>
          </div>
          <Package aria-hidden="true" />
        </div>
        {products.length ? (
          <div className={styles.decisionMiniList}>
            {products.map((product) => (
              <button key={product.id} type="button" onClick={() => onSelect(product)}>
                <span>{product.status}</span>
                <strong>{product.name}</strong>
                <small>{product.summary}</small>
              </button>
            ))}
          </div>
        ) : null}
        {drafts.length ? (
          <div className={styles.decisionMiniList}>
            {drafts.map((artifact) => (
              <button key={artifact.id} type="button" onClick={() => onSelectArtifact?.(artifact)}>
                <span>Private research draft</span>
                <strong>{artifact.title}</strong>
                <small>Source-linked evidence ready for seller review; not published.</small>
              </button>
            ))}
          </div>
        ) : null}
        {!products.length && !drafts.length ? (
          <p className={styles.sectionCopy}>
            {query.isError
              ? "Product Evidence is temporarily unavailable."
              : "Tell SEIL a product name or website. It will research public sources and prepare a cited draft."}
          </p>
        ) : null}
      </section>
    </div>
  );
}

function SellerProductPanel({ product, onBack }: { product: CatalogProduct | null; onBack: () => void }) {
  const query = useQuery({
    queryKey: ["seil-product", product?.id, WEB_DATA_MODE],
    enabled: WEB_DATA_MODE === "api" && Boolean(product?.id),
    queryFn: () =>
      getBrowserApiClient().request("seller_evidence_product_view", {
        headers: sellerEditorDevelopmentHeaders,
        pathParams: { product_id: product!.id },
      }),
  });
  if (!product) return <SellerProductsPanel onSelect={() => undefined} />;
  const view = query.data;
  const nextAction = view?.available_actions[0];
  return (
    <div className={styles.contextBody}>
      <button className={styles.fullViewLink} type="button" onClick={onBack}>Back to products</button>
      <section className={styles.documentHeader}>
        <span>{product.status}</span>
        <h2>{product.name}</h2>
        <p>{product.summary}</p>
      </section>
      <section className={styles.contextSection}>
        <div className={styles.sectionHeading}>
          <div><span>Packet health</span><h3>{view?.pack_health.status.replaceAll("_", " ") ?? (query.isPending ? "Loading" : "Unavailable")}</h3></div>
          <FileCheck2 aria-hidden="true" />
        </div>
        {view ? (
          <dl className={styles.artifactFields}>
            <div><dt>Claims</dt><dd>{view.pack_health.complete_claim_count} of {view.pack_health.required_claim_count}</dd></div>
            <div><dt>Stale</dt><dd>{view.pack_health.stale_claim_count}</dd></div>
            <div><dt>Conflicts</dt><dd>{view.pack_health.conflict_count}</dd></div>
            <div><dt>Next action</dt><dd>{nextAction?.label ?? "Continue in chat"}</dd></div>
          </dl>
        ) : null}
      </section>
    </div>
  );
}

function ProductPanel({ product, onBack }: { product: CatalogProduct | null; onBack: () => void }) {
  if (!product) return <CatalogPanel products={[]} onSelect={() => undefined} />;
  return (
    <div className={styles.contextBody}>
      <button className={styles.fullViewLink} type="button" onClick={onBack}>
        Back to catalogue
      </button>
      <section className={styles.productHero}>
        <div className={styles.productHeroBrand}>
          <ProductLogo product={product} large />
          <div>
            <span>{product.seller}</span>
            <small>{product.category ?? "Business software"}</small>
          </div>
          <span className={styles.productEvidenceBadge}>
            <BadgeCheck aria-hidden="true" /> {product.status}
          </span>
        </div>
        <h2>{product.name}</h2>
        <p>{product.summary}</p>
        <div className={styles.productPrice}>
          <strong>{product.price}</strong>
          <span>per {product.billing_unit.replaceAll("_", " ")}</span>
        </div>
        <dl className={styles.productSpecs}>
          <div>
            <dt>Edition</dt>
            <dd>{product.edition}</dd>
          </div>
          <div>
            <dt>Company fit</dt>
            <dd>{product.fit ?? "Not evaluated"}</dd>
          </div>
          <div>
            <dt>Deployment</dt>
            <dd>{product.deployment ?? "Varies"}</dd>
          </div>
          <div>
            <dt>Capacity</dt>
            <dd>{product.seats ?? "Contact seller"}</dd>
          </div>
          <div>
            <dt>Requirements</dt>
            <dd>{product.requirement_coverage ?? "Not evaluated"}</dd>
          </div>
          <div>
            <dt>Admin effort</dt>
            <dd>{product.admin_effort ?? "Unknown"}</dd>
          </div>
          <div>
            <dt>Evidence freshness</dt>
            <dd>{product.evidence_freshness ?? "Unknown"}</dd>
          </div>
        </dl>
      </section>
      <section className={styles.contextSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span>Company context</span>
            <h3>Why it makes sense</h3>
          </div>
          <Layers3 aria-hidden="true" />
        </div>
        <p className={styles.sectionCopy}>
          {product.why_company ?? "Company fit has not been evaluated yet."}
        </p>
        {product.limitation ? (
          <p className={styles.productLimitation}>
            <strong>Important limitation</strong>
            {product.limitation}
          </p>
        ) : null}
      </section>
      <section className={styles.contextSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span>Evidence</span>
            <h3>Published claims</h3>
          </div>
          <FileCheck2 aria-hidden="true" />
        </div>
        <ul>
          {product.claims.map((claim) => (
            <li key={claim}>{claim}</li>
          ))}
        </ul>
      </section>
      <section className={styles.contextSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span>Stack fit</span>
            <h3>Native integrations</h3>
          </div>
          <Plug aria-hidden="true" />
        </div>
        <div className={styles.integrationTags}>
          {product.integrations.map((item) => (
            <span key={item}>{item.replaceAll("_", " ")}</span>
          ))}
        </div>
        {product.website ? (
          <a className={styles.evidenceLink} href={product.website} target="_blank" rel="noreferrer">
            Open current vendor evidence <ArrowRight aria-hidden="true" />
          </a>
        ) : null}
      </section>
    </div>
  );
}

function ArtifactPanel({
  artifact,
  onApproveDecision,
  approvalState,
}: {
  artifact: MissionArtifactView | null;
  onApproveDecision: (decisionHash: string) => Promise<void>;
  approvalState: "idle" | "saving" | "approved" | "error";
}) {
  if (!artifact) {
    return (
      <div className={styles.contextBody}>
        <section className={styles.documentHeader}>
          <span>Mission artifact</span>
          <h2>Nothing selected</h2>
          <p>Open an artifact from the mission stream to inspect its evidence and limits.</p>
        </section>
      </div>
    );
  }
  if (artifact.kind === "cited_decision") {
    return (
      <CitedDecisionPanel
        artifact={artifact}
        onApproveDecision={onApproveDecision}
        approvalState={approvalState}
      />
    );
  }
  const sources = artifact.source_refs ?? [];
  const entries = Object.entries(artifact.payload);
  return (
    <div className={styles.contextBody}>
      <section className={styles.documentHeader}>
        <span>{artifact.kind.replaceAll("_", " ")}</span>
        <h2>{artifact.title}</h2>
        <p>
          {artifact.authority.toLowerCase().replaceAll("_", " ")} evidence ·{" "}
          {(artifact.status ?? "ready").toLowerCase()}
        </p>
      </section>
      <section className={styles.contextSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span>{artifact.kind.includes("experiment") ? "Observed work" : "Mission output"}</span>
            <h3>
              {artifact.kind === "comparison"
                ? "Compared options"
                : artifact.kind === "candidate_set"
                  ? "Candidate set"
                  : artifact.kind === "purchase_proposal"
                    ? "Authority path"
                    : artifact.kind === "recommendation"
                      ? "Recommendation and uncertainty"
                      : artifact.kind.includes("experiment")
                        ? "Procedure and observations"
                        : "Structured evidence"}
            </h3>
          </div>
          <FileCheck2 aria-hidden="true" />
        </div>
        <dl className={styles.artifactFields}>
          {entries.map(([key, value]) => (
            <div key={key}>
              <dt>{key.replaceAll("_", " ")}</dt>
              <dd>
                {Array.isArray(value) ? (
                  <ul>
                    {value.map((item, index) => (
                      <li key={`${key}-${index}`}>
                        {typeof item === "object" && item !== null
                          ? Object.entries(item)
                              .map(([itemKey, itemValue]) => `${itemKey.replaceAll("_", " ")}: ${String(itemValue)}`)
                              .join(" · ")
                          : String(item)}
                      </li>
                    ))}
                  </ul>
                ) : typeof value === "object" && value !== null ? (
                  <span>
                    {Object.entries(value)
                      .map(([itemKey, itemValue]) => `${itemKey.replaceAll("_", " ")}: ${String(itemValue)}`)
                      .join(" · ")}
                  </span>
                ) : (
                  String(value)
                )}
              </dd>
            </div>
          ))}
        </dl>
      </section>
      <section className={styles.contextSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span>Provenance</span>
            <h3>{sources.length} source references</h3>
          </div>
          <FileSearch aria-hidden="true" />
        </div>
        {sources.length ? (
          <ul className={styles.artifactSources}>
            {sources.map((source, index) => (
              <li key={`${artifact.id}-source-${index}`}>
                {typeof source.url === "string" ? (
                  <a href={source.url} target="_blank" rel="noreferrer">
                    {String(source.title ?? source.url)}
                  </a>
                ) : (
                  Object.entries(source)
                    .map(([key, value]) => `${key.replaceAll("_", " ")}: ${String(value)}`)
                    .join(" · ")
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className={styles.sectionCopy}>
            No external source was attached; treat this as inferred work.
          </p>
        )}
      </section>
    </div>
  );
}

type CitedProduct = {
  product_id?: unknown;
  product_name?: unknown;
  eligible?: unknown;
  unit_price?: unknown;
  reason_codes?: unknown;
};

function CitedDecisionPanel({
  artifact,
  onApproveDecision,
  approvalState,
}: {
  artifact: MissionArtifactView;
  onApproveDecision: (decisionHash: string) => Promise<void>;
  approvalState: "idle" | "saving" | "approved" | "error";
}) {
  const payload = artifact.payload;
  const products = Array.isArray(payload.evaluated_products)
    ? payload.evaluated_products.filter(
        (item): item is CitedProduct => typeof item === "object" && item !== null,
      )
    : [];
  const sources = artifact.source_refs ?? [];
  const changed = payload.private_context_effect === "WINNER_CHANGED";
  const genericWinnerId = String(payload.without_private_context ?? "");
  const genericWinner = products.find(
    (product) => String(product.product_id ?? "") === genericWinnerId,
  );
  const decisionHash = String(payload.decision_hash ?? "");

  return (
    <div className={styles.contextBody}>
      <section className={styles.documentHeader}>
        <span>Snowflake governed decision</span>
        <h2>{String(payload.selected_product ?? artifact.title)}</h2>
        <p>
          {changed
            ? "Private company context materially changed the recommendation."
            : "The recommendation remained stable when private context was removed."}
        </p>
      </section>
      <section className={styles.contextSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span>Causal proof</span>
            <h3>Why this won</h3>
          </div>
          <BadgeCheck aria-hidden="true" />
        </div>
        <dl className={styles.artifactFields}>
          <div>
            <dt>With private context</dt>
            <dd>{String(payload.selected_product ?? "No eligible product")}</dd>
          </div>
          <div>
            <dt>Without it</dt>
            <dd>
              {String(
                genericWinner?.product_name ??
                  payload.without_private_context ??
                  "No eligible product",
              )}
            </dd>
          </div>
          <div>
            <dt>Effect</dt>
            <dd>{changed ? "Winner changed" : "Winner unchanged"}</dd>
          </div>
        </dl>
        {decisionHash.startsWith("sha256:") ? (
          <div className={styles.decisionApproval}>
            <button
              type="button"
              disabled={approvalState === "saving" || approvalState === "approved"}
              onClick={() => void onApproveDecision(decisionHash)}
            >
              {approvalState === "saving"
                ? "Recording approval…"
                : approvalState === "approved"
                  ? "Approval recorded"
                  : "Approve recommendation"}
            </button>
            <small>
              {approvalState === "error"
                ? "Approval was not recorded. Check your authority and retry."
                : "Creates a tamper-evident Snowflake approval event; it does not purchase."}
            </small>
          </div>
        ) : null}
      </section>
      <section className={styles.contextSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span>Deterministic evaluation</span>
            <h3>{products.length} products evaluated</h3>
          </div>
          <Layers3 aria-hidden="true" />
        </div>
        <div className={styles.decisionMiniList}>
          {products.map((product, index) => {
            const reasons = Array.isArray(product.reason_codes)
              ? product.reason_codes.map(String).map((item) => item.replaceAll("_", " "))
              : [];
            return (
              <article key={String(product.product_id ?? index)}>
                <span>{product.eligible === true ? "Eligible" : "Passed honestly"}</span>
                <strong>{String(product.product_name ?? product.product_id ?? "Product")}</strong>
                <small>
                  {product.unit_price ? `USD ${String(product.unit_price)} · ` : ""}
                  {reasons.join(" · ") || "No reason code recorded"}
                </small>
              </article>
            );
          })}
        </div>
      </section>
      <section className={styles.contextSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span>Evidence lineage</span>
            <h3>{sources.length} cited facts and document passages</h3>
          </div>
          <FileSearch aria-hidden="true" />
        </div>
        <ul className={styles.artifactSources}>
          {sources.map((source, index) => (
            <li key={`${artifact.id}-citation-${index}`}>
              <strong>{String(source.citation_type ?? "SOURCE")}</strong>
              {source.exact_excerpt ? ` — ${String(source.exact_excerpt)}` : ""}
            </li>
          ))}
        </ul>
      </section>
      <section className={styles.contextSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span>Audit identity</span>
            <h3>Reproducible decision</h3>
          </div>
          <ShieldCheck aria-hidden="true" />
        </div>
        <dl className={styles.artifactFields}>
          <div>
            <dt>Run</dt>
            <dd>{String(payload.run_id ?? "Not recorded")}</dd>
          </div>
          <div>
            <dt>Decision hash</dt>
            <dd>{String(payload.decision_hash ?? "Not recorded")}</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}

function AgentRunPanel({
  message,
  onSelectArtifact,
}: {
  message: ChatMessage | null;
  onSelectArtifact: (artifact: MissionArtifactView) => void;
}) {
  if (!message) {
    return (
      <div className={styles.emptyContext}>
        <Info aria-hidden="true" />
        <h3>No run selected</h3>
        <p>Open the info button beside an agent response to inspect its run.</p>
      </div>
    );
  }

  return (
    <div className={styles.contextStack}>
      <section className={styles.contextSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span>Agent run</span>
            <h3>
              {message.mission?.state.toLowerCase().replaceAll("_", " ") ??
                message.meta ??
                "Response details"}
            </h3>
          </div>
          <Info aria-hidden="true" />
        </div>
        <dl className={styles.artifactFields}>
          <div><dt>Response</dt><dd>{message.meta ?? "Completed"}</dd></div>
          {message.mission ? (
            <>
              <div><dt>Mission version</dt><dd>v{message.mission.version}</dd></div>
              <div><dt>Runtime state</dt><dd>{message.mission.state.replaceAll("_", " ")}</dd></div>
            </>
          ) : null}
          <div><dt>Tools called</dt><dd>{message.toolCalls?.length ? message.toolCalls.join(", ") : "None"}</dd></div>
        </dl>
      </section>

      {message.events?.length ? (
        <section className={styles.contextSection}>
          <div className={styles.sectionHeading}>
            <div><span>Trace</span><h3>What the agent did</h3></div>
            <Clock3 aria-hidden="true" />
          </div>
          <ol className={styles.runTrace}>
            {message.events.map((event) => (
              <li key={event.id}>
                {event.verified ? <Check aria-hidden="true" /> : <Clock3 aria-hidden="true" />}
                <span><strong>{event.summary}</strong><small>{event.verified ? "Runtime verified" : "Agent reported"}</small></span>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      {message.openTasks?.length || message.handoffs?.length ? (
        <section className={styles.contextSection}>
          <div className={styles.sectionHeading}>
            <div><span>Next</span><h3>Work and authority</h3></div>
            <ShieldCheck aria-hidden="true" />
          </div>
          {message.openTasks?.map((task, index) => (
            <div className={styles.runDetailRow} key={String(task.id ?? index)}>
              <strong>{String(task.title ?? task.kind ?? "Mission task")}</strong>
              <small>{String(task.status ?? "pending").toLowerCase()}</small>
            </div>
          ))}
          {message.handoffs?.map((handoff, index) => {
            const workflow = handoff.workflow as { status?: unknown } | null;
            return (
              <div className={styles.runDetailRow} key={String(handoff.request_id ?? index)}>
                <strong>Buying decision {String(handoff.status ?? "created")}</strong>
                <small>{workflow ? `Temporal workflow ${String(workflow.status ?? "pending")}` : "Approval required before execution"}</small>
              </div>
            );
          })}
        </section>
      ) : null}

      {message.artifacts?.length ? (
        <section className={styles.contextSection}>
          <div className={styles.sectionHeading}>
            <div><span>Outputs</span><h3>Run artifacts</h3></div>
            <FileCheck2 aria-hidden="true" />
          </div>
          <div className={styles.missionArtifacts}>
            {message.artifacts.map((artifact) => (
              <button key={artifact.id} type="button" onClick={() => onSelectArtifact(artifact)}>
                <FileCheck2 aria-hidden="true" />
                <span><small>{artifact.kind.replaceAll("_", " ")}</small><strong>{artifact.title}</strong></span>
                <ArrowRight aria-hidden="true" />
              </button>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function ContextPanel({
  mode,
  tab,
  expanded,
  onTabChange,
  onClose,
  onToggleExpanded,
  products,
  selectedProduct,
  selectedArtifact,
  selectedRunMessage,
  researchArtifacts,
  onSelectProduct,
  onStartChat,
  onSelectArtifact,
  onApproveDecision,
  approvalState,
  activeDecision,
  onSelectDecision,
  onBackDecision,
}: {
  mode: CommerceWorkspaceMode;
  tab: CommerceContextTab;
  expanded: boolean;
  onTabChange: (tab: CommerceContextTab) => void;
  onClose: () => void;
  onToggleExpanded: () => void;
  products: CatalogProduct[];
  selectedProduct: CatalogProduct | null;
  selectedArtifact: MissionArtifactView | null;
  selectedRunMessage: ChatMessage | null;
  researchArtifacts: MissionArtifactView[];
  onSelectProduct: (product: CatalogProduct) => void;
  onStartChat: () => void;
  onSelectArtifact: (artifact: MissionArtifactView) => void;
  onApproveDecision: (decisionHash: string) => Promise<void>;
  approvalState: "idle" | "saving" | "approved" | "error";
  activeDecision: ActiveDecision | null;
  onSelectDecision: (decision: ActiveDecision) => void;
  onBackDecision: () => void;
}) {
  return (
    <aside
      className={`${styles.contextPanel} ${expanded ? styles.contextPanelExpanded : ""}`}
      aria-label="Object inspector"
    >
      <header className={styles.contextHeader}>
        <div className={styles.contextHeaderTools} aria-hidden="true" />
        <div className={styles.contextTitle}>
          {tab === "run"
            ? "Agent run details"
            : tab === "artifact"
            ? (selectedArtifact?.title ?? "Mission artifact")
            : tab === "decisions"
              ? "Decisions"
              : tab === "inbox"
                ? "Inbox"
                : tab === "catalog"
                  ? "Catalogue"
                  : tab === "product"
                    ? (selectedProduct?.name ?? "Product")
                    : tab === "work"
                      ? mode === "sira"
                        ? "Buying decision"
                        : "Product evidence"
                      : "Connectors"}
        </div>
        <div className={styles.contextHeaderActions}>
          <button
            type="button"
            onClick={onToggleExpanded}
            aria-label={expanded ? "Restore panel width" : "Expand panel"}
            title={expanded ? "Restore panel width" : "Expand panel"}
          >
            <Expand aria-hidden="true" />
          </button>
          <button type="button" onClick={onClose} aria-label="Close inspector" title="Close inspector">
            <X aria-hidden="true" />
          </button>
        </div>
      </header>

      <div className={styles.contextScroller}>
        {tab === "run" ? <AgentRunPanel message={selectedRunMessage} onSelectArtifact={onSelectArtifact} /> : null}
        {tab === "artifact" ? (
          <ArtifactPanel
            artifact={selectedArtifact}
            onApproveDecision={onApproveDecision}
            approvalState={approvalState}
          />
        ) : null}
        {tab === "work" && mode === "sira" ? <SiraWorkPanel /> : null}
        {tab === "work" && mode === "seil" ? <SeilWorkPanel /> : null}
        {tab === "decisions" && activeDecision ? <DecisionWorkspacePanel requestId={activeDecision.requestId} version={activeDecision.version} initialStage={activeDecision.stage} onBack={onBackDecision} /> : null}
        {tab === "decisions" && !activeDecision ? <DecisionsPanel onStart={onStartChat} onSelect={onSelectDecision} /> : null}
        {tab === "inbox" ? <InboxPanel mode={mode} /> : null}
        {tab === "catalog" ? (
          mode === "seil"
            ? <SellerProductsPanel onSelect={onSelectProduct} researchArtifacts={researchArtifacts} onSelectArtifact={onSelectArtifact} />
            : <CatalogPanel products={products} onSelect={onSelectProduct} />
        ) : null}
        {tab === "product" ? (
          mode === "seil"
            ? <SellerProductPanel product={selectedProduct} onBack={() => onTabChange("catalog")} />
            : <ProductPanel product={selectedProduct} onBack={() => onTabChange("catalog")} />
        ) : null}
        {tab === "connectors" ? <ConnectorsPanel mode={mode} /> : null}
      </div>
    </aside>
  );
}

export function CommerceWorkspace({
  initialMode = "sira",
  initialContextTab = "decisions",
  initialDecision = null,
  initialContextOpen = false,
  modeLocked = false,
}: {
  initialMode?: CommerceWorkspaceMode;
  initialContextTab?: CommerceContextTab;
  initialDecision?: ActiveDecision | null;
  initialContextOpen?: boolean;
  modeLocked?: boolean;
}) {
  const firebaseAuth = useFirebaseAuth();
  const firebaseUser = firebaseAuth.user;
  const accountName = firebaseUser?.isAnonymous
    ? "Private guest"
    : firebaseUser?.displayName || firebaseUser?.email || "Verified account";
  const accountInitials = firebaseUser?.isAnonymous
    ? "G"
    : accountName.trim().slice(0, 1).toUpperCase() || "U";
  const [mode, setMode] = useState<CommerceWorkspaceMode>(initialMode);
  const [conversations, setConversations] = useState(cloneSeedConversations);
  const [selectedByMode, setSelectedByMode] = useState<Record<CommerceWorkspaceMode, string>>({
    sira: SEED_CONVERSATIONS.sira[0].id,
    seil: SEED_CONVERSATIONS.seil[0].id,
  });
  const [composer, setComposer] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [contextOpen, setContextOpen] = useState(Boolean(initialDecision) || initialContextOpen);
  const [contextTab, setContextTab] = useState<CommerceContextTab>(
    initialDecision ? "decisions" : initialContextTab,
  );
  const [contextExpanded, setContextExpanded] = useState(false);
  const [activeDecision, setActiveDecision] = useState<ActiveDecision | null>(initialDecision);
  const [running, setRunning] = useState(false);
  const [confirmingProposal, setConfirmingProposal] = useState<string | null>(null);
  const [appliedProposalHashes, setAppliedProposalHashes] = useState<Set<string>>(
    () => new Set(),
  );
  const [snowflakeApprovalState, setSnowflakeApprovalState] = useState<
    "idle" | "saving" | "approved" | "error"
  >("idle");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [catalogProducts, setCatalogProducts] = useState<CatalogProduct[]>(() =>
    WEB_DATA_MODE === "fixture" ? FIXTURE_CATALOG.map(withProductBrand) : [],
  );
  const [selectedProduct, setSelectedProduct] = useState<CatalogProduct | null>(null);
  const [selectedArtifact, setSelectedArtifact] = useState<MissionArtifactView | null>(null);
  const [selectedRunMessage, setSelectedRunMessage] = useState<ChatMessage | null>(null);
  const conversationsQuery = useQuery({
    queryKey: ["workspace-conversations", mode],
    enabled: WEB_DATA_MODE === "api",
    queryFn: () =>
      getBrowserApiClient().request("workspace_conversations", {
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

  useEffect(() => {
    if (!firebaseUser?.uid) return;
    try {
      const stored = window.sessionStorage.getItem(
        `sira.applied-proposals.${firebaseUser.uid}`,
      );
      const hashes = stored ? JSON.parse(stored) : [];
      setAppliedProposalHashes(
        new Set(Array.isArray(hashes) ? hashes.filter((item): item is string => typeof item === "string") : []),
      );
    } catch {
      setAppliedProposalHashes(new Set());
    }
  }, [firebaseUser?.uid]);

  const modeConversations = conversations[mode];
  const selectedConversation =
    modeConversations.find((conversation) => conversation.id === selectedByMode[mode]) ??
    modeConversations[0];
  const messages = selectedConversation?.messages ?? [];
  const messageVersion = `${mode}:${selectedConversation?.id ?? "new"}:${messages.map((message) => `${message.id}:${message.content.length}`).join("|")}`;

  usePretextMessages(messageRootRef, messageVersion);

  useEffect(() => {
    if (WEB_DATA_MODE !== "api" || !conversationsQuery.data) return;
    const restored: Conversation[] = conversationsQuery.data.map((conversation) => {
      const restoredMessages: ChatMessage[] = conversation.messages.map((message) => ({
        id: `${message.role}-${crypto.randomUUID()}`,
        role: message.role,
        content: message.content,
        toolCalls: message.tool_calls,
        proposals: message.proposals,
      }));
      const lastAssistant = restoredMessages.findLastIndex((message) => message.role === "assistant");
      if (lastAssistant >= 0) {
        restoredMessages[lastAssistant] = {
          ...restoredMessages[lastAssistant],
          mission: conversation.mission,
          events: (conversation.events ?? []).filter(
            (event) => !["user.message", "assistant.message"].includes(event.type),
          ),
          artifacts: conversation.artifacts ?? [],
          openTasks: conversation.open_tasks ?? [],
        };
      }
      return {
        id: conversation.id,
        mode: conversation.mode,
        title: conversation.title,
        updatedLabel: "Checkpoint saved",
        messages: restoredMessages,
      };
    });
    const next = restored.length
      ? restored
      : [
          {
            id: `${mode}-new-${crypto.randomUUID()}`,
            mode,
            title: "New mission",
            updatedLabel: "Now",
            messages: [],
          },
        ];
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

  useEffect(
    () => () => {
      if (responseTimerRef.current) clearTimeout(responseTimerRef.current);
      responseAbortRef.current?.abort();
    },
    [],
  );

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
    setContextTab(nextMode === "sira" ? "decisions" : "catalog");
    setContextOpen(false);
    if (compact) setSidebarOpen(false);
  }

  function createNewChat() {
    const id = `${mode}-${crypto.randomUUID()}`;
    const conversation: Conversation = {
      id,
      mode,
      title: "New mission",
      updatedLabel: "Now",
      messages: [],
    };
    setConversations((current) => ({ ...current, [mode]: [conversation, ...current[mode]] }));
    setSelectedByMode((current) => ({ ...current, [mode]: id }));
    setComposer("");
    setContextTab(mode === "sira" ? "decisions" : "catalog");
    setContextOpen(false);
    setRunning(false);
    if (compact) setSidebarOpen(false);
  }

  async function restoreMission(id: string, targetMode = mode) {
    if (WEB_DATA_MODE !== "api" || !id.startsWith("msn_")) return;
    try {
      const snapshot = await getBrowserApiClient().request("workspace_mission", {
        headers: targetMode === "seil" ? sellerEditorDevelopmentHeaders : buyerDevelopmentHeaders,
        pathParams: { mission_id: id },
      });
      updateConversation(targetMode, id, (conversation) => {
        const assistantIndex = conversation.messages.findLastIndex(
          (message) => message.role === "assistant",
        );
        const missionMessage: ChatMessage = {
          id: `checkpoint-${snapshot.mission.version}`,
          role: "assistant",
          content: assistantIndex >= 0 ? conversation.messages[assistantIndex].content : "",
          meta: "Checkpoint restored",
          mission: snapshot.mission,
          events: snapshot.events.filter(
            (event) => !["user.message", "assistant.message"].includes(event.type),
          ),
          artifacts: snapshot.artifacts,
          openTasks: snapshot.open_tasks,
          handoffs: snapshot.handoffs,
        };
        const messages = [...conversation.messages];
        if (assistantIndex >= 0) messages[assistantIndex] = { ...messages[assistantIndex], ...missionMessage };
        else messages.push(missionMessage);
        return { ...conversation, messages, updatedLabel: "Checkpoint restored" };
      });
    } catch {
      // Keep the last safe local projection. The inline retry path remains available.
    }
  }

  function selectConversation(id: string) {
    setSelectedByMode((current) => ({ ...current, [mode]: id }));
    setComposer("");
    setRunning(false);
    if (compact) setSidebarOpen(false);
    void restoreMission(id);
  }

  function openContext(tab: CommerceContextTab) {
    setContextTab(tab);
    setContextOpen(true);
    if (compact) setSidebarOpen(false);
  }

  async function approveSnowflakeDecision(decisionHash: string) {
    setSnowflakeApprovalState("saving");
    try {
      await getBrowserApiClient().request("approve_snowflake_decision", {
        headers: buyerDevelopmentHeaders,
        body: { decision_hash: decisionHash },
      });
      setSnowflakeApprovalState("approved");
    } catch {
      setSnowflakeApprovalState("error");
    }
  }

  async function submitMessage(value = composer.trim()) {
    if (!value || running || !selectedConversation) return;
    const targetMode = mode;
    const conversationId = selectedConversation.id;
    const missionId = conversationId.startsWith("msn_")
      ? conversationId
      : `msn_${crypto.randomUUID().replaceAll("-", "")}`;
    const activeConversationId = WEB_DATA_MODE === "api" ? missionId : conversationId;
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
      id: activeConversationId,
      title:
        conversation.title === "New mission" ? buildConversationTitle(value) : conversation.title,
      updatedLabel: "Now",
      messages: [...conversation.messages, userMessage, assistantMessage],
    }));
    if (WEB_DATA_MODE === "api") {
      setSelectedByMode((current) => ({ ...current, [targetMode]: missionId }));
    }
    setComposer("");
    setRunning(true);

    if (WEB_DATA_MODE === "fixture") {
      responseTimerRef.current = setTimeout(() => {
        const response = responseFor(targetMode, value);
        const products = fixtureProductsForPrompt(targetMode, value).map(withProductBrand);
        if (products.length) setCatalogProducts(products);
        updateConversation(targetMode, activeConversationId, (conversation) => ({
          ...conversation,
          messages: conversation.messages.map((message) =>
            message.id === assistantId
              ? { ...message, content: response, meta: "Preview updated", products }
              : message,
          ),
        }));
        if (targetMode === mode) setRunning(false);
        responseTimerRef.current = null;
      }, 850);
      return;
    }

    const controller = new AbortController();
    responseAbortRef.current = controller;
    try {
      const history = selectedConversation.messages
        .slice(-20)
        .map(({ role, content }) => ({ role, content }));
      const payload = await getBrowserApiClient().request("workspace_chat", {
        headers: {
          ...(targetMode === "seil" ? sellerEditorDevelopmentHeaders : buyerDevelopmentHeaders),
        },
        body: {
          mission_id: missionId,
          mode: targetMode,
          message: value,
          history,
        },
        signal: controller.signal,
      });
      const products = (payload.products ?? []).map(withProductBrand);
      if (products.length) setCatalogProducts(products);
      updateConversation(targetMode, activeConversationId, (conversation) => ({
        ...conversation,
        id: payload.conversation_id,
        messages: conversation.messages.map((message) =>
          message.id === assistantId
            ? {
                ...message,
                content: payload.message ?? "I need a little more context.",
                meta: products.length ? "Matches ready" : "Mission updated",
                products,
                toolCalls: payload.tool_calls ?? [],
                proposals: payload.proposals ?? [],
                mission: payload.mission,
                events: payload.events,
                artifacts: payload.artifacts,
                attention: payload.attention ?? undefined,
                retryText: undefined,
              }
            : message,
        ),
      }));
      setSelectedByMode((current) => ({ ...current, [targetMode]: payload.conversation_id }));
    } catch (error) {
      if (!controller.signal.aborted) {
        updateConversation(targetMode, activeConversationId, (conversation) => ({
          ...conversation,
          messages: conversation.messages.map((message) =>
            message.id === assistantId
              ? {
                  ...message,
                  content:
                    error instanceof Error ? error.message : "SIRA is temporarily unavailable.",
                  meta: "Could not complete",
                  retryText: value,
                }
              : message,
          ),
        }));
      }
    } finally {
      if (responseAbortRef.current === controller) responseAbortRef.current = null;
      if (targetMode === mode) setRunning(false);
    }
  }

  async function confirmProposal(messageId: string, proposal: AgentProposalView) {
    if (confirmingProposal) return;
    setConfirmingProposal(proposal.proposal_hash);
    try {
      if (proposal.proposal_type === "PURCHASE_REQUEST") {
        const intent = proposal.payload.intent;
        if (typeof intent !== "string" || intent.trim().length < 10) {
          throw new Error("The proposed buying intent is incomplete.");
        }
        const visibility = proposal.payload.visibility === "PRIVATE" ? "PRIVATE" : "SELECTIVE";
        const created = await getBrowserApiClient().request("create_decision_request", {
          headers: buyerDevelopmentHeaders,
          idempotencyKey: `agent-proposal-${proposal.proposal_hash.replace("sha256:", "")}`,
          body: {
            intent: intent.trim(),
            visibility,
            scenario_id: "consultco_meeting_intelligence_v1",
            mission_id: selectedConversation.id.startsWith("msn_")
              ? selectedConversation.id
              : undefined,
          },
        });
        await getBrowserApiClient().request("discover_decision_request", {
          headers: buyerDevelopmentHeaders,
          pathParams: { request_id: created.id },
          idempotencyKey: `discover-${created.id}`,
        });
        setActiveDecision({ requestId: created.id, version: 1, stage: "options" });
        setContextTab("decisions");
      } else {
        const draftId = proposal.payload.draft_id;
        if (typeof draftId !== "string" || !draftId) {
          throw new Error("The proposal has no authorized packet draft.");
        }
        const draft = await getBrowserApiClient().request("seller_evidence_get_draft", {
          headers: sellerEditorDevelopmentHeaders,
          pathParams: { draft_id: draftId },
        });
        const idempotencyKey = `agent-proposal-${proposal.proposal_hash.replace("sha256:", "")}`;
        if (proposal.proposal_type === "PACK_REVIEW_REQUEST") {
          await getBrowserApiClient().request("seller_evidence_submit_review", {
            headers: sellerEditorDevelopmentHeaders,
            pathParams: { draft_id: draftId },
            idempotencyKey,
            body: { revision_hash: draft.revision_hash },
          });
        } else if (["PACK_CLAIM", "FIT_RULE", "ANTI_FIT_RULE"].includes(proposal.proposal_type)) {
          const field = proposal.payload.field;
          const rawValue = proposal.payload.value;
          if (typeof field !== "string" || typeof rawValue !== "string") {
            throw new Error("The proposed packet change is incomplete.");
          }
          const value = proposal.proposal_type === "PACK_CLAIM"
            ? rawValue
            : `${typeof proposal.payload.operator === "string" ? proposal.payload.operator : "equals"} ${rawValue}`;
          const evidenceIds = Array.isArray(proposal.payload.evidence_ids)
            ? proposal.payload.evidence_ids.filter((item): item is string => typeof item === "string")
            : [];
          const change = { field, value, evidence_ids: evidenceIds };
          await getBrowserApiClient().request("seller_evidence_patch_draft", {
            headers: sellerEditorDevelopmentHeaders,
            pathParams: { draft_id: draftId },
            idempotencyKey,
            body: {
              base_revision: draft.revision,
              ...(proposal.proposal_type === "PACK_CLAIM" ? { claims: [change] } : {}),
              ...(proposal.proposal_type === "FIT_RULE" ? { fit_rules: [change] } : {}),
              ...(proposal.proposal_type === "ANTI_FIT_RULE" ? { anti_fit_rules: [change] } : {}),
            },
          });
        } else {
          throw new Error("This proposed action is not supported.");
        }
        setContextTab("catalog");
      }
      if (selectedConversation) {
        updateConversation(mode, selectedConversation.id, (conversation) => ({
          ...conversation,
          messages: conversation.messages.map((message) =>
            message.id === messageId
              ? {
                  ...message,
                  meta: proposal.proposal_type === "PURCHASE_REQUEST" ? "Decision created" : "Packet updated",
                  proposals: message.proposals?.filter(
                    (item) => item.proposal_hash !== proposal.proposal_hash,
                  ),
                }
              : message,
          ),
        }));
      }
      setAppliedProposalHashes((current) => {
        const next = new Set(current).add(proposal.proposal_hash);
        if (firebaseUser?.uid) {
          window.sessionStorage.setItem(
            `sira.applied-proposals.${firebaseUser.uid}`,
            JSON.stringify([...next]),
          );
        }
        return next;
      });
      setContextOpen(true);
      if (selectedConversation.id.startsWith("msn_")) {
        await restoreMission(selectedConversation.id, mode);
      }
    } catch (error) {
      if (selectedConversation) {
        updateConversation(mode, selectedConversation.id, (conversation) => ({
          ...conversation,
          messages: conversation.messages.map((message) =>
            message.id === messageId
              ? {
                  ...message,
                  meta: error instanceof Error ? error.message : "Could not apply proposal",
                }
              : message,
          ),
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
            ? {
                ...message,
                content: "Paused. Continue whenever you are ready.",
                meta: "Agent paused",
              }
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
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <main className={shellClass} data-mode={mode}>
      <a className={styles.skipLink} href="#chat-thread">
        Skip to mission
      </a>

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
          onCloseContext={() => {
            setContextOpen(false);
            setContextExpanded(false);
          }}
          onOpenContext={openContext}
          onOpenSettings={() => setSettingsOpen(true)}
          account={{
            initials: accountInitials,
            name: accountName,
            detail: firebaseUser?.isAnonymous ? "Isolated workspace" : "Firebase account",
          }}
        />
      ) : null}

      <section className={styles.chatPanel} aria-label={`${MODE_COPY[mode].name} mission`}>
        <header className={styles.chatHeader}>
          <div className={styles.chatHeaderLeft}>
            {!sidebarOpen ? (
              <button
                type="button"
                onClick={() => {
                  setSidebarOpen(true);
                  if (compact) setContextOpen(false);
                }}
                aria-label="Open sidebar"
                title="Open sidebar"
              >
                <PanelLeftOpen aria-hidden="true" />
              </button>
            ) : null}
            <div>
              <strong>{selectedConversation?.title ?? "New mission"}</strong>
              <small>
                <span />{" "}
                {WEB_DATA_MODE === "fixture"
                  ? "Development preview · sample workflow"
                  : `${MODE_COPY[mode].name} ${MODE_COPY[mode].accentLabel.toLowerCase()}`}
              </small>
            </div>
          </div>
          <div className={styles.chatHeaderActions}>
            <button
              type="button"
              onClick={() => {
                setContextOpen(true);
                if (compact) setSidebarOpen(false);
              }}
              aria-label="Open inspector"
              title="Open inspector"
            >
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
            shouldAutoScrollRef.current =
              viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight < 96;
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
                    <button key={suggestion} type="button" onClick={() => setComposer(suggestion)}>
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            {messages.map((message) =>
              message.role === "user" ? (
                <article className={styles.userMessage} key={message.id}>
                  <div className={styles.userBubble}>
                    <ChatMessageBody content={message.content} tone="user" />
                  </div>
                </article>
              ) : (
                <article className={styles.assistantMessage} key={message.id}>
                  {message.content ? (
                    <div className={styles.messageHeader}>
                      {message.meta ? (
                        <p className={styles.messageMeta}>
                          <Sparkles aria-hidden="true" /> {message.meta}
                        </p>
                      ) : <span />}
                      {message.events?.length || message.artifacts?.length || message.mission || message.toolCalls?.length ? (
                        <button
                          className={styles.messageInfoButton}
                          type="button"
                          aria-label="Open agent run details"
                          title="Agent run details"
                          onClick={() => {
                            setSelectedRunMessage(message);
                            setContextTab("run");
                            setContextOpen(true);
                          }}
                        >
                          <Info aria-hidden="true" />
                        </button>
                      ) : null}
                    </div>
                  ) : null}
                  {message.content ? (
                    <ChatMessageBody content={message.content} />
                  ) : (
                    <AgentWorkingState mode={mode} />
                  )}
                  {message.attention ? (
                    <section className={styles.attentionCard}>
                      <span>{message.attention.kind}</span>
                      <strong>{message.attention.prompt}</strong>
                      <p>{message.attention.reason}</p>
                      {message.attention.options?.length ? (
                        <div>
                          {message.attention.options.map((option) => (
                            <button type="button" key={option} onClick={() => setComposer(option)}>
                              {option}
                            </button>
                          ))}
                        </div>
                      ) : null}
                    </section>
                  ) : null}
                  {message.retryText ? (
                    <button
                      className={styles.inlineRetry}
                      type="button"
                      disabled={running}
                      onClick={() => void submitMessage(message.retryText)}
                    >
                      Retry from the saved checkpoint
                    </button>
                  ) : null}
                  {message.products?.length ? (
                    <div className={styles.messageProductShelf} aria-label="Matching products">
                      {message.products.map((product) => (
                        <ProductCard
                          key={product.id}
                          product={product}
                          compact
                          onSelect={(selected) => {
                            setSelectedProduct(selected);
                            openContext("product");
                          }}
                        />
                      ))}
                    </div>
                  ) : null}
                  {message.artifacts
                    ?.filter((artifact) => artifact.kind === "cited_decision")
                    .map((artifact) => {
                      const selectedProduct =
                        typeof artifact.payload.selected_product === "string"
                          ? artifact.payload.selected_product
                          : "Recommendation ready";
                      const decisionHash =
                        typeof artifact.payload.decision_hash === "string"
                          ? artifact.payload.decision_hash
                          : "";
                      const contextEffect =
                        typeof artifact.payload.private_context_effect === "string"
                          ? artifact.payload.private_context_effect
                          : "Private company context and cited seller evidence were evaluated in Snowflake.";
                      return (
                        <button
                          className={styles.governedResultCard}
                          key={artifact.id}
                          type="button"
                          onClick={() => {
                            setSelectedArtifact(artifact);
                            setContextTab("artifact");
                            setContextOpen(true);
                          }}
                        >
                          <span><ShieldCheck aria-hidden="true" /> Governed decision</span>
                          <strong>{selectedProduct}</strong>
                          <p>{contextEffect}</p>
                          <small>
                            {decisionHash ? `Decision ${decisionHash.slice(0, 12)}…` : "Open cited evidence"}
                            <ArrowRight aria-hidden="true" />
                          </small>
                        </button>
                      );
                    })}
                  {message.proposals?.filter((proposal) => !appliedProposalHashes.has(proposal.proposal_hash)).map((proposal) => (
                    <section className={styles.proposalCard} key={proposal.proposal_hash}>
                      <div>
                        <span>Requires your confirmation</span>
                        <strong>
                          {proposal.proposal_type === "PURCHASE_REQUEST"
                            ? "Create this buying decision"
                            : proposal.proposal_type === "PACK_REVIEW_REQUEST"
                              ? "Submit this packet for review"
                              : proposal.proposal_type === "PACK_CLAIM"
                                ? "Add this evidence-backed claim"
                                : proposal.proposal_type === "FIT_RULE"
                                  ? "Add this fit rule"
                                  : "Add this anti-fit rule"}
                        </strong>
                        {typeof proposal.payload.intent === "string" ? (
                          <p>{proposal.payload.intent}</p>
                        ) : null}
                      </div>
                      <button
                        type="button"
                        disabled={confirmingProposal !== null}
                        onClick={() => void confirmProposal(message.id, proposal)}
                      >
                        {confirmingProposal === proposal.proposal_hash
                          ? "Applying…"
                          : proposal.proposal_type === "PACK_REVIEW_REQUEST"
                            ? "Confirm and submit"
                            : "Confirm and apply"}
                        <ArrowRight aria-hidden="true" />
                      </button>
                    </section>
                  ))}
                  {message.proposals?.some((proposal) => appliedProposalHashes.has(proposal.proposal_hash)) ? (
                    <section className={styles.proposalReceipt}>
                      <Check aria-hidden="true" />
                      <div>
                        <strong>Applied successfully</strong>
                        <span>The durable workspace record is ready in the detail panel.</span>
                      </div>
                    </section>
                  ) : null}
                </article>
              ),
            )}
            <div ref={messageBottomRef} />
          </div>
        </div>

        <div className={styles.composerDock}>
          <div className={styles.composer}>
            <textarea
              aria-label={`Direct ${MODE_COPY[mode].name}`}
              onChange={(event) => setComposer(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  if (running) stopResponse();
                  else submitMessage();
                }
              }}
              placeholder="Direct the mission..."
              rows={1}
              value={composer}
            />
            <div className={styles.composerToolbar}>
              <div>
                {WEB_DATA_MODE === "fixture" ? (
                  <>
                    <input
                      className={styles.hiddenFileInput}
                      ref={fileInputRef}
                      type="file"
                      onChange={handleFile}
                    />
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      aria-label="Preview company context attachment"
                      title="Preview company context attachment"
                    >
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
                    <select
                      value={mode}
                      onChange={(event) => switchMode(event.target.value as CommerceWorkspaceMode)}
                    >
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
            {MODE_COPY[mode].privacy}. The agent can investigate and recommend; protected actions
            still require your exact authority.
          </p>
        </div>
      </section>

      {contextOpen ? (
        <ContextPanel
          mode={mode}
          tab={contextTab}
          expanded={contextExpanded}
          onTabChange={setContextTab}
          onClose={() => {
            setContextOpen(false);
            setContextExpanded(false);
          }}
          onToggleExpanded={() => setContextExpanded((current) => !current)}
          products={catalogProducts}
          selectedProduct={selectedProduct}
          selectedArtifact={selectedArtifact}
          selectedRunMessage={selectedRunMessage}
          researchArtifacts={selectedConversation?.messages.flatMap((message) => message.artifacts ?? []) ?? []}
          onSelectProduct={(product) => {
            setSelectedProduct(product);
            setContextTab("product");
          }}
          onStartChat={() => {
            setContextOpen(false);
            setComposer("What do you want to buy today? ");
          }}
          onSelectArtifact={(artifact) => {
            setSelectedArtifact(artifact);
            setContextTab("artifact");
          }}
          onApproveDecision={approveSnowflakeDecision}
          approvalState={snowflakeApprovalState}
          activeDecision={activeDecision}
          onSelectDecision={(decision) => {
            setActiveDecision(decision);
            setContextTab("decisions");
            setContextOpen(true);
          }}
          onBackDecision={() => setActiveDecision(null)}
        />
      ) : null}

      {settingsOpen ? (
        <ProfileSettingsModal
          workspace={mode}
          onClose={() => setSettingsOpen(false)}
          identity={{
            displayName: firebaseUser?.displayName ?? null,
            email: firebaseUser?.email ?? null,
            isAnonymous: firebaseUser?.isAnonymous ?? true,
          }}
          onSignOut={firebaseAuth.signOut}
          onUpgradeGuest={firebaseAuth.upgradeGuestWithGoogle}
        />
      ) : null}

      {compact && (sidebarOpen || contextOpen) ? (
        <button
          className={styles.mobileScrim}
          type="button"
          aria-label="Close open panel"
          onClick={() => {
            setSidebarOpen(false);
            setContextOpen(false);
          }}
        />
      ) : null}
    </main>
  );
}
