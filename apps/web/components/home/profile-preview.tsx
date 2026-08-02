"use client";

import {
  Bell,
  ChevronLeft,
  CircleAlert,
  Languages,
  ShieldCheck,
  UserRound,
  X,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { WORKSPACE_ACCOUNTS, type ProfileWorkspace } from "./workspace-account";
import styles from "./profile-preview.module.css";

type SettingsSection = "profile" | "general" | "notifications" | "privacy";

const SETTINGS_ITEMS: ReadonlyArray<{
  icon: LucideIcon;
  id: SettingsSection;
  label: string;
}> = [
  { icon: UserRound, id: "profile", label: "Profile" },
  { icon: Languages, id: "general", label: "General" },
  { icon: Bell, id: "notifications", label: "Notifications" },
  { icon: ShieldCheck, id: "privacy", label: "Privacy & access" },
];

const SECTION_COPY: Record<SettingsSection, { description: string; title: string }> = {
  profile: {
    description: "Your identity inside this workspace.",
    title: "Profile",
  },
  general: {
    description: "Language, region, and display defaults.",
    title: "General",
  },
  notifications: {
    description: "Where assigned work and review requests appear.",
    title: "Notifications",
  },
  privacy: {
    description: "Workspace boundaries, role preview, and account access.",
    title: "Privacy & access",
  },
};

function SettingRows({
  rows,
}: {
  rows: ReadonlyArray<{ href?: string; label: string; value: string }>;
}) {
  return (
    <dl className={styles.settingRows}>
      {rows.map((row) => (
        <div key={row.label}>
          <dt>{row.label}</dt>
          <dd>{row.href ? <Link href={row.href}>{row.value}</Link> : row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function ProfileSettingsModal({ workspace, onClose }: { workspace: ProfileWorkspace; onClose?: () => void }) {
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const navRef = useRef<HTMLElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const paneHeadingRef = useRef<HTMLHeadingElement>(null);
  const router = useRouter();
  const [activeSection, setActiveSection] = useState<SettingsSection>("profile");
  const [mobilePane, setMobilePane] = useState<"menu" | "detail">("menu");
  const account = WORKSPACE_ACCOUNTS[workspace];
  const workspaceName = workspace.toUpperCase();
  const section = SECTION_COPY[activeSection];
  const noticeId = `${workspace}-settings-preview-notice`;
  const titleId = `${workspace}-settings-title`;

  useEffect(() => {
    const overlay = overlayRef.current;
    const background = overlay?.previousElementSibling as HTMLElement | null;
    const previousBodyOverflow = document.body.style.overflow;
    const previousAriaHidden = background ? background.getAttribute("aria-hidden") : null;
    const backgroundWasInert = background?.hasAttribute("inert") ?? false;

    document.body.style.overflow = "hidden";
    background?.setAttribute("aria-hidden", "true");
    background?.setAttribute("inert", "");
    closeButtonRef.current?.focus();

    return () => {
      document.body.style.overflow = previousBodyOverflow;
      if (background) {
        if (!backgroundWasInert) background.removeAttribute("inert");
        if (previousAriaHidden === null) background.removeAttribute("aria-hidden");
        else background.setAttribute("aria-hidden", previousAriaHidden);
      }
    };
  }, []);

  useEffect(() => {
    if (mobilePane !== "detail") return;
    const frame = window.requestAnimationFrame(() => paneHeadingRef.current?.focus());
    return () => window.cancelAnimationFrame(frame);
  }, [activeSection, mobilePane]);

  function dismiss() {
    if (onClose) onClose();
    else router.replace(`/${workspace}`, { scroll: false });
  }

  function handleDialogKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      dismiss();
      return;
    }
    if (event.key !== "Tab") return;

    const focusable = Array.from(
      event.currentTarget.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ),
    ).filter((element) => element.getClientRects().length > 0);
    if (!focusable.length) return;

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function selectSection(nextSection: SettingsSection) {
    setActiveSection(nextSection);
    setMobilePane("detail");
  }

  function showMenu() {
    setMobilePane("menu");
    window.requestAnimationFrame(() => {
      navRef.current?.querySelector<HTMLButtonElement>('[aria-current="page"]')?.focus();
    });
  }

  return (
    <div
      className={styles.overlay}
      onPointerDown={(event) => {
        if (event.target === event.currentTarget) dismiss();
      }}
      ref={overlayRef}
    >
      <div
        aria-describedby={noticeId}
        aria-labelledby={titleId}
        aria-modal="true"
        className={styles.dialog}
        data-mobile-pane={mobilePane}
        data-workspace={workspace}
        onKeyDown={handleDialogKeyDown}
        role="dialog"
      >
        <div className={styles.modalShell}>
        <aside className={styles.settingsMenu} aria-label={`${workspaceName} settings navigation`}>
          <div className={styles.menuHeader}>
            <button autoFocus className={styles.closeButton} ref={closeButtonRef} type="button" aria-label="Close settings" onClick={dismiss}>
              <X aria-hidden="true" />
            </button>
            <div>
              <strong id={titleId}>{workspaceName} settings</strong>
              <span>{account.scope}</span>
            </div>
          </div>

          <nav className={styles.settingsNav} ref={navRef}>
            {SETTINGS_ITEMS.map((item) => {
              const Icon = item.icon;
              const active = item.id === activeSection;
              return (
                <button
                  aria-current={active ? "page" : undefined}
                  key={item.id}
                  onClick={() => selectSection(item.id)}
                  type="button"
                >
                  <Icon aria-hidden="true" />
                  {item.label}
                </button>
              );
            })}
          </nav>

          <div className={styles.menuFooter}>
            <nav aria-label="Account information">
              <Link href="/security">Security</Link>
              <Link href="/privacy">Privacy</Link>
              <Link href="/terms">Terms</Link>
            </nav>
            <div className={styles.accountSummary}>
              <span aria-hidden="true">{account.initials}</span>
              <div><strong>{account.name}</strong><small>{account.roleShort}</small></div>
            </div>
          </div>
        </aside>

        <section className={styles.settingsPane} aria-labelledby={`${workspace}-settings-section-title`}>
          <header className={styles.paneHeader}>
            <div className={styles.mobileActions}>
              <button className={styles.mobileBack} type="button" onClick={showMenu}>
                <ChevronLeft aria-hidden="true" /> Settings
              </button>
              <button className={styles.mobileClose} type="button" aria-label="Close settings" onClick={dismiss}>
                <X aria-hidden="true" />
              </button>
            </div>
            <p>{workspaceName} account</p>
            <h2 id={`${workspace}-settings-section-title`} ref={paneHeadingRef} tabIndex={-1}>{section.title}</h2>
            <span>{section.description}</span>
          </header>

          <div className={styles.previewNotice} id={noticeId} role="status">
            <CircleAlert aria-hidden="true" />
            <span><strong>Development preview.</strong> Settings are read-only. Changes are not saved, identity is not verified, and notification delivery is unchanged.</span>
          </div>

          <div className={styles.paneBody}>
            {activeSection === "profile" ? (
              <>
                <div className={styles.profileIdentity}>
                  <span aria-hidden="true">{account.initials}</span>
                  <div><strong>{account.name}</strong><small>{account.scope}</small></div>
                </div>
                <SettingRows rows={[
                  { label: "Display name", value: account.name },
                  { label: "Work email", value: account.email },
                  { label: "Workspace role", value: account.role },
                  { label: "Organization", value: account.organization },
                ]} />
              </>
            ) : null}

            {activeSection === "general" ? (
              <SettingRows rows={[
                { label: "Language", value: "English" },
                { label: "Region and time zone", value: "India · Asia/Kolkata" },
                { label: "Appearance", value: "Light" },
                { label: "Reduced motion", value: "Uses system preference" },
              ]} />
            ) : null}

            {activeSection === "notifications" ? (
              <SettingRows rows={[
                { href: `/${workspace}/inbox`, label: "In-app inbox", value: "Open inbox" },
                { label: "Email assignments", value: "Not connected" },
                { label: "Slack or Teams", value: "Not connected" },
                { label: "Quiet hours", value: "Not configured" },
              ]} />
            ) : null}

            {activeSection === "privacy" ? (
              <>
                <div className={styles.boundaryCallout}>
                  <ShieldCheck aria-hidden="true" />
                  <div><strong>Workspace boundary</strong><p>{account.boundary}</p></div>
                </div>
                <SettingRows rows={[
                  { label: "Role preview", value: account.role },
                  { label: "Identity verification", value: "Not connected" },
                  { label: "Cross-product access", value: "Not available here" },
                ]} />
              </>
            ) : null}

            <p className={styles.safetyNote}>Nothing on this screen changes account or workspace state.</p>
          </div>
        </section>
        </div>
      </div>
    </div>
  );
}
