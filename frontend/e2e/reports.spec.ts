import { test, expect } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// DEFECT-004: playwright-global-setup.ts resets rate limits once per full
// suite invocation, which is not always enough for a large suite -- a
// spec file's own request volume, especially with other files having run
// immediately before it, can still cross the general API limiter's
// 300 req/60s budget partway through (observed live running this suite).
// A per-file reset gives this file its own fresh budget. Best-effort; see
// e2e-rate-limit-reset.ts for what this does and its known limitations.
test.beforeAll(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || "http://localhost:8000");
});

// ── Training Reports (Phase 12, Gap #12) ─────────────────────────────────────
// Tests the three report cards in Reports.tsx:
//   1. Curriculum coverage — coverage_pct Bar + scheduled/delivered summary
//   2. Facilitator load — table with Facilitator/Sessions/Delivered/Risk columns
//   3. Not delivered — table of sessions with Code + Reason columns
//
// Also verifies:
//   - API endpoints return expected shapes
//   - sqn_general can view reports (read-only, no write controls on this page)
//   - Wing/national note appears for non-squadron roles (not tested here — out of scope for beta)
//
// Requires: local backend on :8000 (seeded), Vite dev server on :5173.
//
// Selector notes (from Reports.tsx):
//   - Page heading: h1 "Training Reports"
//   - Cards: role="heading" level 2 within Cards — "Curriculum coverage", "Facilitator load", "Not delivered"
//   - Bar component: a progress/bar visual — no specific role, tested by presence of parent card content
//   - "Other reports" card is always shown as a placeholder

const ADMIN_CODE = "ADMIN703";
const GENERAL_CODE = "703SQN2026";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Access code").fill(ADMIN_CODE);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
});

// ── 1. Page loads ─────────────────────────────────────────────────────────────

test("Training Reports page loads with all three report cards", async ({ page }) => {
  await page.goto("/reports");
  await expect(page.getByRole("heading", { name: "Training Reports" })).toBeVisible({ timeout: 8000 });
  await expect(page.getByText("Curriculum coverage")).toBeVisible({ timeout: 8000 });
  await expect(page.getByText("Facilitator load")).toBeVisible({ timeout: 8000 });
  await expect(page.getByText("Not delivered")).toBeVisible({ timeout: 8000 });
});

test("Other reports placeholder card is always shown", async ({ page }) => {
  await page.goto("/reports");
  await expect(page.getByRole("heading", { name: "Training Reports" })).toBeVisible({ timeout: 8000 });
  await expect(page.getByText("Other reports")).toBeVisible({ timeout: 8000 });
});

// ── 2. Curriculum coverage card ───────────────────────────────────────────────

test("curriculum coverage card shows coverage summary", async ({ page }) => {
  await page.goto("/reports");
  await expect(page.getByRole("heading", { name: "Training Reports" })).toBeVisible({ timeout: 8000 });

  // Wait for the card content to load (not still showing Loading spinner)
  await expect(page.getByText(/scheduled · .* delivered/i)).toBeVisible({ timeout: 10000 });
  // Format: "{scheduled}/{total} scheduled · {delivered} delivered."
  await expect(page.getByText(/\d+\/\d+ scheduled/i)).toBeVisible();
});

test("curriculum coverage API returns expected shape", async ({ page }) => {
  const hdr = await authHeader(page, ADMIN_CODE);
  const r = await page.request.get("/api/reports/curriculum-coverage", { headers: hdr });
  expect(r.status()).toBe(200);
  const body = await r.json();
  expect(body).toHaveProperty("coverage_pct");
  expect(body).toHaveProperty("scheduled");
  expect(body).toHaveProperty("delivered");
  expect(body).toHaveProperty("total");
  expect(body).toHaveProperty("decision");
  expect(body).toHaveProperty("unscheduled");
  expect(Array.isArray(body.unscheduled)).toBe(true);
  expect(typeof body.coverage_pct).toBe("number");
});

// ── 3. Facilitator load card ──────────────────────────────────────────────────

test("facilitator load card renders without error", async ({ page }) => {
  await page.goto("/reports");
  await expect(page.getByRole("heading", { name: "Training Reports" })).toBeVisible({ timeout: 8000 });

  // DEFECT-003 (AL-02): two bugs fixed here.
  // 1. The card shows a Loading state (role="status") while its query is in
  //    flight, then settles into either a table or the "No facilitator load
  //    yet." empty state. A one-shot isVisible().catch(() => false) was
  //    flaky-by-design -- it could run during the Loading window, before
  //    either exists. Now waits (with Playwright's built-in retry) for one
  //    to actually appear.
  // 2. table.nth(0) assumed the facilitator table is always the first
  //    <table> on the page, but the Curriculum coverage card above it also
  //    renders a <table> (inside a closed <details>, for unscheduled items)
  //    whenever there's unscheduled curriculum -- which is hidden, but
  //    still nth(0). Locate by header content instead of position.
  const table = page.locator("table").filter({ hasText: /Facilitator.*Sessions.*Delivered.*Risk/i });
  const empty = page.getByText(/no facilitator load yet/i);
  await expect(table.or(empty)).toBeVisible({ timeout: 10000 });

  // Must be one or the other — no error note
  await expect(page.locator(".errnote, .errbox").first()).not.toBeVisible();
});

