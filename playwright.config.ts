import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/browser",
  outputDir: ".artifacts/playwright/results",
  reporter: [["line"], ["html", { outputFolder: ".artifacts/playwright/report", open: "never" }]],
  timeout: 30_000,
  expect: { timeout: 7_500 },
  fullyParallel: false,
  workers: process.env.CI ? 2 : 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: process.env.SIRA_WEB_URL ?? "http://127.0.0.1:3000",
    channel: process.env.CI ? undefined : "chrome",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: "pnpm dev:web",
    url: process.env.SIRA_WEB_URL ?? "http://127.0.0.1:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      NEXT_PUBLIC_WEB_DATA_MODE: "fixture",
      NEXT_PUBLIC_GUEST_SESSION_ENABLED: "true",
    },
  },
  projects: [
    { name: "desktop-chrome", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile-chrome", use: { ...devices["Pixel 7"] } },
  ],
});
