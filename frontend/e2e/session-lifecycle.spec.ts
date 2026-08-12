import { test, expect, type Page } from "@playwright/test";
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

// ── Session lifecycle: cancellation and rescheduling ─────────────────────────
// Phase 12 — Tests the full cancelled-lesson and rescheduled-lesson operator
// workflows through the Planning Workspace browser UI.
//
// Each test that needs a session seeds one via API (using the already-authenticated
// page.request context) rather than clicking through creation UIs — this tests the
// status-change interaction, not the creation UI (which parade-nights.spec.ts already
// covers). The test then navigates to the parade nights list and opens the seeded
// parade night's modal to exercise the status workflow.

const ADMIN_CODE = "ADMIN703";
const GENERAL_CODE = "703SQN2026";
const BASE = process.env.E2E_BACKEND_BASE_URL || "http://localhost:8000";

/** Login and seed a parade night + session via API. Returns the parade_night_id. */
async function seedParadeNightWithSession(page: Page, date: string): Promise<string> {
  // Derive auth token from the already-logged-in session cookie/storage.
  const meRes = await page.request.get(`${BASE}/api/auth/me`);
  expect(meRes.ok()).toBe(true);
  const me = await meRes.json();
  const sqnId = me.session.squadron_id as string;
  const wingId = me.session.wing_id as string;

  // Create parade night
  const pnRes = await page.request.post(`${BASE}/api/parade-nights`, {
    data: { squadron_id: sqnId, wing_id: wingId, date, parade_type: "normal" },
  });
  expect(pnRes.ok()).toBe(true);
  const pnId = (await pnRes.json()).parade_night_id as string;

  // Add one session
  const sessRes = await page.request.post(`${BASE}/api/sessions`, {
    data: { parade_night_id: pnId, period_number: 1 },
  });
  expect(sessRes.ok()).toBe(true);

  return pnId;
}

/** Navigate to parade nights list, find the row for <date>, and open its detail modal. */
async function openParadeNightModal(page: Page, date: string) {
  await page.goto("/parade-nights");
  await expect(page.getByRole("heading", { name: "Parade Nights" })).toBeVisible({ timeout: 8000 });
  // Find the row containing our date and click its Open button
  const row = page.locator("table tbody tr").filter({ hasText: date });
  await expect(row).toBeVisible({ timeout: 5000 });
  await row.getByRole("button", { name: "Open" }).click();
  // Modal should appear
  await expect(page.getByRole("dialog")).toBeVisible({ timeout: 5000 });
}

// ── Basic navigation tests ────────────────────────────────────────────────────

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await loginPW(page, ADMIN_CODE);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
});

test("parade night list shows planned nights", async ({ page }) => {
  await page.goto("/parade-nights");
  await expect(page.getByRole("heading", { name: /parade night/i })).toBeVisible({ timeout: 8000 });
  // 703 has seeded parade nights
  const rows = page.locator("table tbody tr");
  await expect(rows.first()).toBeVisible({ timeout: 5000 });
});

test("can open a parade night detail modal", async ({ page }) => {
  await page.goto("/parade-nights");
  await expect(page.getByRole("heading", { name: /parade night/i })).toBeVisible({ timeout: 8000 });
  const openBtn = page.getByRole("button", { name: "Open" }).first();
  await expect(openBtn).toBeVisible({ timeout: 5000 });
  await openBtn.click();
  await expect(page.getByRole("dialog")).toBeVisible({ timeout: 5000 });
});

test("facilitator statistics show on facilitators page", async ({ page }) => {
  await page.goto("/facilitators");
  await expect(page.getByRole("heading", { name: /facilitator/i })).toBeVisible({ timeout: 8000 });
  // 703 has 5 seeded facilitators — use .first() to avoid strict-mode violation
  await expect(page.getByText(/Daley|Flanders|McGhie|Milligen|Daniels/i).first()).toBeVisible({ timeout: 5000 });
});

// ── Session status: not_delivered (cancellation) ──────────────────────────────

test("can mark a session as not_delivered with a reason", async ({ page }) => {
  const date = "2099-11-28";
  await seedParadeNightWithSession(page, date);
  await openParadeNightModal(page, date);

  // Click Set status on the session row
  await page.getByRole("button", { name: "Set status" }).first().click();

  // The inline form should appear with the status selector
  await expect(page.locator("#st-status")).toBeVisible({ timeout: 3000 });

  // Change to not_delivered
  await page.locator("#st-status").selectOption("not_delivered");

  // Reason dropdown must now appear (required for not_delivered)
  await expect(page.locator("#st-reason")).toBeVisible({ timeout: 2000 });
  await page.locator("#st-reason").selectOption("Facilitator unavailable");

  // Save
  await page.getByRole("button", { name: "Save status" }).click();

  // Form should close and session row should reflect the new status
  await expect(page.locator("#st-status")).not.toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/not delivered/i).first()).toBeVisible({ timeout: 5000 });
});

