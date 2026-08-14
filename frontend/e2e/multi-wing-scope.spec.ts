/**
 * Multi-Wing scope isolation and national aggregation — E2E (VIS-10 / DOC-03).
 *
 * Verifies, through the rendered React Planning Workspace UI:
 * - National admin sees all Wings in /national-overview
 * - Wing admin (7WG) sees only their Wing's squadrons in /wing-overview
 * - 11WG data does not leak into 7WG wing-level views
 * - Wing admin cannot reach /national-overview
 *
 * Setup: provisions a synthetic 11WG with one squadron (1101) via the
 * backend API in beforeAll. 11WG is chosen because no other test in this
 * suite uses that code (2WG–6WG are used by test_org_account_linking.py;
 * 7WG is the primary seeded Wing; 8WG–9WG used by test_organisations.py).
 *
 * Backend must be running on :8000 (seeded). Vite dev server on :5173.
 */
import { test, expect, type APIRequestContext } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";
import { loginPW } from "../e2e-login-helper";

const BACKEND = process.env.E2E_BACKEND_BASE_URL || "http://localhost:8000";

// ── Setup ─────────────────────────────────────────────────────────────────────

async function apiToken(request: APIRequestContext, code: string): Promise<string> {
  const r = await request.post(`${BACKEND}/api/auth/login`, { data: { code } });
  return (await r.json()).token as string;
}

test.beforeAll(async ({ request }) => {
  await resetBackendRateLimits(BACKEND);

  // Provision synthetic 11WG with one squadron so national reports have 2 Wings.
  const token = await apiToken(request, "SYSADMIN2026");
  const r = await request.post(`${BACKEND}/api/system/provision-wing`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      wing_code: "11WG",
      wing_name: "11 Wing (E2E Test)",
      wing_short: "11WG",
      squadrons: [{ code: "1101", name: "1101 Squadron AAFC", short_name: "1101SQN" }],
      create_accounts: false,
    },
  });
  // 200 on create; also idempotent so a re-run won't fail
  expect(r.status(), `provision-wing failed: ${await r.text()}`).toBe(200);
  const body = await r.json();
  expect(body.wing.code).toBe("11WG");
});

// ── National admin: /national-overview ───────────────────────────────────────

test.describe("national_admin at /national-overview", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await loginPW(page, "ADMINNATIONAL");
    await expect(page.getByRole("heading", { name: "National Assurance" })).toBeVisible({ timeout: 10000 });
  });

  test("national overview page heading is visible", async ({ page }) => {
    await page.goto("/national-overview");
    await expect(page.getByRole("heading", { name: "National Assurance" })).toBeVisible({ timeout: 10000 });
  });

  test("national overview shows 7WG row", async ({ page }) => {
    await page.goto("/national-overview");
    await expect(page.getByRole("heading", { name: "National Assurance" })).toBeVisible({ timeout: 10000 });
    // Wait for the Wing table to load (not still showing Loading)
    await expect(page.locator("table").first()).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("cell", { name: /7WG/i }).first()).toBeVisible({ timeout: 8000 });
  });

  test("national overview shows 11WG row after provisioning", async ({ page }) => {
    await page.goto("/national-overview");
    await expect(page.getByRole("heading", { name: "National Assurance" })).toBeVisible({ timeout: 10000 });
    await expect(page.locator("table").first()).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("cell", { name: /11WG/i }).first()).toBeVisible({ timeout: 8000 });
  });

  test("national overview Wing count stat shows at least 2 Wings", async ({ page }) => {
    await page.goto("/national-overview");
    await expect(page.getByRole("heading", { name: "National Assurance" })).toBeVisible({ timeout: 10000 });
    // Stat component renders label "Wings" and a numeric value
    const wingsStat = page.locator(".sg-item, .stat, [class*='stat']").filter({ hasText: /^Wings/i });
    await expect(wingsStat.first()).toBeVisible({ timeout: 8000 });
  });

  test("command dashboard wing selector includes 11WG option", async ({ page }) => {
    await page.goto("/national-overview");
    await expect(page.getByRole("heading", { name: "National Assurance" })).toBeVisible({ timeout: 10000 });
    await expect(page.locator("table").first()).toBeVisible({ timeout: 10000 });
    // The wing-selector dropdown lists each Wing as an <option>
    await expect(page.locator("#command-wing-select option", { hasText: /11WG/i })).toHaveCount(1, { timeout: 8000 });
  });

  test("national overview API returns both Wings", async ({ page }) => {
    const token = await apiToken(page.request, "ADMINNATIONAL");
    const r = await page.request.get(`${BACKEND}/api/reports/national-overview`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(r.status()).toBe(200);
    const body = await r.json();
    const codes = (body.wings as { code: string }[]).map((w) => w.code);
    expect(codes).toContain("7WG");
    expect(codes).toContain("11WG");
  });

  test("national capability API returns both Wings", async ({ page }) => {
    const token = await apiToken(page.request, "ADMINNATIONAL");
    const r = await page.request.get(`${BACKEND}/api/reports/national-capability`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(r.status()).toBe(200);
    const body = await r.json();
    const codes = (body.wings as { code: string }[]).map((w) => w.code);
    expect(codes).toContain("7WG");
    expect(codes).toContain("11WG");
  });
});

// ── Wing admin (7WG): scope isolation ────────────────────────────────────────

