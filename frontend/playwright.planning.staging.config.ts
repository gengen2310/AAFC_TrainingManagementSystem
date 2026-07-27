import { defineConfig } from "@playwright/test";

// Planning Workspace E2E config — targets the LIVE deployed staging service
// directly (aafc-tms-planning-workspace-preview-staging), not a local Vite
// dev server. Required for release-qualification screenshot evidence to
// reflect the actual deployed module-mode build, not local working-tree code
// (playwright.staging.config.ts's local-dev-server approach does not satisfy
// this — it serves the non-module "full app" build, which is not what's
// actually deployed).
process.env.E2E_BACKEND_BASE_URL = process.env.E2E_BACKEND_BASE_URL || "https://aafc-tms-backend-staging.up.railway.app";

export default defineConfig({
  testDir: "./e2e-connected",
  timeout: 30000,
  globalSetup: "./playwright-global-setup.ts",
  use: { baseURL: "https://aafc-tms-planning-workspace-preview-staging.up.railway.app", trace: "on-first-retry" },
});
