import { defineConfig } from "@playwright/test";

// Planning Workspace NATIVE E2E config — runs ./e2e/ (the standalone
// Planning-Workspace-login-form suite, not the connected-frontend handoff
// suite in ./e2e-connected/) directly against the DEPLOYED staging preview
// service (aafc-tms-planning-workspace-preview-staging), for release-grade
// verification that the actual built/deployed static assets work, not just
// local working-tree code served by Vite dev. Unlike
// playwright.planning.staging.config.ts (which targets ./e2e-connected and
// the connected-frontend cross-origin cookie handoff flow, since the
// preview service is deployed in module mode / no visible login form), this
// config's own tests must authenticate via a direct API login
// (page.request.post("/api/auth/login")) rather than the on-page login
// form, since module mode hides that form when no session cookie is
// present -- matching the pattern already used in
// e2e/mission-backlog-classes.spec.ts.
process.env.E2E_BACKEND_BASE_URL = process.env.E2E_BACKEND_BASE_URL || "https://aafc-tms-backend-staging.up.railway.app";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  globalSetup: "./playwright-global-setup.ts",
  use: { baseURL: "https://aafc-tms-planning-workspace-preview-staging.up.railway.app", trace: "on-first-retry" },
});