test("Save status button is disabled without a reason for not_delivered", async ({ page }) => {
  const date = "2099-11-29";
  await seedParadeNightWithSession(page, date);
  await openParadeNightModal(page, date);

  await page.getByRole("button", { name: "Set status" }).first().click();
  await expect(page.locator("#st-status")).toBeVisible({ timeout: 3000 });

  // Select not_delivered — reason now required
  await page.locator("#st-status").selectOption("not_delivered");
  await expect(page.locator("#st-reason")).toBeVisible({ timeout: 2000 });

  // Without selecting a reason, Save status must be disabled
  const saveBtn = page.getByRole("button", { name: "Save status" });
  await expect(saveBtn).toBeDisabled();
});

// ── Session status: rescheduled ───────────────────────────────────────────────

test("can mark a session as rescheduled with a target date", async ({ page }) => {
  const date = "2099-11-30";
  await seedParadeNightWithSession(page, date);
  await openParadeNightModal(page, date);

  await page.getByRole("button", { name: "Set status" }).first().click();
  await expect(page.locator("#st-status")).toBeVisible({ timeout: 3000 });

  // Select rescheduled — shows the target date field (#st-res), no reason required
  await page.locator("#st-status").selectOption("rescheduled");
  const reschedField = page.locator("#st-res");
  await expect(reschedField).toBeVisible({ timeout: 2000 });
  await reschedField.fill("2099-12-05");

  await page.getByRole("button", { name: "Save status" }).click();

  // Form closes; status cell shows "rescheduled"
  await expect(page.locator("#st-status")).not.toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/rescheduled/i).first()).toBeVisible({ timeout: 5000 });
});

// ── Session status: RBAC ──────────────────────────────────────────────────────

test("viewer role does not see Set status button", async ({ page }) => {
  // Re-login as a viewer (sqn_general)
  await page.goto("/");
  await loginPW(page, GENERAL_CODE);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });

  await page.goto("/parade-nights");
  await expect(page.getByRole("heading", { name: "Parade Nights" })).toBeVisible({ timeout: 8000 });

  // Open first parade night (seeded data)
  const openBtn = page.getByRole("button", { name: "Open" }).first();
  if (await openBtn.count() > 0) {
    await openBtn.click();
    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 5000 });
    // sqn_general is read-only — no "Set status" or "Add session" buttons
    await expect(page.getByRole("button", { name: "Set status" })).not.toBeVisible();
    await expect(page.getByRole("button", { name: "Add session" })).not.toBeVisible();
  }
});

// ── Session status: reason also required for cancelled_late ───────────────────

test("reason dropdown appears for cancelled_late status", async ({ page }) => {
  const date = "2099-12-01";
  await seedParadeNightWithSession(page, date);
  await openParadeNightModal(page, date);

  await page.getByRole("button", { name: "Set status" }).first().click();
  await expect(page.locator("#st-status")).toBeVisible({ timeout: 3000 });

  await page.locator("#st-status").selectOption("cancelled_late");
  // Same REASON_REQUIRED_STATUSES set — reason dropdown must appear
  await expect(page.locator("#st-reason")).toBeVisible({ timeout: 2000 });
});

// ── Session status: delivered (no reason required) ────────────────────────────

test("can mark a session as delivered without a reason", async ({ page }) => {
  const date = "2099-12-02";
  await seedParadeNightWithSession(page, date);
  await openParadeNightModal(page, date);

  await page.getByRole("button", { name: "Set status" }).first().click();
  await expect(page.locator("#st-status")).toBeVisible({ timeout: 3000 });

  // "delivered" is the default — reason dropdown should NOT appear
  await expect(page.locator("#st-reason")).not.toBeVisible();

  // Save without selecting a reason — button must be enabled
  const saveBtn = page.getByRole("button", { name: "Save status" });
  await expect(saveBtn).not.toBeDisabled();
  await saveBtn.click();

  await expect(page.locator("#st-status")).not.toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/delivered/i).first()).toBeVisible({ timeout: 5000 });
});
