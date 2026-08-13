"use client";

import type { WorkspaceSettingsUpdate, WorkspaceSettingsView } from "@sira/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

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

import {
  WEB_DATA_MODE,
  buyerDevelopmentHeaders,
  createIdempotencyKey,
  getBrowserApiClient,
  sellerEditorDevelopmentHeaders,
} from "@/lib/api";

import { WORKSPACE_ACCOUNTS, type ProfileWorkspace } from "./workspace-account";
import styles from "./profile-preview.module.css";

type SettingsSection = "profile" | "general" | "notifications" | "privacy";

const DEFAULT_SETTINGS: WorkspaceSettingsUpdate = {
  notification_channels: { in_app: true, email: false },
  quiet_hours: { enabled: false, start: "22:00", end: "07:00", timezone: "Asia/Kolkata" },
  disclosure_defaults: {
    allow_anonymized_requirement_preview: true,
    share_organization_name_after_consent: false,
    allow_outcome_follow_up: true,
  },
  change_reason: "Update workspace notification and disclosure preferences.",
};

function editableSettings(value: WorkspaceSettingsView): WorkspaceSettingsUpdate {
  return {
    notification_channels: value.notification_channels,
    quiet_hours: value.quiet_hours,
    disclosure_defaults: value.disclosure_defaults,
    change_reason: "Update workspace notification and disclosure preferences.",
  };
}

function ToggleRow({
  checked,
  disabled,
  label,
  note,
  onChange,
}: {
  checked: boolean;
  disabled?: boolean;
  label: string;
  note: string;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className={styles.toggleRow}>
      <span>
        <strong>{label}</strong>
        <small>{note}</small>
      </span>
      <input
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        type="checkbox"
      />
    </label>
  );
}

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