test("facilitator load API returns expected shape", async ({ page }) => {
  const hdr = await authHeader(page, ADMIN_CODE);
  const r = await page.request.get("/api/reports/facilitator-load", { headers: hdr });
  expect(r.status()).toBe(200);
  const body = await r.json();
  expect(body).toHaveProperty("facilitators");
  expect(Array.isArray(body.facilitators)).toBe(true);
  expect(body).toHaveProperty("decision");
  if (body.facilitators.length > 0) {
    const f = body.facilitators[0];
    expect(f).toHaveProperty("name");
    expect(f).toHaveProperty("sessions");
    expect(f).toHaveProperty("delivered");
    expect(f).toHaveProperty("risk");
  }
});

test("facilitator load table has correct columns when data is present", async ({ page }) => {
  await page.goto("/reports");
  await expect(page.getByRole("heading", { name: "Training Reports" })).toBeVisible({ timeout: 8000 });

  // Only assert column headers if the table is visible
  const tables = page.locator("table");
  const tableCount = await tables.count();
  if (tableCount > 0) {
    // Find the facilitator load table by its header row
    const facTable = tables.filter({ hasText: /Facilitator.*Sessions.*Delivered.*Risk/i });
    if (await facTable.count() > 0) {
      await expect(facTable.getByRole("columnheader", { name: "Facilitator" })).toBeVisible();
      await expect(facTable.getByRole("columnheader", { name: "Sessions" })).toBeVisible();
      await expect(facTable.getByRole("columnheader", { name: "Delivered" })).toBeVisible();
      await expect(facTable.getByRole("columnheader", { name: "Risk" })).toBeVisible();
    }
  }
});

// ── 4. Not delivered card ─────────────────────────────────────────────────────

test("not delivered card renders without error", async ({ page }) => {
  await page.goto("/reports");
  await expect(page.getByRole("heading", { name: "Training Reports" })).toBeVisible({ timeout: 8000 });

  // DEFECT-003 (AL-02): same two fixes as the facilitator load card above --
  // wait for the query to settle instead of a one-shot check, and locate by
  // header content ("Code"/"Reason") instead of table.last(), which would
  // silently resolve to a different table if this card's own table hasn't
  // rendered yet (or isn't present at all, in the empty-state case).
  const table = page.locator("table").filter({ hasText: /Code.*Reason/i });
  const empty = page.getByText(/no not-delivered sessions/i);
  await expect(table.or(empty)).toBeVisible({ timeout: 10000 });

  await expect(page.locator(".errnote, .errbox").first()).not.toBeVisible();
});

test("not delivered API returns expected shape", async ({ page }) => {
  const hdr = await authHeader(page, ADMIN_CODE);
  const r = await page.request.get("/api/reports/not-delivered", { headers: hdr });
  expect(r.status()).toBe(200);
  const body = await r.json();
  expect(body).toHaveProperty("sessions");
  expect(Array.isArray(body.sessions)).toBe(true);
  expect(body).toHaveProperty("decision");
  if (body.sessions.length > 0) {
    const s = body.sessions[0];
    expect(s).toHaveProperty("id");
  }
});

// ── 5. sqn_general can view all three cards ───────────────────────────────────

test("sqn_general can access the reports page", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /sign out/i }).click();
  await expect(page.getByRole("button", { name: "Log in" })).toBeVisible({ timeout: 5000 });

  await page.getByLabel("Access code").fill(GENERAL_CODE);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });

  await page.goto("/reports");
  await expect(page.getByRole("heading", { name: "Training Reports" })).toBeVisible({ timeout: 8000 });
  await expect(page.getByText("Curriculum coverage")).toBeVisible({ timeout: 8000 });
  await expect(page.getByText("Facilitator load")).toBeVisible({ timeout: 8000 });
  await expect(page.getByText("Not delivered")).toBeVisible({ timeout: 8000 });
});

// ── Helpers ───────────────────────────────────────────────────────────────────

async function authHeader(page: import("@playwright/test").Page, code: string): Promise<Record<string, string>> {
  const r = await page.request.post("/api/auth/login", { data: { code } });
  const token = (await r.json()).token as string;
  return { Authorization: `Bearer ${token}` };
}
