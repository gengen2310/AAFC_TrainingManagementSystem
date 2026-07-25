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

// ── Parade nights CRUD and scheduling (Phase 12, Gap #12) ────────────────────
// Tests the full parade-night lifecycle in the React TMS app:
//  1. Page loads and shows the parade nights list.
//  2. sqn_admin can create a parade night.
//  3. Created parade night appears in the list.
//  4. Open a parade night detail modal.
//  5. Add a session to a parade night.
//  6. Publish a parade night.
//  7. sqn_general sees the parade nights list (read-only, no "New parade night" button).
//
// Requires: local backend on :8000 (seeded), Vite dev server on :5173.

const ADMIN_CODE = "ADMIN703";
const GENERAL_CODE = "703SQN2026";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Access code").fill(ADMIN_CODE);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
});

// ── 1. Parade nights page loads ──────────────────────────────────────────────

test("parade nights page loads with list", async ({ page }) => {
  await page.goto("/parade-nights");
  await expect(page.getByRole("heading", { name: "Parade Nights" })).toBeVisible({ timeout: 8000 });
  // Should show a table or empty state — not an error
  const hasTable = await page.locator("table").first().isVisible().catch(() => false);
  const hasEmpty = await page.getByText(/no parade nights yet/i).isVisible().catch(() => false);
  expect(hasTable || hasEmpty).toBe(true);
});

test("sqn_admin sees New parade night button", async ({ page }) => {
  await page.goto("/parade-nights");
  await expect(page.getByRole("heading", { name: "Parade Nights" })).toBeVisible({ timeout: 8000 });
  await expect(page.getByRole("button", { name: "New parade night" })).toBeVisible();
});

// ── 2. Create a parade night ─────────────────────────────────────────────────

test("sqn_admin can create a parade night", async ({ page }) => {
  await page.goto("/parade-nights");
  await expect(page.getByRole("heading", { name: "Parade Nights" })).toBeVisible({ timeout: 8000 });

  await page.getByRole("button", { name: "New parade night" }).click();
  await expect(page.getByRole("dialog", { name: "New parade night" })).toBeVisible({ timeout: 5000 });

  // Fill in the form
  await page.locator("#pn-date").fill("2099-11-14");
  await page.locator("#pn-term").selectOption("T2");
  await page.locator("#pn-count").fill("3");

  // Submit
  await page.getByRole("button", { name: "Create" }).click();

  // Modal should close
  await expect(page.getByRole("dialog", { name: "New parade night" })).not.toBeVisible({ timeout: 8000 });

  // New parade night should appear in the list
  await expect(page.getByText("2099-11-14")).toBeVisible({ timeout: 8000 });
});

// ── 3. Parade night appears in list after creation ───────────────────────────

test("created parade night has correct columns in list", async ({ page }) => {
  // Create via API to avoid date collision with other tests
  const hdr = await authHeader(page, ADMIN_CODE);
  const r = await page.request.post("/api/parade-nights", {
    data: { date: "2099-12-05", term: "T4", session_count: 2 },
    headers: hdr,
  });
  expect(r.status()).toBe(200); // POST /api/parade-nights returns 200, not 201 -- app-wide convention (83/84 POST routes)

  await page.goto("/parade-nights");
  await expect(page.getByRole("heading", { name: "Parade Nights" })).toBeVisible({ timeout: 8000 });
  await expect(page.getByText("2099-12-05")).toBeVisible({ timeout: 5000 });

  // Row should show the date and a status
  const row = page.locator("tr").filter({ hasText: "2099-12-05" });
  await expect(row.getByText("T4")).toBeVisible(); // term column
  await expect(row.getByText("normal")).toBeVisible(); // parade_type default
});

// ── 4. Open parade night detail ──────────────────────────────────────────────

test("clicking Open shows parade night detail modal", async ({ page }) => {
  // Ensure we have a parade night to open (use API)
  const hdr = await authHeader(page, ADMIN_CODE);
  const r = await page.request.post("/api/parade-nights", {
    data: { date: "2099-12-12", term: "T4", session_count: 3 },
    headers: hdr,
  });
  expect(r.status()).toBe(200); // POST /api/parade-nights returns 200, not 201 -- app-wide convention (83/84 POST routes)

  await page.goto("/parade-nights");
  await expect(page.getByRole("heading", { name: "Parade Nights" })).toBeVisible({ timeout: 8000 });

  const row = page.locator("tr").filter({ hasText: "2099-12-12" });
  await row.getByRole("button", { name: "Open" }).click();

  // Detail modal appears
  const dialog = page.getByRole("dialog", { name: "Parade night" });
  await expect(dialog).toBeVisible({ timeout: 8000 });
  await expect(dialog.getByText("2099-12-12")).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Publish" })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Add session" })).toBeVisible();
});

