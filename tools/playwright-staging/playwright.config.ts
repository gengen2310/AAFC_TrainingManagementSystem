import { defineConfig, devices } from "@playwright/test";

const STAGING_URL =
  process.env.STAGING_URL ??
  "https://aafc-tms-frontend-staging.up.railway.app";
const STAGING_API =
  process.env.STAGING_API ??
  "https://aafc-tms-backend-staging.up.railway.app";

export default defineConfig({
  testDir: "./tests",
  timeout: 45_000,
  retries: 1,
  workers: 1,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    baseURL: STAGING_URL,
    screenshot: "on",
    video: "off",
    trace: "on-first-retry",
    extraHTTPHeaders: { "x-test-run": "staging-verification-e548875" },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"] },
    },
    {
      name: "mobile",
      use: { ...devices["Pixel 7"] },
    },
  ],
  outputDir: "test-results",
});

export { STAGING_URL, STAGING_API };
