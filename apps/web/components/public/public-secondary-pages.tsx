"use client";

import {
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  Check,
  CircleDollarSign,
  CreditCard,
  FileBadge,
  Handshake,
  LockKeyhole,
  ReceiptText,
  Scale,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent, type ReactNode, type RefObject } from "react";
import { layout, prepare, type PreparedText } from "@chenglou/pretext";

import { CombinedBrandLogo } from "@/components/brand/combined-brand-logo";
import { useFirebaseAuth } from "@/components/auth/firebase-auth-provider";

import styles from "./public-secondary-pages.module.css";

type PreferredWorkspace = "sira" | "seil";

type PreparedElement = {
  element: HTMLElement;
  prepared: PreparedText;
  lineHeight: number;
};

function usePretextLayout(rootRef: RefObject<HTMLElement | null>, version: string) {
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
  }, [rootRef, version]);
}

function PublicHeader({ compact = false }: { compact?: boolean }) {
  return (
    <header className={styles.header} data-compact={compact || undefined}>
      <div className={styles.headerInner}>
        <Link className={styles.wordmark} href="/" aria-label="SIRA and SEIL home">
          <CombinedBrandLogo className={styles.combinedLogo} priority />
        </Link>
        <nav aria-label="Public navigation">
          <Link href="/pricing">Pricing</Link>
          <Link href="/security">Security</Link>
          <Link href="/privacy">Privacy</Link>
        </nav>
        <div className={styles.headerActions} aria-label="Sign in">
          <Link className={styles.headerAction} data-workspace="sira" href="/sira/sign-in">SIRA sign in</Link>
          <Link className={styles.headerAction} data-workspace="seil" href="/seil/sign-in">SEIL sign in</Link>
        </div>
      </div>
    </header>
  );
}

function PublicFooter() {
  return (
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
  );
}

function PageFrame({
  children,
  version,
}: {
  children: ReactNode;
  version: string;
}) {
  const pageRef = useRef<HTMLElement>(null);
  usePretextLayout(pageRef, version);

  return (
    <main className={styles.page} ref={pageRef}>
      <a className={styles.skipLink} href="#main-content">Skip to main content</a>
      <PublicHeader />
      <div id="main-content">{children}</div>
      <PublicFooter />
    </main>
  );
}

export function SignInPreview({
  preferredWorkspace,
}: {
  preferredWorkspace?: PreferredWorkspace;
}) {
  const router = useRouter();
  const auth = useFirebaseAuth();
  const workspace = preferredWorkspace ?? "sira";
  const workspaceName = workspace.toUpperCase();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState<"google" | "email" | "guest" | null>(null);
  const [error, setError] = useState<string | null>(null);

  function finish() {
    router.replace(`/${workspace}`);
  }

  async function run(kind: "google" | "email" | "guest", action: () => Promise<unknown>) {
    setBusy(kind);
    setError(null);
    try {
      await action();
      finish();
    } catch {
      setError(
        kind === "guest"
          ? "Could not create a private guest workspace. Please try again."
          : "Sign-in failed. Check your details or try another method.",
      );
    } finally {
      setBusy(null);
    }
  }

  function submitEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void run("email", () =>
      creating
        ? auth.createEmailAccount(email, password)
        : auth.signInWithEmail(email, password),
    );
  }

  return (
    <PageFrame version={`sign-in:${preferredWorkspace ?? "none"}`}>
      <section className={styles.signInSection} aria-labelledby="sign-in-title">
        <div className={styles.narrowWidth}>
          <div className={styles.signInIntro}>
            <Link className={styles.backLink} href="/">
              <ArrowLeft aria-hidden="true" /> Back to SIRA + SEIL
            </Link>
            <p className={styles.eyebrow}>Private {workspaceName} workspace</p>
            <h1 id="sign-in-title" data-pretext>Sign in and start working.</h1>
            <p data-pretext>
              Google and email accounts restore your work on any device. Guest access is
              instant, private to this browser, and cannot authorize purchases.
            </p>
          </div>

          <div className={styles.authCard}>
            {!auth.configured ? (
              <div className={styles.authError} role="alert">
                Firebase web credentials are missing from this build.
              </div>
            ) : null}

            <button
              className={styles.googleButton}
              disabled={!auth.configured || busy !== null}
              onClick={() => void run("google", auth.signInWithGoogle)}
              type="button"
            >
              <span aria-hidden="true">G</span>
              {busy === "google" ? "Opening Google…" : "Continue with Google"}
            </button>

            <div className={styles.authDivider}><span>or use email</span></div>

            <form className={styles.emailForm} onSubmit={submitEmail}>
              <label>
                <span>Email</span>
                <input
                  autoComplete="email"
                  disabled={!auth.configured || busy !== null}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                  type="email"
                  value={email}
                />
              </label>
              <label>
                <span>Password</span>
                <input
                  autoComplete={creating ? "new-password" : "current-password"}
                  disabled={!auth.configured || busy !== null}
                  minLength={8}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                  type="password"
                  value={password}
                />
              </label>
              <button disabled={!auth.configured || busy !== null} type="submit">
                {busy === "email"
                  ? "Please wait…"
                  : creating
                    ? "Create account"
                    : "Sign in with email"}
              </button>
            </form>

            <button
              className={styles.authModeButton}
              disabled={busy !== null}
              onClick={() => setCreating((current) => !current)}
              type="button"
            >
              {creating ? "Already have an account? Sign in" : "New here? Create an account"}
            </button>

            {error ? <p className={styles.authError} role="alert">{error}</p> : null}

            <div className={styles.guestChoice}>
              <div>
                <strong>Just exploring?</strong>
                <span>Get an isolated Firebase guest workspace without entering details.</span>
              </div>
              <button
                disabled={!auth.configured || busy !== null}
                onClick={() => void run("guest", auth.continueAsGuest)}
                type="button"
              >
                {busy === "guest" ? "Creating workspace…" : "Continue as guest"}
              </button>
            </div>
          </div>

          <p className={styles.authBoundary}>
            <LockKeyhole aria-hidden="true" /> Firebase verifies identity. SIRA derives
            workspace access server-side; the browser cannot choose an organization or role.
          </p>
        </div>
      </section>
    </PageFrame>
  );
}

