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
  await expect(page.locator("h1").first()).toBeVisible();
  await expect(page.locator("main")).toHaveCount(1);
  await expect(page.locator("body")).not.toContainText("Application error");

  const horizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  );
  expect(horizontalOverflow, `${route} should not overflow the viewport`).toBe(false);

  const scan = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(scan.violations, `${route} has WCAG A/AA violations`).toEqual([]);
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