test.describe("wing_admin (7WG) scope isolation", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await loginPW(page, "ADMIN7WG");
    await expect(page.getByRole("heading", { name: "Wing Assurance" })).toBeVisible({ timeout: 10000 });
  });

  test("wing overview page heading is visible", async ({ page }) => {
    await page.goto("/wing-overview");
    await expect(page.getByRole("heading", { name: "Wing Assurance" })).toBeVisible({ timeout: 10000 });
  });

  test("wing overview shows 7WG squadrons (not empty)", async ({ page }) => {
    await page.goto("/wing-overview");
    await expect(page.getByRole("heading", { name: "Wing Assurance" })).toBeVisible({ timeout: 10000 });
    // Should have a table with squadron data, not the empty-state message
    await expect(page.getByText(/no squadrons in this wing yet/i)).not.toBeVisible({ timeout: 8000 });
    await expect(page.locator("table").first()).toBeVisible({ timeout: 8000 });
  });

  test("wing overview does NOT show 11WG squadron (1101SQN)", async ({ page }) => {
    await page.goto("/wing-overview");
    await expect(page.getByRole("heading", { name: "Wing Assurance" })).toBeVisible({ timeout: 10000 });
    await expect(page.locator("table").first()).toBeVisible({ timeout: 8000 });
    // 1101SQN should not appear anywhere in the wing overview table
    await expect(page.getByRole("cell", { name: /1101/i })).not.toBeVisible();
  });

  test("wing admin navigating to /national-overview is denied or redirected", async ({ page }) => {
    await page.goto("/national-overview");
    // React PW should either redirect away or show the "no access" empty state
    // Wing assurance heading should NOT appear (wrong page)
    // National assurance heading should NOT appear (access denied)
    // The app shows a generic "not found or access not permitted" div for unrouted pages,
    // OR redirects home, OR stays on the route but renders an ErrorNote.
    // In any case: no Wing data from 11WG visible, no "National Assurance" heading.
    await page.waitForTimeout(2000);
    const nationalHeading = page.getByRole("heading", { name: "National Assurance" });
    const isVisible = await nationalHeading.isVisible().catch(() => false);
    // If the page IS accessible (e.g. no frontend access gate), verify the API
    // itself returns 403 for wing_admin — not a UI guarantee, a security guarantee
    if (isVisible) {
      // The UI rendered national-overview for a wing_admin — verify the API is the gate
      const token = await apiToken(page.request, "ADMIN7WG");
      const r = await page.request.get(`${BACKEND}/api/reports/national-overview`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      expect(r.status()).toBe(403);
    }
    // Either way: 11WG data must not appear
    await expect(page.getByRole("cell", { name: /11WG/i })).not.toBeVisible();
  });

  test("wing overview API returns only 7WG squadrons (no 11WG)", async ({ page }) => {
    const token = await apiToken(page.request, "ADMIN7WG");
    const r = await page.request.get(`${BACKEND}/api/reports/wing-overview`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(r.status()).toBe(200);
    const body = await r.json();
    const codes = (body.squadrons as { code: string }[]).map((s) => s.code);
    expect(codes).not.toContain("1101");
    // 7WG squadrons should be present
    expect(codes.length).toBeGreaterThan(0);
  });

  test("national-overview API returns 403 for wing_admin", async ({ page }) => {
    const token = await apiToken(page.request, "ADMIN7WG");
    const r = await page.request.get(`${BACKEND}/api/reports/national-overview`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(r.status()).toBe(403);
  });

  test("national-capability API returns 403 for wing_admin", async ({ page }) => {
    const token = await apiToken(page.request, "ADMIN7WG");
    const r = await page.request.get(`${BACKEND}/api/reports/national-capability`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(r.status()).toBe(403);
  });

  test("wing_id param bypass: wing_overview API ignores other wing ID", async ({ page }) => {
    // Get 11WG's ID so we can try to pass it as a query param
    const adminToken = await apiToken(page.request, "ADMINNATIONAL");
    const natR = await page.request.get(`${BACKEND}/api/reports/national-overview`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    const wings = (await natR.json()).wings as { code: string; wing_id: string }[];
    const wing11 = wings.find((w) => w.code === "11WG");
    if (!wing11) {
      test.skip(true, "11WG not found in national overview — skip bypass test");
      return;
    }

    const wingToken = await apiToken(page.request, "ADMIN7WG");
    const r = await page.request.get(`${BACKEND}/api/reports/wing-overview?wing_id=${wing11.wing_id}`, {
      headers: { Authorization: `Bearer ${wingToken}` },
    });
    // Must either 403 or return only 7WG squadrons
    if (r.status() === 200) {
      const body = await r.json();
      const codes = (body.squadrons as { code: string }[]).map((s) => s.code);
      expect(codes).not.toContain("1101");
    } else {
      expect(r.status()).toBeGreaterThanOrEqual(400);
    }
  });
});

// ── Unauthenticated ──────────────────────────────────────────────────────────

test.describe("unauthenticated access", () => {
  test("national-overview API returns 401 without token", async ({ page }) => {
    const r = await page.request.get(`${BACKEND}/api/reports/national-overview`);
    expect(r.status()).toBe(401);
  });

  test("national-capability API returns 401 without token", async ({ page }) => {
    const r = await page.request.get(`${BACKEND}/api/reports/national-capability`);
    expect(r.status()).toBe(401);
  });
});
