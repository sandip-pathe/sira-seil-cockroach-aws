import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const routes = [
  "/sira",
  "/sira/missions/demo-mission",
  "/seil/products/demo-product/evidence",
  "/seil/opportunities/demo-opportunity",
  "/matches/demo-match",
  "/integrity/demo-mission",
] as const;

async function assertPageContract(page: Page, route: string) {
  const response = await page.goto(route, { waitUntil: "domcontentloaded" });
  expect(response, `${route} should return an HTTP response`).not.toBeNull();
  expect(response?.status(), `${route} should not be a server error`).toBeLessThan(500);
  await expect(page.locator("body")).toBeVisible();
  await expect(page.getByLabel("Loading current marketplace state")).toHaveCount(0, {
    timeout: 15_000,
  });
  await expect(page.getByText("Loading the authorized Product Evidence view")).toHaveCount(0, {
    timeout: 15_000,
  });
  await expect(page.getByRole("heading").first()).toBeVisible();
  await expect(page.locator("main")).toHaveCount(1);
  await expect(page.locator("body")).not.toContainText("Application error");

  const horizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  );
  expect(horizontalOverflow, `${route} should not overflow the viewport`).toBe(false);

  const scan = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const restoredSiraContrast = route === "/sira"
    ? scan.violations.find((violation) => violation.id === "color-contrast")
    : undefined;
  if (restoredSiraContrast) {
    const maximumKnownNodes = (page.viewportSize()?.width ?? 1280) < 600 ? 8 : 24;
    expect(
      restoredSiraContrast.nodes.length,
      "the frozen SIRA contrast debt must not grow before the approved accessibility pass",
    ).toBeLessThanOrEqual(maximumKnownNodes);
  }
  const blockingViolations = scan.violations.filter(
    (violation) => !(route === "/sira" && violation.id === "color-contrast"),
  );
  expect(blockingViolations, `${route} has unbaselined WCAG A/AA violations`).toEqual([]);
}

for (const route of routes) {
  test(`${route} renders without critical accessibility or viewport failures`, async ({ page }) => {
    await assertPageContract(page, route);
  });
}

test("authentication setup state is keyboard reachable", async ({ page }) => {
  await page.goto("/sira", { waitUntil: "domcontentloaded" });
  const controls = page.locator(
    "a[href]:visible, button:visible, input:visible, textarea:visible, select:visible",
  );
  if ((await controls.count()) === 0) {
    await expect(
      page.getByRole("heading", { name: "Authentication setup required" }),
    ).toBeVisible();
    return;
  }
  await controls.first().focus();
  await expect(controls.first()).toBeFocused();
});

test("Firebase-disabled workspace presents a safe private guest account", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  await page.goto("/seil", { waitUntil: "domcontentloaded" });
  await expect(page.getByLabel("Loading current marketplace state")).toHaveCount(0, {
    timeout: 15_000,
  });
  await page.waitForTimeout(250);
  await expect(page.getByText("SEIL selling agent", { exact: true })).toBeVisible();
  await expect(page.getByText("Isolated guest workspace", { exact: true })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Direct SEIL" })).toBeVisible();

  const profile = page.getByRole("button", { name: "Open SEIL profile settings" });
  if ((await profile.count()) === 0) {
    await page.getByRole("button", { name: "Open sidebar" }).click();
  }
  await expect(profile).toContainText("Private guest");
  await expect(profile).toContainText("Isolated workspace");
  await profile.click();

  await expect(page.getByRole("dialog", { name: "SEIL settings" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Leave guest workspace" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Save this workspace with Google" })).toHaveCount(0);
  expect(browserErrors).toEqual([]);
});

test("mission next task comes from the saved task list and opens run details", async ({ page }) => {
  await page.route("**/v1/workspace/conversations**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([{
        id: "msn_00000000000000000000000000000001",
        mode: "seil",
        title: "Prepare CRM evidence",
        messages: [{ role: "assistant", content: "I found the evidence gap.", tool_calls: [], proposals: [] }],
        updated_at: "2026-10-21T12:00:00Z",
        mission: { id: "msn_00000000000000000000000000000001", mode: "seil", goal: "Prepare CRM evidence", state: "PAUSED", version: 3, plan: [], stop_reason: null },
        events: [],
        artifacts: [],
        open_tasks: [{ id: "task_1", kind: "human_review", title: "Confirm CRM sync is enabled in this plan", status: "WAITING", owner_type: "HUMAN", assigned_role: "seller_editor" }],
      }]),
    });
  });

  await page.goto("/seil", { waitUntil: "domcontentloaded" });
  const nextTask = page.getByRole("button", {
    name: "Inspect next open task: Confirm CRM sync is enabled in this plan",
  });
  await expect(nextTask).toContainText("You or your team · Waiting");
  await expect(page.getByText("Version 3 · PAUSED", { exact: true })).toBeVisible();
  await nextTask.focus();
  await expect(nextTask).toBeFocused();
  await nextTask.press("Enter");
  const inspector = page.getByLabel("Object inspector");
  await expect(inspector.getByRole("heading", { name: "Work and authority" })).toBeVisible();
  await expect(inspector.getByText("Confirm CRM sync is enabled in this plan", { exact: true })).toBeVisible();
});

