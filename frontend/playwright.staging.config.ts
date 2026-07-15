import { defineConfig } from "@playwright/test";

// Staging E2E config: runs the Vite dev server proxied to the staging backend.
// Tests execute the rc3 frontend code against staging data to verify the
// deployed environment. All 35 E2E specs from ./e2e/ are included.
export default defineConfig({
  testDir: "./e2e",
  timeout: 45000,
  use: { baseURL: "http://localhost:5173", trace: "on-first-retry" },
  webServer: {
    command: "VITE_API_BASE_URL=https://aafc-tms-backend-staging.up.railway.app npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: false,
    timeout: 90000,
  },
});
