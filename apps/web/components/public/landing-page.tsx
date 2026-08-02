"use client";

import {
  ArrowRight,
  BadgeCheck,
  Building2,
  Check,
  FileSearch,
  LockKeyhole,
  PackageCheck,
  PlugZap,
  ReceiptText,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, type RefObject } from "react";
import { layout, prepare, type PreparedText } from "@chenglou/pretext";

import { CombinedBrandLogo } from "@/components/brand/combined-brand-logo";

import styles from "./landing-page.module.css";

type PreparedElement = {
  element: HTMLElement;
  prepared: PreparedText;
  lineHeight: number;
};

function usePretextLayout(rootRef: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;

    let cancelled = false;
    let observer: ResizeObserver | undefined;

    const start = async () => {
      await document.fonts.ready;
      if (cancelled) return;

      const entries: PreparedElement[] = Array.from(
        root.querySelectorAll<HTMLElement>("[data-pretext]"),
      ).map((element) => {
        const computed = getComputedStyle(element);
        const parsedLineHeight = Number.parseFloat(computed.lineHeight);
        const fontSize = Number.parseFloat(computed.fontSize);

        return {
          element,
          prepared: prepare(element.textContent ?? "", computed.font),
          lineHeight: Number.isFinite(parsedLineHeight)
            ? parsedLineHeight
            : fontSize * 1.4,
        };
      });

      const relayout = () => {
        for (const entry of entries) {
          const width = entry.element.getBoundingClientRect().width;
          if (width <= 0) continue;
          const result = layout(entry.prepared, width, entry.lineHeight);
          entry.element.style.setProperty(
            "--pretext-height",
            `${Math.ceil(result.height)}px`,
          );
        }
      };

      observer = new ResizeObserver(relayout);
      observer.observe(root);
      relayout();
    };

    void start();

    return () => {
      cancelled = true;
      observer?.disconnect();
    };
  }, [rootRef]);
}

const buyerOutcomes = [
  "Reuse or configure what the company already has",
  "Renew, resize, replace, cancel, buy, or take no action",
  "Approve the exact plan, amount, and authority path",
  "Verify the result and update the company Stack",
];

const sellerOutcomes = [
  "Compile private product knowledge without exposing it",
  "Publish current evidence, fit rules, and anti-fit rules",
  "Respond to qualified requirements with a pass or offer",
  "Keep claims, fulfillment, and product changes current",
];

