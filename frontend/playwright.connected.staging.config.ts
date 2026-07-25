import { defineConfig } from "@playwright/test";

// Connected-frontend (Main TMS) E2E config — targets the LIVE deployed staging
// service directly (not a local proxy), avoiding the CORS restriction that
// blocks localhost-origin requests to the staging backend. No webServer block:
// the app is already deployed.
//
// DEFECT-004: same reset-rate-limits wiring as playwright.staging.config.ts --
// see that file's comment. E2E_SYSADMIN_CODE must be supplied externally,
// never hardcoded here.
process.env.E2E_BACKEND_BASE_URL = process.env.E2E_BACKEND_BASE_URL || "https://aafc-tms-backend-staging.up.railway.app";

export default defineConfig({
  testDir: "./e2e-connected",
  timeout: 30000,
  globalSetup: "./playwright-global-setup.ts",
  use: { baseURL: "https://aafc-tms-frontend-staging.up.railway.app", trace: "on-first-retry" },
});