const freeUtilities = [
  ["SIRA", "Stack audit, renewal scan, comparison, and procurement brief."],
  ["SEIL", "Product Evidence compiler, positioning review, and anti-fit diagnostics."],
] as const;

const paidPrinciples = [
  "Workspace pricing is published before paid activation.",
  "Any transaction fee is shown with the exact plan, currency, and amount before approval.",
  "Zero-charge actions omit checkout, payment states, transaction fees, and receipts.",
  "Seller subscription, positioning, and transaction participation never influence SIRA ranking.",
] as const;

export function PricingPage() {
  return (
    <PageFrame version="pricing">
      <section className={styles.pageHero} aria-labelledby="pricing-title">
        <div className={styles.contentWidth}>
          <p className={styles.eyebrow}>Pricing</p>
          <h1 id="pricing-title" data-pretext>Useful before a transaction ever happens.</h1>
          <p data-pretext>
            SIRA and SEIL start with free utility that creates better decision context
            and better product truth. Paid access supports governed team workflows,
            integrations, and controlled execution.
          </p>
        </div>
      </section>

      <section className={styles.rankPolicy} aria-labelledby="rank-policy-title">
        <div className={styles.contentWidth}>
          <Scale aria-hidden="true" />
          <div>
            <p>Commercial neutrality</p>
            <h2 id="rank-policy-title" data-pretext>Payment never buys rank.</h2>
            <span>
              SIRA can recommend reuse, configuration, cancellation, no action, or a
              product that pays nothing to Seilnsara. Seller payment and positioning
              stay outside eligibility, evidence, cost, risk, and ordering.
            </span>
          </div>
        </div>
      </section>

      <section className={styles.pricingSection} aria-labelledby="pricing-structure-title">
        <div className={styles.contentWidth}>
          <div className={styles.sectionHeading}>
            <p>Pricing structure</p>
            <h2 id="pricing-structure-title" data-pretext>
              Clear product access, then exact transaction terms only when needed.
            </h2>
          </div>

          <div className={styles.pricingColumns}>
            <article>
              <div className={styles.pricingTopline}>
                <BadgeCheck aria-hidden="true" />
                <span>Free utility</span>
              </div>
              <h3>Start with real work</h3>
              <p>No payment path is required to create the records that make either side useful.</p>
              <dl>
                {freeUtilities.map(([name, description]) => (
                  <div key={name}>
                    <dt>{name}</dt>
                    <dd>{description}</dd>
                  </div>
                ))}
              </dl>
            </article>

            <article>
              <div className={styles.pricingTopline}>
                <CircleDollarSign aria-hidden="true" />
                <span>Governed workspace</span>
              </div>
              <h3>Published before activation</h3>
              <p>
                Final package names and amounts are not invented in this implementation
                preview. Production pricing must show included roles, limits, connectors,
                billing cadence, and cancellation terms before commitment.
              </p>
              <div className={styles.pricingCtas}>
                <Link href="/sira/sign-in">SIRA sign in <ArrowRight aria-hidden="true" /></Link>
                <Link href="/seil/sign-in">SEIL sign in <ArrowRight aria-hidden="true" /></Link>
              </div>
            </article>
          </div>

          <div className={styles.pricingRules}>
            <div>
              <ReceiptText aria-hidden="true" />
              <h3>When money moves</h3>
            </div>
            <ul>
              {paidPrinciples.map((principle) => (
                <li key={principle}><Check aria-hidden="true" /> {principle}</li>
              ))}
            </ul>
          </div>
        </div>
      </section>
    </PageFrame>
  );
}