export function LandingPage() {
  const pageRef = useRef<HTMLElement>(null);
  usePretextLayout(pageRef);

  return (
    <main className={styles.page} ref={pageRef}>
      <a className={styles.skipLink} href="#main-content">
        Skip to main content
      </a>

      <header className={styles.siteHeader}>
        <div className={styles.headerInner}>
          <Link className={styles.wordmark} href="/" aria-label="SIRA and SEIL home">
            <CombinedBrandLogo className={styles.combinedLogo} priority />
          </Link>

          <nav className={styles.primaryNav} aria-label="Primary navigation">
            <a href="#how-it-works">How it works</a>
            <a href="#trust">Trust</a>
            <a href="#connectors">Connectors</a>
            <Link href="/pricing">Pricing</Link>
          </nav>

          <div className={styles.signInGroup} aria-label="Sign in">
            <Link className={styles.signInLink} data-workspace="sira" href="/sira/sign-in">
              SIRA sign in
            </Link>
            <Link className={styles.signInLink} data-workspace="seil" href="/seil/sign-in">
              SEIL sign in
            </Link>
          </div>
        </div>
      </header>

      <div id="main-content">
        <section className={styles.hero} aria-labelledby="landing-title">
          <div className={styles.contentWidth}>
            <p className={styles.eyebrow}>Company-aware software decisions</p>
            <h1 id="landing-title" data-pretext>
              Product truth on one side. Company truth on the other.
            </h1>
            <p className={styles.heroCopy} data-pretext>
              SIRA helps a company choose, approve, execute, and verify the best
              supported action. SEIL helps a seller publish reusable Product Evidence
              and respond honestly when the fit is real.
            </p>
            <div className={styles.heroActions} aria-label="Choose a product">
              <Link className={styles.siraAction} href="/sira">
                Talk to SIRA <ArrowRight aria-hidden="true" />
              </Link>
              <Link className={styles.seilAction} href="/seil">
                Talk to SEIL <ArrowRight aria-hidden="true" />
              </Link>
            </div>
            <p className={styles.heroNote}>
              Separate products for different teams. Information crosses only when people choose to share it. Payment never buys rank.
            </p>
          </div>
        </section>

        <section className={styles.productDoors} aria-labelledby="product-doors-title">
          <div className={styles.contentWidth}>
            <div className={styles.sectionHeading}>
              <p>Choose your side</p>
              <h2 id="product-doors-title" data-pretext>
                Buying teams use SIRA. B2B sellers use SEIL.
              </h2>
            </div>

            <div className={styles.doorGrid}>
              <article className={`${styles.productDoor} ${styles.siraDoor}`}>
                <div className={styles.doorHeader}>
                  <Building2 aria-hidden="true" />
                  <span>For buying teams</span>
                </div>
                <h3>SIRA</h3>
                <p data-pretext>
                  Tell SIRA what your company needs, what you already use, and what
                  matters. It compares supported actions and keeps approvals explicit.
                </p>
                <ul>
                  {buyerOutcomes.map((outcome) => (
                    <li key={outcome}>
                      <Check aria-hidden="true" /> {outcome}
                    </li>
                  ))}
                </ul>
                <Link href="/sira">
                  Talk to SIRA <ArrowRight aria-hidden="true" />
                </Link>
              </article>

              <article className={`${styles.productDoor} ${styles.seilDoor}`}>
                <div className={styles.doorHeader}>
                  <PackageCheck aria-hidden="true" />
                  <span>For product teams</span>
                </div>
                <h3>SEIL</h3>
                <p data-pretext>
                  Give SEIL your product sources, fit rules, and constraints. It turns
                  reviewed facts into reusable Product Evidence for B2B buyers.
                </p>
                <ul>
                  {sellerOutcomes.map((outcome) => (
                    <li key={outcome}>
                      <Check aria-hidden="true" /> {outcome}
                    </li>
                  ))}
                </ul>
                <Link href="/seil">
                  Talk to SEIL <ArrowRight aria-hidden="true" />
                </Link>
              </article>
            </div>
          </div>
        </section>

        <section className={styles.flowSection} id="how-it-works" aria-labelledby="flow-title">
          <div className={styles.contentWidth}>
            <div className={styles.sectionHeading}>
              <p>How the exchange works</p>
              <h2 id="flow-title" data-pretext>
                Structured records cross the boundary. Private memory does not.
              </h2>
            </div>

            <ol className={styles.flowList}>
              <li>
                <span>01</span>
                <div>
                  <strong>Buyer context stays private</strong>
                  <p>SIRA turns confirmed company facts into a versioned Purchase Brief.</p>
                </div>
              </li>
              <li>
                <span>02</span>
                <div>
                  <strong>Seller knowledge is reviewed</strong>
                  <p>SEIL publishes only allowlisted claims from the Private Product Passport.</p>
                </div>
              </li>
              <li>
                <span>03</span>
                <div>
                  <strong>Evidence meets requirements</strong>
                  <p>SIRA evaluates seller-published evidence against the buyer&apos;s company rules.</p>
                </div>
              </li>
              <li>
                <span>04</span>
                <div>
                  <strong>Humans keep authority</strong>
                  <p>Disclosure, plan approval, payment, fulfillment, and verification remain separate.</p>
                </div>
              </li>
            </ol>
          </div>
        </section>

        <section className={styles.trustSection} id="trust" aria-labelledby="trust-title">
          <div className={styles.contentWidth}>
            <div className={styles.trustIntro}>
              <p className={styles.eyebrow}>The boundary is part of the product</p>
              <h2 id="trust-title" data-pretext>
                Share only what the other side needs to decide.
              </h2>
              <p data-pretext>
                A sanitized Requirement Brief can cross from SIRA to SEIL. Reviewed
                Product Evidence, an attributable pass, or a structured offer can come
                back. Identity and contact stay hidden until both sides consent to the
                exact scope.
              </p>
            </div>

            <div className={styles.boundaryTable}>
              <div>
                <LockKeyhole aria-hidden="true" />
                <h3>Buyer-private</h3>
                <p>Company facts, budgets, internal strategy, competing offers, and private failures.</p>
              </div>
              <div>
                <FileSearch aria-hidden="true" />
                <h3>Shared for evaluation</h3>
                <p>Sanitized requirements, reviewed claims, fit rules, evidence, plans, and labelled positioning.</p>
              </div>
              <div>
                <ShieldCheck aria-hidden="true" />
                <h3>Seller-private</h3>
                <p>Roadmap, capacity, negotiation limits, commercial rules, and unpublished constraints.</p>
              </div>
            </div>
          </div>
        </section>

        <section className={styles.outcomeSection} aria-labelledby="outcome-title">
          <div className={styles.contentWidth}>
            <div className={styles.outcomeHeader}>
              <BadgeCheck aria-hidden="true" />
              <div>
                <p>What good looks like</p>
                <h2 id="outcome-title" data-pretext>
                  A supported action, with the evidence and proof to defend it.
                </h2>
              </div>
            </div>
            <dl className={styles.outcomeRows}>
              <div>
                <dt>Decision</dt>
                <dd>Best supported action among evaluated options, plus what could change it.</dd>
              </div>
              <div>
                <dt>Authority</dt>
                <dd>Exact policy, budget, cardholder, and execution responsibility.</dd>
              </div>
              <div>
                <dt>Result</dt>
                <dd>Verified artifacts, separate payment and fulfillment state, and the Company-stack consequence.</dd>
              </div>
            </dl>
          </div>
        </section>

        <section className={styles.connectorSection} id="connectors" aria-labelledby="connector-title">
          <div className={styles.contentWidth}>
            <div className={styles.connectorHeading}>
              <PlugZap aria-hidden="true" />
              <div>
                <p>Connectors</p>
                <h2 id="connector-title" data-pretext>
                  Current evidence and controlled execution, without hidden credentials.
                </h2>
              </div>
            </div>
            <ul className={styles.connectorList}>
              <li><strong>Senso</strong><span>Scoped evidence ingestion, citations, freshness, and source health.</span></li>
              <li><strong>Prava hosted authorization</strong><span>Cardholder handoff and backend reconciliation; credentials never enter the browser.</span></li>
              <li><strong>Merchant and fulfillment</strong><span>Order, entitlement, provisioning, cancellation, and refund as separate states.</span></li>
              <li><strong>Company discovery</strong><span>Identity, contracts, inventory, usage, and security sources with a manual path.</span></li>
              <li><strong>Slack and Teams</strong><span>Safe summaries and authenticated deep links, never hidden context.</span></li>
            </ul>
          </div>
        </section>

        <section className={styles.assuranceSection} aria-label="Security and pricing">
          <div className={styles.contentWidth}>
            <div className={styles.assuranceGrid}>
              <article>
                <ShieldCheck aria-hidden="true" />
                <p>Security and control</p>
                <h2 data-pretext>Private records never become marketplace inventory.</h2>
                <span>
                  Role-filtered projections keep unauthorized facts, controls, counts,
                  and notifications out of the payload and DOM.
                </span>
                <Link href="/security">Read the trust model <ArrowRight aria-hidden="true" /></Link>
              </article>
              <article>
                <ReceiptText aria-hidden="true" />
                <p>Pricing principle</p>
                <h2 data-pretext>Useful before a transaction ever happens.</h2>
                <span>
                  Start with a stack audit, comparison, procurement brief, or Product
                  Evidence compiler. Seller payment and positioning never influence rank.
                </span>
                <Link href="/pricing">See product pricing <ArrowRight aria-hidden="true" /></Link>
              </article>
            </div>
          </div>
        </section>
      </div>

      <footer className={styles.footer}>
        <div className={styles.footerInner}>
          <div>
            <Link className={styles.footerWordmark} href="/" aria-label="SIRA and SEIL home">
              <CombinedBrandLogo className={styles.footerLogo} />
            </Link>
            <p>Company-aware decisions and reusable product truth.</p>
          </div>
          <nav aria-label="Footer navigation">
            <Link href="/security">Security</Link>
            <Link href="/pricing">Pricing</Link>
            <Link href="/privacy">Privacy</Link>
            <Link href="/terms">Terms</Link>
          </nav>
          <small>Seilnsara</small>
        </div>
      </footer>
    </main>
  );
}
