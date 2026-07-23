import { defineConfig } from "@playwright/test";

// Connected-frontend (Main TMS) E2E config — targets the LIVE deployed staging
// service directly (not a local proxy), avoiding the CORS restriction that
// blocks localhost-origin requests to the staging backend. No webServer block:
// the app is already deployed.
export default defineConfig({
  testDir: "./e2e-connected",
  timeout: 30000,
  use: { baseURL: "https://aafc-tms-frontend-staging.up.railway.app", trace: "on-first-retry" },
});