export function SecurityPage() {
  return (
    <PageFrame version="security">
      <section className={styles.pageHero} aria-labelledby="security-title">
        <div className={styles.contentWidth}>
          <p className={styles.eyebrow}>Security and trust</p>
          <h1 id="security-title" data-pretext>Every boundary stays visible.</h1>
          <p data-pretext>
            SIRA and SEIL separate private working memory, reviewed cross-boundary
            records, human authority, provider authorization, and verified outcomes.
            A convenient interface never collapses those controls into one success flag.
          </p>
        </div>
      </section>

      <section className={styles.securityPrinciples} aria-label="Security principles">
        <div className={styles.contentWidth}>
          <article>
            <LockKeyhole aria-hidden="true" />
            <h2>Private records stay private</h2>
            <p>
              Buyer Passport, Company Stack, Private Product Passport, hidden budgets,
              seller limits, and unpublished constraints never share a browser payload,
              cache, notification, or analytics event.
            </p>
          </article>
          <article>
            <FileBadge aria-hidden="true" />
            <h2>Publisher is not verifier</h2>
            <p>
              Published by vendor, Compiled by Seilnsara, and External not claimed state
              who stands behind a package. Publisher authority never implies every claim
              was independently verified or remains fresh.
            </p>
          </article>
          <article>
            <Handshake aria-hidden="true" />
            <h2>Consent is scoped</h2>
            <p>
              Mutual contact consent reveals only the displayed identity, fields,
              purpose, and expiry. It does not approve a plan, amount, payment,
              purchase, or execution.
            </p>
          </article>
        </div>
      </section>

      <section className={styles.controlSection} aria-labelledby="control-title">
        <div className={styles.contentWidth}>
          <div className={styles.sectionHeading}>
            <p>Independent controls</p>
            <h2 id="control-title" data-pretext>
              Recommendation, approval, external action, and outcome are different facts.
            </h2>
          </div>

          <ol className={styles.controlTimeline}>
            <li>
              <span>01</span>
              <div><strong>Select a plan</strong><p>The exact Decision version and plan hash are locked.</p></div>
            </li>
            <li>
              <span>02</span>
              <div><strong>Approve authority</strong><p>Policy and budget roles review the exact terms they control.</p></div>
            </li>
            <li>
              <span>03</span>
              <div><strong>Open the approved handoff</strong><p>An authorized user sees the recipient, amount, currency, reference, and expiry before leaving SIRA.</p></div>
            </li>
            <li>
              <span>04</span>
              <div><strong>Record the outcome</strong><p>An opened link is not proof of payment, deployment, or a successful outcome.</p></div>
            </li>
          </ol>
        </div>
      </section>

      <section className={styles.stateSeparation} aria-labelledby="state-separation-title">
        <div className={styles.contentWidth}>
          <div className={styles.stateIntro}>
            <CreditCard aria-hidden="true" />
            <div>
              <p>External action boundary</p>
              <h2 id="state-separation-title" data-pretext>SIRA never invents success outside its authority.</h2>
            </div>
          </div>
          <div className={styles.stateRows}>
            <div>
              <strong>Handoff opened</strong>
              <span>Record only that the approved destination was opened; wait for separate outcome evidence.</span>
            </div>
            <div>
              <strong>Outcome unknown</strong>
              <span>Do not infer payment or delivery from navigation, retries, or browser state.</span>
            </div>
            <div>
              <strong>Evidence received</strong>
              <span>Keep the external result, company-stack change, and measured outcome separate.</span>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.credentialSection} aria-labelledby="credential-title">
        <div className={styles.contentWidth}>
          <div>
            <ShieldCheck aria-hidden="true" />
            <p>Credential isolation</p>
            <h2 id="credential-title" data-pretext>Payment credentials stay outside SIRA.</h2>
          </div>
          <p data-pretext>
            They do not enter product models, browser payloads, persistence, logs,
            traces, Redis, workflow histories, analytics, or safe errors. The browser
            receives only an approved external destination and records that it was opened.
          </p>
        </div>
      </section>

      <section className={styles.roleSection} aria-labelledby="role-title">
        <div className={styles.contentWidth}>
          <div className={styles.sectionHeading}>
            <p>Role-filtered projections</p>
            <h2 id="role-title" data-pretext>Unauthorized data is absent, not blurred.</h2>
          </div>
          <p className={styles.roleCopy} data-pretext>
            Tenant, role, purpose, and object scope filter every fact, count, task,
            route, action, notification, and audit view before it reaches the browser.
            A selected organization or workspace never grants authority.
          </p>
          <Link className={styles.textLink} href="/privacy">
            Read the privacy implementation notice <ArrowRight aria-hidden="true" />
          </Link>
        </div>
      </section>
    </PageFrame>
  );
}

