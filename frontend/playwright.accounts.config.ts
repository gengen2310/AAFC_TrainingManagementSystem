import { defineConfig, devices } from "@playwright/test";

// Year-bar config. Deliberately NOT port 8080 and NOT reuseExistingServer:
// another static server is often already on 8080 serving a different checkout,
// and reusing it silently tests the wrong file.
process.env.CONNECTED_LOCAL_API_BASE =
  process.env.CONNECTED_LOCAL_API_BASE || "http://localhost:8010";

export default defineConfig({
  testDir: "./e2e-connected",
  // Without this the general 300 req/60s limiter returns 429 partway through
  // a repeated run and the login page renders with an empty wing list.
  globalSetup: "./playwright-global-setup.ts",
  testMatch: /account-management\.spec\.ts/,
  timeout: 30000,
  use: { baseURL: "http://localhost:8123", trace: "off" },
  webServer: {
    command: "python3 -m http.server 8123 --directory ../connected-frontend",
    url: "http://localhost:8123",
    reuseExistingServer: false,
    timeout: 30000,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