// ── 5. Add a session to a parade night ───────────────────────────────────────

test("sqn_admin can add a session to a parade night", async ({ page }) => {
  const hdr = await authHeader(page, ADMIN_CODE);
  const r = await page.request.post("/api/parade-nights", {
    data: { date: "2099-12-19", term: "T4", session_count: 1 },
    headers: hdr,
  });
  expect(r.status()).toBe(200); // POST /api/parade-nights returns 200, not 201 -- app-wide convention (83/84 POST routes)

  await page.goto("/parade-nights");
  await expect(page.getByRole("heading", { name: "Parade Nights" })).toBeVisible({ timeout: 8000 });

  const row = page.locator("tr").filter({ hasText: "2099-12-19" });
  await row.getByRole("button", { name: "Open" }).click();

  const dialog = page.getByRole("dialog", { name: "Parade night" });
  await expect(dialog).toBeVisible({ timeout: 8000 });

  await dialog.getByRole("button", { name: "Add session" }).click();
  await expect(page.getByRole("heading", { name: "Add session" })).toBeVisible({ timeout: 5000 });

  // Fill in period number (minimum required field)
  await page.locator("#s-period").fill("1");
  await page.getByRole("button", { name: "Add", exact: true }).click();

  // Session should appear in the table
  await expect(dialog.locator("tbody tr").first()).toBeVisible({ timeout: 8000 });
});

// ── 6. Publish a parade night ─────────────────────────────────────────────────

test("parade night status changes to published after Publish", async ({ page }) => {
  const hdr = await authHeader(page, ADMIN_CODE);
  const r = await page.request.post("/api/parade-nights", {
    data: { date: "2099-12-26", term: "T4", session_count: 1 },
    headers: hdr,
  });
  expect(r.status()).toBe(200); // POST /api/parade-nights returns 200, not 201 -- app-wide convention (83/84 POST routes)
  const pnId = (await r.json()).parade_night_id as string;

  // Publishing requires every session to have a title, a facilitator, and a
  // room (see publish_blockers() in backend/app/services.py) -- fetch real
  // seeded 703 records so the session actually satisfies those blockers.
  const facs = await (await page.request.get("/api/facilitators", { headers: hdr })).json();
  const rooms = await (await page.request.get("/api/training-areas", { headers: hdr })).json();
  await page.request.post("/api/sessions", {
    data: {
      parade_night_id: pnId, period_number: 1, custom_title: "Test session",
      facilitator_id: facs[0].facilitator_id, training_area_id: rooms[0].training_area_id,
    },
    headers: hdr,
  });

  await page.goto("/parade-nights");
  await expect(page.getByRole("heading", { name: "Parade Nights" })).toBeVisible({ timeout: 8000 });

  const row = page.locator("tr").filter({ hasText: "2099-12-26" });
  await row.getByRole("button", { name: "Open" }).click();

  const dialog = page.getByRole("dialog", { name: "Parade night" });
  await expect(dialog).toBeVisible({ timeout: 8000 });

  await dialog.getByRole("button", { name: "Publish" }).click();

  // Status badge should update to published
  await expect(dialog.getByText(/published/i).first()).toBeVisible({ timeout: 8000 });
});

// ── 7. sqn_general sees read-only list ───────────────────────────────────────

test("sqn_general sees parade nights list but no create button", async ({ page }) => {
  // Re-login as general user
  await page.goto("/");
  await page.getByRole("button", { name: /sign out/i }).click();
  await expect(page.getByRole("button", { name: "Log in" })).toBeVisible({ timeout: 5000 });

  await page.getByLabel("Access code").fill(GENERAL_CODE);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });

  await page.goto("/parade-nights");
  await expect(page.getByRole("heading", { name: "Parade Nights" })).toBeVisible({ timeout: 8000 });

  // Should NOT see the create button
  await expect(page.getByRole("button", { name: "New parade night" })).not.toBeVisible();
  // Should see the table (list of parade nights created in other tests)
  const hasTable = await page.locator("table").first().isVisible().catch(() => false);
  const hasEmpty = await page.getByText(/no parade nights yet/i).isVisible().catch(() => false);
  expect(hasTable || hasEmpty).toBe(true);
});

// ── Helpers ──────────────────────────────────────────────────────────────────

async function authHeader(page: import("@playwright/test").Page, code: string): Promise<Record<string, string>> {
  const r = await page.request.post("/api/auth/login", { data: { code } });
  const token = (await r.json()).token as string;
  return { Authorization: `Bearer ${token}` };
}
