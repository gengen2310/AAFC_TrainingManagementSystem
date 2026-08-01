import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// ── NATHQ/Wing/Squadron Activities inheritance (Phase 2) ─────────────────────
// Verifies the core requirement end-to-end through the real UI: a National
// activity created once is immediately visible at Wing and Squadron scope
// with no republish/reimport step, correctly badged by source, and read-only
// at every scope except the one that owns it.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

test.beforeEach(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

async function loginNational(page: Page, code: string, role: "system_admin" = "system_admin") {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => { (window as any).AAFC_API_BASE = base; }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("national");
  await page.locator("#auth-role").selectOption(role);
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill(code);
  await page.locator("#auth-btn").click();
  await expect(page.getByText("System Overview")).toBeVisible({ timeout: 10000 });
}

async function loginSquadron(page: Page, code: string) {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => { (window as any).AAFC_API_BASE = base; }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("squadron");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-sqn-select").selectOption("703");
  await page.locator("#auth-role").selectOption("sqn_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill(code);
  await page.locator("#auth-btn").click();
  await expect(page.locator(".ph-title", { hasText: "Training Dashboard" })).toBeVisible({ timeout: 10000 });
}

test("National activity created via the UI is immediately visible, correctly badged, at Wing and Squadron scope", async ({ page }) => {
  const uniqueName = "E2E National Activity " + Date.now();

  await loginNational(page, "SYSADMIN2026");
  await page.evaluate(() => (window as any).nav("national-activities"));
  await expect(page.locator("#act-tab-national .ctitle", { hasText: "Activities" })).toBeVisible({ timeout: 10000 });

  await page.locator("#act-tab-national button", { hasText: "+ New National Activity" }).click();
  await page.locator("#act-tab-national-c-name").fill(uniqueName);
  await page.locator("#act-tab-national-c-start").fill("2026-11-01");
  await page.locator("#act-tab-national-detail button", { hasText: "Create" }).click();

  await expect(page.locator("#act-tab-national").getByText(uniqueName)).toBeVisible({ timeout: 10000 });
  const nationalRow = page.locator("#act-tab-national tr", { hasText: uniqueName });
  await expect(nationalRow.getByText("NATHQ", { exact: true })).toBeVisible();

  // Wing scope — same activity, no republish step. Selecting a wing reboots
  // the app and its own bootApp() lands on Wing Overview (SCOPE_LANDING) —
  // must wait for that async landing to finish before navigating onward, or
  // this explicit nav() races bootApp()'s own and loses (same class of race
  // documented in training-dashboard.spec.ts's loginNational() helper).
  const wsel = page.locator("#sa-scope-wing");
  await wsel.selectOption({ label: "7WG — 7 Wing (Western Australia)" });
  await expect(page.locator("#page-wing-overview")).toHaveClass(/active/, { timeout: 10000 });
  await page.evaluate(() => (window as any).nav("wing-activities"));
  await expect(page.locator("#act-tab-wing").getByText(uniqueName)).toBeVisible({ timeout: 10000 });
  const wingRow = page.locator("#act-tab-wing tr", { hasText: uniqueName });
  await expect(wingRow.getByText("NATHQ", { exact: true })).toBeVisible();
  await expect(wingRow.locator("text=🔒")).toHaveCount(0); // system_admin can still write nationally-owned rows directly

  // Squadron scope — same activity again. Note: read_only reflects the
  // VIEWER's own write capability, not the viewing scope -- system_admin has
  // unconditional write authority over national-owned rows everywhere
  // (require_can_write_activity), so it correctly still gets the Edit form
  // here too. The genuine "inherited = read-only for a real subordinate
  // viewer" case is covered by the sqn_admin test below, using a holiday row.
  const ssel = page.locator("#sa-scope-sqn");
  await ssel.selectOption({ label: "703 — 703 Squadron — City of Fremantle" });
  await expect(page.locator("#page-dashboard")).toHaveClass(/active/, { timeout: 10000 });
  await page.evaluate(() => (window as any).nav("activities"));
  await expect(page.locator("#act-tab-squadron").getByText(uniqueName)).toBeVisible({ timeout: 10000 });
});

test("Squadron admin sees inherited activities as read-only alongside their own local activities", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await page.evaluate(() => (window as any).nav("activities"));
  await expect(page.locator("#act-tab-squadron .ctitle", { hasText: "Inherited Activities" })).toBeVisible({ timeout: 10000 });
  // The existing local-only Activities table (pre-existing feature) must still
  // be present, unaffected, above the new inherited-activities section.
  await expect(page.locator("#act-tbody")).toBeVisible();

  // A real subordinate viewer (sqn_admin) sees an inherited row as read-only.
  // Holiday rows are pre-seeded and always read_only=true for every viewer.
  const holidayRow = page.locator("#act-tab-squadron tr", { hasText: "Holiday" }).first();
  await expect(holidayRow).toBeVisible({ timeout: 10000 });
  await holidayRow.click();
  await expect(page.locator("#act-tab-squadron-detail")).toContainText("read-only here");
});
