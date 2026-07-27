import { defineConfig } from "@playwright/test";

// Connected-frontend (Main TMS) E2E config — targets the static single-file SPA,
// not the React Planning Workspace. Backend must already be running/seeded on :8000
// (this config does not start it). API base is overridden per-test via addInitScript,
// never by editing connected-frontend/index.html's own meta tag.
process.env.CONNECTED_LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE || "http://localhost:8000";

export default defineConfig({
  testDir: "./e2e-connected",
  timeout: 30000,
  globalSetup: "./playwright-global-setup.ts",
  use: { baseURL: "http://localhost:8080", trace: "on-first-retry" },
  webServer: {
    command: "python3 -m http.server 8080 --directory ../connected-frontend",
    url: "http://localhost:8080",
    reuseExistingServer: true,
    timeout: 30000,
  },
});
