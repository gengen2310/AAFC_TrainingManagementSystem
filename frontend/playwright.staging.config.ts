import { defineConfig } from "@playwright/test";

// Staging E2E config: runs the Vite dev server proxied to the staging backend.
// Tests execute the rc3 frontend code against staging data to verify the
// deployed environment. All 35 E2E specs from ./e2e/ are included.
//
// DEFECT-004: reset-rate-limits' backend is staging, not localhost:8000 --
// set explicitly for playwright-global-setup.ts. E2E_SYSADMIN_CODE (the
// staging system_admin access code) must be supplied by whoever runs this
// config; it is never hardcoded here (see CLAUDE.md -- staging credentials
// are managed separately and must not be reset/altered/embedded).
process.env.E2E_BACKEND_BASE_URL = process.env.E2E_BACKEND_BASE_URL || "https://aafc-tms-backend-staging.up.railway.app";

export default defineConfig({
  testDir: "./e2e",
  timeout: 45000,
  globalSetup: "./playwright-global-setup.ts",
  use: { baseURL: "http://localhost:5173", trace: "on-first-retry" },
  webServer: {
    command: "VITE_API_BASE_URL=https://aafc-tms-backend-staging.up.railway.app npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: false,
    timeout: 90000,
  },
});