test("seller evidence search keeps authority and missing pricing explicit", async ({ page }) => {
  await page.route("**/v1/seller/products/search**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        results: [{
          id: "product_evidence_1",
          name: "Northstar Notes",
          public_summary: "Source-linked meeting notes for distributed teams.",
          publisher_authority: "EXTERNAL_UNSEALED",
          state: "IN_REVIEW",
          category: "Meeting intelligence",
          href: "/seller/products/product_evidence_1/evidence",
        }],
      }),
    });
  });

  await page.goto("/seil", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Open inspector" }).click();
  const inspector = page.getByLabel("Object inspector");
  await expect(inspector.getByRole("heading", { name: /1 registered/ })).toBeVisible();
  await inspector.getByRole("button", { name: /Northstar Notes/ }).click();
  await expect(inspector.getByText("External source · unverified", { exact: true })).toBeVisible();
  await expect(inspector.getByText(/External source · unverified · In Review/)).toBeVisible();
  await expect(inspector.getByText("Not provided", { exact: true })).toBeVisible();
  await expect(inspector.getByText("Evidence packet", { exact: true })).toHaveCount(0);
});

test("seller evidence retry reuses one idempotency key and expected version", async ({ page }) => {
  const keys: string[] = [];
  const versions: number[] = [];
  const exchangeRequests: string[] = [];
  let publishes = 0;
  await page.addInitScript(() => {
    const windowWithEvents = window as typeof window & { __siraEvents?: unknown[] };
    windowWithEvents.__siraEvents = [];
    window.addEventListener("sira:instrumentation", (event) => {
      windowWithEvents.__siraEvents?.push((event as CustomEvent).detail);
    });
  });
  page.on("request", (request) => {
    if (request.url().includes("exchange")) exchangeRequests.push(`${request.method()} ${request.url()}`);
  });
  await page.route("**/v1/exchange-cases/**", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          case_id: "demo-case",
          party: "SELLER",
          projection_hash: "a".repeat(64),
          released: {},
          state: publishes > 1 ? "EVIDENCE_RELEASED" : "REQUIREMENT_RELEASED",
          version: publishes > 1 ? 5 : 4,
        }),
      });
      return;
    }
    const headers = route.request().headers();
    keys.push(headers["idempotency-key"] ?? "missing");
    const body = route.request().postDataJSON() as { expected_version: number };
    versions.push(body.expected_version);
    publishes += 1;
    if (publishes === 1) {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Unavailable" }) });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        case_id: "demo-case",
        party: "SELLER",
        projection_hash: "b".repeat(64),
        released: {},
        state: "EVIDENCE_RELEASED",
        version: 5,
      }),
    });
  });

  await page.goto(`/exchange/demo-case?route=${"a".repeat(64)}&mode=seil`, { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Publish current evidence" }).click();
  const retry = page.getByRole("button", { name: "Retry evidence submission" });
  await expect(retry).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "No buyer-safe published evidence is available yet." })).toBeVisible();
  await retry.click();
  await expect.poll(() => keys.length, { message: exchangeRequests.join("\n") || "No exchange requests observed" }).toBe(2);
  await expect(page.getByRole("status").filter({ hasText: "Evidence was submitted. Refreshing the exchange version." })).toBeVisible();
  expect(keys).toHaveLength(2);
  expect(keys[0]).not.toBe("missing");
  expect(keys[1]).toBe(keys[0]);
  expect(versions).toEqual([4, 4]);
  const productEvents = await page.evaluate(() =>
    ((window as typeof window & { __siraEvents?: Array<Record<string, unknown>> }).__siraEvents ?? [])
      .filter((event) => event.layer === "ui_intent" || event.layer === "server_effect"),
  );
  expect(productEvents.map((event) => event.layer)).toEqual(["ui_intent", "ui_intent", "server_effect"]);
  expect(productEvents.every((event) => Object.keys(event).every((key) =>
    ["schema_version", "layer", "name", "surface", "confirmation", "occurred_at"].includes(key),
  ))).toBe(true);
  expect(productEvents.some((event) => event.layer === "external_outcome")).toBe(false);
});

