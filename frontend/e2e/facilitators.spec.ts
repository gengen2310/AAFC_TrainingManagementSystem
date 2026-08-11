import { test, expect } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";
import { loginPW } from "../e2e-login-helper";

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

// ── Facilitator management (Phase 12, Gap #12) ───────────────────────────────
// Tests the facilitator list, add-facilitator flow, tag editing, stats panel,
// and leave-period API (RBAC proof).
//
// Requires: local backend on :8000 (seeded), Vite dev server on :5173.
//
// Selector notes (from Facilitators.tsx + Modal.tsx):
//   - Add form fields: #f-first, #f-last, #f-rank
//   - Add button in modal: role="button" name="Add"
//   - Stats drilldown: role="dialog" aria-label="Facilitator stats"
//   - Leave endpoint: POST /api/planning/facilitators/{fac_id}/leave

const ADMIN_CODE = "ADMIN703";
const GENERAL_CODE = "703SQN2026";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await loginPW(page, ADMIN_CODE);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
});

// ── 1. Page loads ─────────────────────────────────────────────────────────────

test("facilitators page loads with seeded data", async ({ page }) => {
  await page.goto("/facilitators");
  await expect(page.getByRole("heading", { name: "Facilitators" })).toBeVisible({ timeout: 8000 });
  const hasTable = await page.locator("table").first().isVisible().catch(() => false);
  const hasEmpty = await page.getByText(/no facilitators yet/i).isVisible().catch(() => false);
  expect(hasTable || hasEmpty).toBe(true);
});

test("facilitators table has correct column headers", async ({ page }) => {
  await page.goto("/facilitators");
  await expect(page.getByRole("heading", { name: "Facilitators" })).toBeVisible({ timeout: 8000 });
  await expect(page.getByRole("columnheader", { name: "Rank" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Name" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Type" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Subjects" })).toBeVisible();
});

test("seeded facilitators appear in list", async ({ page }) => {
  await page.goto("/facilitators");
  await expect(page.getByRole("heading", { name: "Facilitators" })).toBeVisible({ timeout: 8000 });
  const rowCount = await page.locator("tbody tr").count();
  expect(rowCount).toBeGreaterThan(0);
});

// ── 2. Add a facilitator ──────────────────────────────────────────────────────

test("sqn_admin can add a facilitator", async ({ page }) => {
  await page.goto("/facilitators");
  await expect(page.getByRole("heading", { name: "Facilitators" })).toBeVisible({ timeout: 8000 });

  await page.getByRole("button", { name: "Add facilitator" }).click();
  const dialog = page.getByRole("dialog", { name: "Add facilitator" });
  await expect(dialog).toBeVisible({ timeout: 5000 });

  await dialog.locator("#f-first").fill("Playwright");
  await dialog.locator("#f-last").fill("TestFac");
  await dialog.locator("#f-rank").fill("CI");

  // "Add" button is enabled only when first + last are filled
  await dialog.getByRole("button", { name: "Add" }).click();

  await expect(dialog).not.toBeVisible({ timeout: 8000 });
  await expect(page.getByText("TestFac")).toBeVisible({ timeout: 8000 });
});

// ── 3. Stats drilldown ────────────────────────────────────────────────────────

test("clicking Stats opens the facilitator stats drilldown", async ({ page }) => {
  await page.goto("/facilitators");
  await expect(page.getByRole("heading", { name: "Facilitators" })).toBeVisible({ timeout: 8000 });

  // Click Stats on the first row (DrilldownPanel wraps Modal → role="dialog")
  await page.locator("tbody tr").first().getByRole("button", { name: "Stats" }).click();
  await expect(page.getByRole("dialog", { name: "Facilitator stats" })).toBeVisible({ timeout: 6000 });
});

// ── 4. Tags modal opens ───────────────────────────────────────────────────────

test("sqn_admin can open the Tags modal for a facilitator", async ({ page }) => {
  await page.goto("/facilitators");
  await expect(page.getByRole("heading", { name: "Facilitators" })).toBeVisible({ timeout: 8000 });

  // Tags button is only visible to canWriteSquadron
  const tagsBtn = page.locator("tbody tr").first().getByRole("button", { name: "Tags" });
  await expect(tagsBtn).toBeVisible({ timeout: 5000 });
  await tagsBtn.click();

  // Dialog title is "Subject areas — <rank> <first> <last>"
  const dialog = page.locator('[role="dialog"]').filter({ hasText: /Subject areas/i });
  await expect(dialog).toBeVisible({ timeout: 5000 });
  await expect(page.getByRole("button", { name: "Save tags" })).toBeVisible();
});

// ── 5. Leave conflict API proof ───────────────────────────────────────────────

test("facilitator leave can be recorded via API", async ({ page }) => {
  const hdr = await authHeader(page, ADMIN_CODE);

  const facs = await page.request.get("/api/facilitators", { headers: hdr });
  expect(facs.status()).toBe(200);
  const facList = (await facs.json()) as { facilitator_id: string }[];

  if (facList.length === 0) {
    test.skip(true, "No facilitators seeded; skipping leave test");
    return;
  }

  const facId = facList[0].facilitator_id;
  const leave = await page.request.post(`/api/planning/facilitators/${facId}/leave`, {
    data: {
      start_date: "2099-08-01",
      end_date: "2099-08-07",
      reason: "Playwright test leave",
    },
    headers: hdr,
  });
  expect([200, 201]).toContain(leave.status());
  const body = await leave.json();
  // AL-02 (docs/beta/15_known_limitations.md): the real response nests the
  // created record under "leave" -- {"ok", "leave": {...}, "affected_sessions"}
  // -- not a bare facilitator_id at the top level.
  expect(body).toHaveProperty("leave");
  expect(body.leave).toHaveProperty("facilitator_id", facId);
});

// ── 6. Read-only for sqn_general ──────────────────────────────────────────────

test("sqn_general sees facilitators list but no Add facilitator button", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /sign out/i }).click();
  await expect(page.getByRole("button", { name: "Log in" })).toBeVisible({ timeout: 5000 });

  await loginPW(page, GENERAL_CODE);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });

  await page.goto("/facilitators");
  await expect(page.getByRole("heading", { name: "Facilitators" })).toBeVisible({ timeout: 8000 });
  await expect(page.getByRole("button", { name: "Add facilitator" })).not.toBeVisible();
  // Tags button is also hidden for general
  const rows = page.locator("tbody tr");
  if (await rows.count() > 0) {
    await expect(rows.first().getByRole("button", { name: "Tags" })).not.toBeVisible();
    // Stats is visible to all
    await expect(rows.first().getByRole("button", { name: "Stats" })).toBeVisible();
  }
});

// ── Helpers ───────────────────────────────────────────────────────────────────

async function authHeader(page: import("@playwright/test").Page, code: string): Promise<Record<string, string>> {
  const r = await page.request.post("/api/auth/login", { data: { code } });
  const token = (await r.json()).token as string;
  return { Authorization: `Bearer ${token}` };
}
