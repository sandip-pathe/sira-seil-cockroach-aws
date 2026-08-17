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