export function ProfileSettingsModal({
  workspace,
  onClose,
  identity,
  onSignOut,
  onUpgradeGuest,
}: {
  workspace: ProfileWorkspace;
  onClose?: () => void;
  identity?: { displayName: string | null; email: string | null; isAnonymous: boolean };
  onSignOut?: () => Promise<void>;
  onUpgradeGuest?: () => Promise<unknown>;
}) {
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const navRef = useRef<HTMLElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const paneHeadingRef = useRef<HTMLHeadingElement>(null);
  const router = useRouter();
  const [activeSection, setActiveSection] = useState<SettingsSection>("profile");
  const [mobilePane, setMobilePane] = useState<"menu" | "detail">("menu");
  const [settingsOverride, setSettingsOverride] = useState<WorkspaceSettingsUpdate | null>(null);
  const queryClient = useQueryClient();
  const settingsHeaders =
    workspace === "sira" ? buyerDevelopmentHeaders : sellerEditorDevelopmentHeaders;
  const settingsQuery = useQuery({
    queryKey: ["workspace-settings", workspace, WEB_DATA_MODE],
    enabled: WEB_DATA_MODE === "api",
    queryFn: () =>
      getBrowserApiClient().request("qualification_get_workspace_settings", {
        headers: settingsHeaders,
      }),
  });
  const settingsMutation = useMutation({
    mutationFn: (body: WorkspaceSettingsUpdate) => {
      if (!settingsQuery.data) throw new Error("Reload current settings before saving.");
      return getBrowserApiClient().request("qualification_update_workspace_settings", {
        headers: { ...settingsHeaders, "If-Match": settingsQuery.data.etag },
        idempotencyKey: createIdempotencyKey(`${workspace}-settings`),
        body,
      });
    },
    onSuccess: () => {
      setSettingsOverride(null);
      return queryClient.invalidateQueries({ queryKey: ["workspace-settings", workspace] });
    },
  });
  const guest = identity?.isAnonymous ?? false;
  const fallbackAccount = WORKSPACE_ACCOUNTS[workspace];
  const verifiedName = identity?.displayName || identity?.email || "Verified account";
  const account = guest
    ? {
        boundary:
          "This browser has a private, isolated workspace. Protected purchasing actions require a verified account.",
        email: "Not connected",
        initials: "G",
        name: "Private guest",
        organization: "Guest workspace",
        role: `${workspace.toUpperCase()} guest operator`,
        roleShort: "Isolated session",
        scope: `${workspace.toUpperCase()} guest workspace`,
      }
    : identity
      ? {
          ...fallbackAccount,
          boundary:
            "Firebase verifies this account. Workspace and purchasing permissions are derived by the server.",
          email: identity.email || "Google account",
          initials: verifiedName.trim().slice(0, 1).toUpperCase() || "U",
          name: verifiedName,
          organization: "Private account workspace",
          role: `${workspace.toUpperCase()} verified operator`,
          roleShort: "Verified identity",
          scope: `${workspace.toUpperCase()} account workspace`,
        }
      : fallbackAccount;
  const workspaceName = workspace.toUpperCase();
  const section = SECTION_COPY[activeSection];
  const noticeId = `${workspace}-settings-preview-notice`;
  const titleId = `${workspace}-settings-title`;
  const draftSettings =
    settingsOverride ??
    (settingsQuery.data ? editableSettings(settingsQuery.data) : DEFAULT_SETTINGS);

  function updateDraftSettings(
    update: (current: WorkspaceSettingsUpdate) => WorkspaceSettingsUpdate,
  ) {
    setSettingsOverride((current) =>
      update(
        current ?? (settingsQuery.data ? editableSettings(settingsQuery.data) : DEFAULT_SETTINGS),
      ),
    );
  }

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
          <aside
            className={styles.settingsMenu}
            aria-label={`${workspaceName} settings navigation`}
          >
            <div className={styles.menuHeader}>
              <button
                autoFocus
                className={styles.closeButton}
                ref={closeButtonRef}
                type="button"
                aria-label="Close settings"
                onClick={dismiss}
              >
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
                <div>
                  <strong>{account.name}</strong>
                  <small>{account.roleShort}</small>
                </div>
              </div>
            </div>
          </aside>

          <section
            className={styles.settingsPane}
            aria-labelledby={`${workspace}-settings-section-title`}
          >
            <header className={styles.paneHeader}>
              <div className={styles.mobileActions}>
                <button className={styles.mobileBack} type="button" onClick={showMenu}>
                  <ChevronLeft aria-hidden="true" /> Settings
                </button>
                <button
                  className={styles.mobileClose}
                  type="button"
                  aria-label="Close settings"
                  onClick={dismiss}
                >
                  <X aria-hidden="true" />
                </button>
              </div>
              <p>{workspaceName} account</p>
              <h2 id={`${workspace}-settings-section-title`} ref={paneHeadingRef} tabIndex={-1}>
                {section.title}
              </h2>
              <span>{section.description}</span>
            </header>

            <div className={styles.previewNotice} id={noticeId} role="status">
              <CircleAlert aria-hidden="true" />
              <span>
                <strong>{guest ? "Private guest session." : "Verified Firebase account."}</strong>{" "}
                {guest
                  ? "Your work is isolated to this browser. Protected purchasing actions require an account."
                  : "Your account is persistent; workspace roles remain server-controlled."}
              </span>
            </div>

            <div className={styles.paneBody}>
              {activeSection === "profile" ? (
                <>
                  <div className={styles.profileIdentity}>
                    <span aria-hidden="true">{account.initials}</span>
                    <div>
                      <strong>{account.name}</strong>
                      <small>{account.scope}</small>
                    </div>
                  </div>
                  <SettingRows
                    rows={[
                      { label: "Display name", value: account.name },
                      { label: "Work email", value: account.email },
                      { label: "Workspace role", value: account.role },
                      { label: "Organization", value: account.organization },
                    ]}
                  />
                </>
              ) : null}

              {activeSection === "general" ? (
                <SettingRows
                  rows={[
                    { label: "Language", value: "English" },
                    { label: "Region and time zone", value: "India · Asia/Kolkata" },
                    { label: "Appearance", value: "Light" },
                    { label: "Reduced motion", value: "Uses system preference" },
                    {
                      href: `/${workspace}/analytics`,
                      label: "Operations analytics",
                      value: "Open tenant-safe metrics",
                    },
                  ]}
                />
              ) : null}

              {activeSection === "notifications" ? (
                <div className={styles.preferencePanel}>
                  <ToggleRow
                    checked={draftSettings.notification_channels.in_app ?? true}
                    disabled
                    note="Keep durable assignments visible in your workspace inbox."
                    label="In-app inbox"
                    onChange={() => undefined}
                  />
                  <ToggleRow
                    checked={draftSettings.notification_channels.email ?? false}
                    note="Send assignment summaries when an email provider is configured."
                    label="Email assignments"
                    onChange={(email) =>
                      updateDraftSettings((current) => ({
                        ...current,
                        notification_channels: { ...current.notification_channels, email },
                      }))
                    }
                  />
                  <ToggleRow
                    checked={draftSettings.quiet_hours.enabled ?? false}
                    note={`${draftSettings.quiet_hours.start}–${draftSettings.quiet_hours.end} · ${draftSettings.quiet_hours.timezone}`}
                    label="Quiet hours"
                    onChange={(enabled) =>
                      updateDraftSettings((current) => ({
                        ...current,
                        quiet_hours: { ...current.quiet_hours, enabled },
                      }))
                    }
                  />
                  <Link className={styles.inlineLink} href={`/${workspace}/inbox`}>
                    Open current inbox
                  </Link>
                </div>
              ) : null}

              {activeSection === "privacy" ? (
                <>
                  <div className={styles.boundaryCallout}>
                    <ShieldCheck aria-hidden="true" />
                    <div>
                      <strong>Workspace boundary</strong>
                      <p>{account.boundary}</p>
                    </div>
                  </div>
                  <SettingRows
                    rows={[
                      { label: "Role preview", value: account.role },
                      {
                        label: "Identity verification",
                        value: guest ? "Anonymous Firebase user" : "Firebase verified",
                      },
                      { label: "Cross-product access", value: "Not available here" },
                    ]}
                  />
                  <div className={styles.preferencePanel}>
                    <ToggleRow
                      checked={
                        draftSettings.disclosure_defaults.allow_anonymized_requirement_preview ??
                        true
                      }
                      note="Let matched sellers see a minimum-disclosure requirement before identity exchange."
                      label="Anonymous requirement preview"
                      onChange={(value) =>
                        updateDraftSettings((current) => ({
                          ...current,
                          disclosure_defaults: {
                            ...current.disclosure_defaults,
                            allow_anonymized_requirement_preview: value,
                          },
                        }))
                      }
                    />
                    <ToggleRow
                      checked={
                        draftSettings.disclosure_defaults.share_organization_name_after_consent ??
                        false
                      }
                      note="Request organization-name sharing only after both parties approve the exact fields."
                      label="Organization name after consent"
                      onChange={(value) =>
                        updateDraftSettings((current) => ({
                          ...current,
                          disclosure_defaults: {
                            ...current.disclosure_defaults,
                            share_organization_name_after_consent: value,
                          },
                        }))
                      }
                    />
                    <ToggleRow
                      checked={draftSettings.disclosure_defaults.allow_outcome_follow_up ?? true}
                      note="Allow a post-purchase outcome request without exposing contacts."
                      label="Outcome follow-up"
                      onChange={(value) =>
                        updateDraftSettings((current) => ({
                          ...current,
                          disclosure_defaults: {
                            ...current.disclosure_defaults,
                            allow_outcome_follow_up: value,
                          },
                        }))
                      }
                    />
                    <p className={styles.consentNote}>
                      <ShieldCheck aria-hidden="true" /> These defaults never disclose contact data.
                      Every introduction still requires bilateral consent to the identical field
                      hash.
                    </p>
                  </div>
                </>
              ) : null}

              {activeSection === "notifications" || activeSection === "privacy" ? (
                <div className={styles.saveSettings}>
                  {WEB_DATA_MODE === "fixture" ? (
                    <p>Development fixture: preferences are preview-only.</p>
                  ) : null}
                  {settingsQuery.isPending && WEB_DATA_MODE === "api" ? (
                    <p>Loading current settings…</p>
                  ) : null}
                  {settingsQuery.isError ? (
                    <p role="alert">Current settings could not be loaded. Reload before saving.</p>
                  ) : null}
                  {settingsMutation.isError ? (
                    <p role="alert">
                      Settings changed elsewhere or could not be saved. Reload and try again.
                    </p>
                  ) : null}
                  {settingsMutation.isSuccess ? (
                    <p role="status">Saved as a new immutable settings version.</p>
                  ) : null}
                  <button
                    className={styles.accountAction}
                    disabled={
                      WEB_DATA_MODE !== "api" || !settingsQuery.data || settingsMutation.isPending
                    }
                    onClick={() => settingsMutation.mutate(draftSettings)}
                    type="button"
                  >
                    {settingsMutation.isPending ? "Saving…" : "Save preferences"}
                  </button>
                </div>
              ) : null}

              {guest && onUpgradeGuest ? (
                <button
                  className={styles.accountAction}
                  type="button"
                  onClick={() => void onUpgradeGuest()}
                >
                  Save this workspace with Google
                </button>
              ) : null}
              {onSignOut ? (
                <button
                  className={styles.accountActionSecondary}
                  type="button"
                  onClick={() => void onSignOut()}
                >
                  {guest ? "Leave guest workspace" : "Sign out"}
                </button>
              ) : null}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