const legalContent = {
  privacy: {
    eyebrow: "Privacy implementation notice",
    title: "How product data is separated and used.",
    intro:
      "This concise placeholder describes the intended product boundaries while approved legal language is prepared. It is not a substitute for the final privacy notice.",
    sections: [
      ["Private workspace records", "Buyer and seller private records remain scoped to their authorized organization, role, purpose, and object."],
      ["Cross-boundary records", "Only reviewed, allowlisted Product Evidence and the exact sanitized Requirement Brief may cross between products."],
      ["Service providers", "Identity, evidence, external payment, and communication providers receive only the scope required for their operation."],
      ["Measurement", "Restricted screens exclude hidden buyer and seller context from analytics and disable session replay where required."],
      ["Retention and rights", "The approved notice must state region-specific retention, access, correction, deletion, export, objection, and contact procedures before production activation."],
    ],
  },
  terms: {
    eyebrow: "Terms implementation notice",
    title: "The service records evidence and authority; it does not invent either.",
    intro:
      "This concise placeholder describes the intended service boundaries while approved contractual terms are prepared. It is not a substitute for the final terms of service.",
    sections: [
      ["Account authority", "Users may act only for organizations, roles, products, and decisions the server authorizes. A UI selection never changes that authority."],
      ["Evidence and recommendations", "Product Evidence carries publisher authority, provenance, freshness, and uncertainty. SIRA reports the best supported action among evaluated options, not a guarantee."],
      ["Consent and transactions", "Contact consent, plan selection, policy approval, budget approval, external payment, deployment, and outcome remain separate acts."],
      ["Provider operations", "External payment providers retain their own operating terms. Opening a handoff does not prove payment or fulfillment."],
      ["Acceptable use and disputes", "The approved terms must define prohibited use, suspension, evidence disputes, appeals, liability, termination, governing law, and contact procedures before production activation."],
    ],
  },
} as const;

export function LegalPage({ kind }: { kind: "privacy" | "terms" }) {
  const content = legalContent[kind];

  return (
    <PageFrame version={`legal:${kind}`}>
      <section className={styles.legalHero} aria-labelledby="legal-title">
        <div className={styles.legalWidth}>
          <div className={styles.legalNotice} role="note">
            <TriangleAlert aria-hidden="true" />
            <div>
              <strong>Implementation placeholder</strong>
              <p>
                No effective legal version has been issued. Production activation must
                replace this page with approved text, an effective date, version history,
                and the required consent or notice flow.
              </p>
            </div>
          </div>
          <p className={styles.eyebrow}>{content.eyebrow}</p>
          <h1 id="legal-title" data-pretext>{content.title}</h1>
          <p data-pretext>{content.intro}</p>
          <dl className={styles.effectiveVersion}>
            <div><dt>Status</dt><dd>Draft implementation copy</dd></div>
            <div><dt>Effective version</dt><dd>Not yet issued</dd></div>
          </dl>
        </div>
      </section>

      <section className={styles.legalBody} aria-label={`${kind} topics`}>
        <div className={styles.legalWidth}>
          {content.sections.map(([title, body], index) => (
            <article key={title}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <div>
                <h2>{title}</h2>
                <p>{body}</p>
              </div>
            </article>
          ))}

          <div className={styles.legalSwitch}>
            <Scale aria-hidden="true" />
            <div>
              <strong>{kind === "privacy" ? "Looking for service terms?" : "Looking for the privacy notice?"}</strong>
              <Link href={kind === "privacy" ? "/terms" : "/privacy"}>
                Open {kind === "privacy" ? "Terms" : "Privacy"} <ArrowRight aria-hidden="true" />
              </Link>
            </div>
          </div>
        </div>
      </section>
    </PageFrame>
  );
}