test("mission skip link reaches the focused chat at narrow and 200% effective widths", async ({ page }) => {
  await page.setViewportSize({ width: 640, height: 900 });
  await page.goto("/seil", { waitUntil: "domcontentloaded" });

  const skipLink = page.getByRole("link", { name: "Skip to mission" });
  await page.keyboard.press("Tab");
  await expect(skipLink).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#chat-thread")).toBeFocused();

  await page.emulateMedia({ reducedMotion: "reduce" });
  const transitionDuration = await page.locator("[data-mode]").evaluate(
    (element) => Number.parseFloat(getComputedStyle(element).transitionDuration),
  );
  expect(transitionDuration).toBeLessThan(0.001);

  await page.setViewportSize({ width: 320, height: 800 });
  const hasHorizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  );
  expect(hasHorizontalOverflow).toBe(false);

});

test("Product Evidence tabs support arrow navigation and submission dialog returns focus", async ({ page }) => {
  await page.route("**/v1/seller/products/a11y-product/view", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        activity_metrics: { answer_rendered_count: 0, measurement_label: "OBSERVATIONAL_NOT_CAUSAL", observed_self_service_count: 0, seller_handoff_requested_count: 0, window_end: "2026-10-21T00:00:00Z", window_start: "2026-10-20T00:00:00Z" },
        actor: { capabilities: ["SUBMIT_REVIEW"], role: "SELLER_EDITOR" },
        available_actions: [{ href: "/v1/seller/pack-drafts/a11y-draft/submit-review", id: "SUBMIT_REVIEW", label: "Submit for review", method: "POST" }],
        pack_health: { complete_claim_count: 1, conflict_count: 0, required_claim_count: 2, stale_claim_count: 0, status: "NEEDS_ATTENTION" },
        product: { current_version: 1, href: "/seil/product-evidence/a11y-product", id: "a11y-product", name: "Accessibility Test Product", seller_state: "SELLER_DRAFT" },
        publisher_authority: { label: "Seller confirmed", supporting_copy: "Authority and verification are separate.", value: "SELLER_SEALED" },
        reusable_answers: { formats: [], published_answer_count: 0 },
        review: null,
        validation: { gaps: [], status: "VALID" },
        version_links: { current: "/current", previous: "/previous" },
      }),
    });
  });
  await page.route("**/v1/seller/pack-drafts/a11y-draft", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        anti_fit_rules: [],
        claims: [],
        fit_rules: [],
        id: "a11y-draft",
        product_id: "a11y-product",
        publisher_authority: "SELLER_SEALED",
        revision: 2,
        revision_hash: "sha256:reviewable-revision",
        state: "SELLER_DRAFT",
        updated_at: "2026-10-21T00:00:00Z",
        validation: { gaps: [], status: "VALID" },
      }),
    });
  });

  await page.goto("/seil/product-evidence/a11y-product", { waitUntil: "domcontentloaded" });
  const skipLink = page.getByRole("link", { name: "Skip to main content" });
  await page.keyboard.press("Tab");
  await expect(skipLink).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#seller-main")).toBeFocused();
  await expect(page.getByRole("heading", { name: "Draft in progress" })).toBeVisible();
  await expect(page.getByText("Needs Attention", { exact: true })).toBeVisible();
  const packTab = page.getByRole("tab", { name: "Pack" });
  const evidenceTab = page.getByRole("tab", { name: "Evidence" });
  await packTab.focus();
  await packTab.press("ArrowRight");
  await expect(evidenceTab).toBeFocused();
  await expect(evidenceTab).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tabpanel").getByRole("heading", { name: "Freshness and conflicts" })).toBeVisible();

  await evidenceTab.press("ArrowRight");
  await page.getByRole("tab", { name: "Fit" }).press("ArrowRight");
  await page.getByRole("tab", { name: "Publish" }).press("Enter");
  const submit = page.getByRole("button", { name: "Submit for review" });
  await expect(submit).toBeVisible();
  await submit.click();

  const dialog = page.getByRole("alertdialog", { name: "Submit revision 2 for review?" });
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(submit).toBeFocused();
});
