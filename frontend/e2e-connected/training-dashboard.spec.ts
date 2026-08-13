import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// ── Wing/National Training Dashboard (Sections A + B) ───────────────────────
// Covers the scenarios most specific to this feature. Scenarios already
// exercised by the existing System Administrator scope-selector suite
// (squadron isolation, archive filters, Proxy/Intervention Mode banner+audit,
// IDOR) are not duplicated here — see the GAP-21 regression suite
// (backend/tests/test_org_account_linking.py) and this file's own coverage of
// the command-dashboard-specific backend logic
// (backend/tests/test_command_dashboard.py).

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

// Per-test (not beforeAll): each test's login + loadData() pulls enough
// dashboard traffic that a single suite-wide reset can still let the general
// 300req/60s limiter (DEFECT-004) trip partway through this file's 10 tests —
// confirmed live (a consistent failure at the same later test, "Cannot reach
// the backend" from the app's own fetch, across repeated runs). A fresh
// reset per test removes the flakiness rather than tolerating it.
test.beforeEach(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

async function loginNational(page: Page, code: string, role: "system_admin" | "national_admin" = "system_admin") {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => { (window as any).AAFC_API_BASE = base; }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("national");
  await page.locator("#auth-role").selectOption(role);
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill(code);
  await page.locator("#auth-btn").click();
  // System Console — not National Overview — is system_admin's documented
  // default landing page (.claude/rules/frontend.md). Must wait for login's
  // own async bootApp() to finish landing on System Console FIRST (its own
  // nav('system-console') call would otherwise race with and override an
  // early nav('national') call here) before navigating onward — matching
  // this suite's established page.evaluate(() => nav(...)) convention (see
  // main-tms.spec.ts) rather than clicking the sidenav item, so this helper
  // also works regardless of viewport/hamburger-menu state.
  await expect(page.getByText("System Overview")).toBeVisible({ timeout: 10000 });
  await page.evaluate(() => (window as any).nav("national"));
  // #dash-title is the pre-existing (always-in-DOM, statically-labelled)
  // Squadron Dashboard title — ".ph-title:has-text('Training Dashboard')"
  // matches it too, so every assertion below is scoped to this feature's own
  // container (#cmd-dash-national / #cmd-dash-wing), not a bare class search.
  await expect(page.locator("#cmd-dash-national .ph-title", { hasText: "Training Dashboard" })).toBeVisible({ timeout: 10000 });
}

async function loginWing(page: Page, code: string, role: "wing_admin" | "wing_viewer" = "wing_admin") {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => { (window as any).AAFC_API_BASE = base; }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("wing");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-role").selectOption(role);
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill(code);
  await page.locator("#auth-btn").click();
  await expect(page.locator("#cmd-dash-wing .ph-title", { hasText: "Training Dashboard" })).toBeVisible({ timeout: 10000 });
}

// 1. System Administrator opens National dashboard.
test("System Administrator opens the National Training Dashboard", async ({ page }) => {
  await loginNational(page, "SYSADMIN2026");
  await expect(page.locator("#page-national .ph-title", { hasText: "Training Dashboard" })).toBeVisible();
  await expect(page.getByText("A — IMMEDIATE TRAINING READINESS")).toBeVisible();
  await expect(page.getByText("B — TRAINING DELIVERY PERFORMANCE")).toBeVisible();
  await expect(page.getByText("NEXT PARADE NIGHT READINESS")).toBeVisible();
  // National-scope Wing/National dashboard functions coexist with the
  // existing National oversight page below it — not replaced.
  await expect(page.getByText("National HQ — Assurance Overview")).toBeVisible();
});

// REM-115 residual: Wing/National Overview previously had zero real headings
// (the .ph-title page title and the A/B section labels were all plain divs),
// unlike the 14 other pages REM-115's main pass already converted. Each of
// these two pages now has exactly one <h1> ("Training Dashboard", the page's
// primary heading) with the pre-existing "A —"/"B —" section labels and the
// page's own "{scope} — Training/Assurance ..." sub-heading demoted to <h2>
// siblings -- not left as unlabelled divs, and not given a second competing
// <h1>.
test("National Overview has exactly one h1, and its section headings are real headings not divs", async ({ page }) => {
  await loginNational(page, "SYSADMIN2026");
  const page1 = page.locator("#page-national");
  await expect(page1.locator("h1")).toHaveCount(1);
  await expect(page1.locator("h1")).toHaveText("Training Dashboard");
  await expect(page1.locator("h2", { hasText: "A — Immediate Training Readiness" })).toBeVisible();
  await expect(page1.locator("h2", { hasText: "B — Training Delivery Performance" })).toBeVisible();
  await expect(page1.locator("h2", { hasText: "National HQ — Assurance Overview" })).toBeVisible();
});

test("Wing Overview has exactly one h1, and its section headings are real headings not divs", async ({ page }) => {
  await loginWing(page, "ADMIN7WG");
  const page1 = page.locator("#page-wing-overview");
  await expect(page1.locator("h1")).toHaveCount(1);
  await expect(page1.locator("h1")).toHaveText("Training Dashboard");
  await expect(page1.locator("h2", { hasText: "A — Immediate Training Readiness" })).toBeVisible();
  await expect(page1.locator("h2", { hasText: "B — Training Delivery Performance" })).toBeVisible();
  await expect(page1.locator("h2", { hasText: "Training Assurance" })).toBeVisible();
});

// 2. System Administrator selects 7 Wing.
test("System Administrator drills into 7 Wing via the scope selector", async ({ page }) => {
  await loginNational(page, "SYSADMIN2026");
  await page.locator("#sa-scope-wing").selectOption({ label: "7WG — 7 Wing (Western Australia)" });
  // Selecting a Wing lands system_admin on the Wing Overview page (SCOPE_LANDING
  // in index.html) — the same page wing_admin uses, not a separate
  // implementation. #cmd-dash-national's own (now-inactive) content stays in the
  // DOM, so every assertion below is scoped to #cmd-dash-wing specifically.
  await expect(page.locator("#page-wing-overview")).toHaveClass(/active/, { timeout: 10000 });
  await expect(page.locator("#cmd-dash-wing .ph-sub", { hasText: "Scope: Wing" })).toBeVisible();
  await expect(page.locator("#cmd-dash-wing").getByText("Next parade night readiness", { exact: false })).toBeVisible();
  // Wing view rows are Squadrons, not Wings. Cell text is "703 703SQN" (code +
  // short name), so match as a substring rather than exact.
  await expect(page.locator("#cmd-dash-wing table").first().getByText("703", { exact: false }).first()).toBeVisible();
});

// 3. System Administrator selects a Squadron.
test("System Administrator drills into a Squadron and sees the native Squadron dashboard", async ({ page }) => {
  await loginNational(page, "SYSADMIN2026");
  await page.locator("#sa-scope-wing").selectOption({ label: "7WG — 7 Wing (Western Australia)" });
  await expect(page.locator("#sa-scope-sqn")).toBeVisible({ timeout: 10000 });
  await page.locator("#sa-scope-sqn").selectOption({ label: "703 — 703 Squadron — City of Fremantle" });
  // Squadron scope shows the existing native Squadron Dashboard, not the
  // Wing/National command sections — "Do not remove existing Squadron
  // dashboard functions" is satisfied by reusing it as-is, not duplicating it.
  await expect(page.getByText("A — TONIGHT & THIS WEEK")).toBeVisible({ timeout: 10000 });
  await expect(page.getByText("Enter Intervention Mode (for writes)")).toBeVisible();
});

// 4. Wing Administrator opens Wing dashboard.
test("Wing Administrator opens the Wing Training Dashboard for their own Wing", async ({ page }) => {
  await loginWing(page, "ADMIN7WG");
  await expect(page.locator(".ph-sub", { hasText: "7 Wing" })).toBeVisible();
  await expect(page.getByText("NEXT PARADE NIGHT READINESS")).toBeVisible();
  // No Proxy/Intervention Mode required to view.
  await expect(page.locator(".mode-banner.show")).toHaveCount(0);
});

// 5. Wing Administrator drills into a Squadron (existing Squadron Comparison
// table below the new Training Dashboard sections — unchanged behaviour).
test("Wing Administrator can still use the existing Squadron Comparison drill-down", async ({ page }) => {
  await loginWing(page, "ADMIN7WG");
  await expect(page.getByText("Squadron Comparison", { exact: true })).toBeVisible();
  // #cmd-dash-wing (the new Training Dashboard) renders before #wing-dash (the
  // pre-existing Squadron Comparison table) in the page, and both have their
  // own "703" .drow rows — scope to #wing-dash so this exercises the
  // pre-existing drill-down, not the new readiness matrix's row.
  await page.locator("#wing-dash .drow", { hasText: "703" }).first().click();
  await expect(page.locator("#wing-drill")).toHaveClass(/show/);
});

// 11. Every graph drill-down opens the correct filtered evidence.
test("Readiness matrix row click opens the correct unit's evidence panel", async ({ page }) => {
  await loginNational(page, "SYSADMIN2026");
  await page.locator("#sa-scope-wing").selectOption({ label: "7WG — 7 Wing (Western Australia)" });
  await expect(page.locator("#cmd-dash-wing table").first()).toBeVisible({ timeout: 10000 });
  await page.locator("#cmd-dash-wing tr.drow", { hasText: "703" }).first().click();
  const panel = page.locator("#cmd-drill-wing");
  await expect(panel).toHaveClass(/show/);
  await expect(panel).toContainText("703");
  await expect(panel).toContainText("next parade night readiness");
});

// 12. No graph shows confirmed zero for missing data.
test("A unit with no upcoming parade night shows 'Data not available', never a fabricated 0%/100%", async ({ page }) => {
  await loginNational(page, "SYSADMIN2026");
  await page.locator("#sa-scope-wing").selectOption({ label: "7WG — 7 Wing (Western Australia)" });
  const table = page.locator("#cmd-dash-national table, #cmd-dash-wing table").first();
  await expect(table).toBeVisible({ timeout: 10000 });
  // 701 has no seeded parade night data — its row must read "Data not
  // available" for the confirmation columns, not a bare 0.
  const row701 = table.locator("tr", { hasText: "701" }).first();
  await expect(row701).toContainText("Data not available");
});

// Purpose/Measure/Action metadata, required on every chart.
test("Every Section A/B chart exposes Purpose, Measure and Action via the info toggle", async ({ page }) => {
  await loginNational(page, "SYSADMIN2026");
  const firstToggle = page.getByRole("button", { name: "ℹ Purpose" }).first();
  await firstToggle.click();
  const panel = page.locator('[id^="cmd-info-"]:visible').first();
  await expect(panel).toContainText("Purpose:");
  await expect(panel).toContainText("Measure:");
  await expect(panel).toContainText("Action:");
});

// Accessibility: no console errors, keyboard-reachable period control.
test("Training Dashboard loads with no console errors and a keyboard-accessible period control", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", msg => { if (msg.type() === "error") errors.push(msg.text()); });
  page.on("pageerror", err => errors.push(String(err)));
  await loginNational(page, "SYSADMIN2026");
  await page.waitForTimeout(1500);
  expect(errors, `Console errors: ${errors.join("; ")}`).toEqual([]);
  const periodSelect = page.locator("#cmd-window-sel");
  await expect(periodSelect).toBeVisible();
  await periodSelect.focus();
  await expect(periodSelect).toBeFocused();
});

// Mobile layout — no horizontal scroll introduced by the new dashboard content.
// Scoped to `.main` (this feature's own render target), not the whole document:
// the app chrome (`.topbar`) has a pre-existing horizontal-overflow issue at this
// viewport width on every page of the app, predating this branch (present
// identically on `main`) — out of scope for the Sections A+B dashboard work and
// not introduced or worsened by it. Asserting on `document.documentElement`
// would fail on that unrelated, already-broken chrome rather than verifying
// what this feature is responsible for.
test.describe("Mobile viewport", () => {
  test.use({ viewport: { width: 390, height: 844 } });
  test("Training Dashboard content renders without introducing horizontal scroll within .main", async ({ page }) => {
    await loginNational(page, "SYSADMIN2026");
    const widths = await page.evaluate(() => {
      const main = document.querySelector("main.main") as HTMLElement;
      return { scrollWidth: main.scrollWidth, clientWidth: main.clientWidth };
    });
    expect(widths.scrollWidth).toBeLessThanOrEqual(widths.clientWidth + 4); // small tolerance for scrollbar rounding
  });
});

// T2-04 / T2-05 — wing-cancellation-trend and wing-not-delivered endpoints are
// wired to Wing dashboard cards (renderWing()). Both endpoints always render a
// card: either a data table (when sessions exist) or a green no-data state.
test("wing_admin sees T2-04 Cancellation Trend card in #wing-dash", async ({ page }) => {
  await loginWing(page, "ADMIN7WG");
  // The card is rendered in #wing-dash (renderWing()), not #cmd-dash-wing.
  // Its ctitle contains "Cancellation Trend" regardless of whether sessions
  // were cancelled (data table) or not (green status line).
  const wingDash = page.locator("#wing-dash");
  await expect(wingDash.getByText("Cancellation Trend", { exact: false })).toBeVisible({ timeout: 5000 });
  // Confirm either data or no-data state is rendered — not a blank container.
  const hasTable = await wingDash.locator("table").count();
  const hasNoDataMsg = await wingDash.getByText("No cancelled sessions", { exact: false }).count();
  expect(hasTable + hasNoDataMsg, "T2-04 card must show a table or a no-data message").toBeGreaterThan(0);
});

test("wing_admin sees T2-05 Not-Delivered Sessions card in #wing-dash", async ({ page }) => {
  await loginWing(page, "ADMIN7WG");
  const wingDash = page.locator("#wing-dash");
  await expect(wingDash.getByText("Not-Delivered Sessions", { exact: false })).toBeVisible({ timeout: 5000 });
  const hasTable = await wingDash.locator("table").count();
  const hasNoDataMsg = await wingDash.getByText("No not-delivered sessions", { exact: false }).count();
  expect(hasTable + hasNoDataMsg, "T2-05 card must show a table or a no-data message").toBeGreaterThan(0);
});

// ── Section C — System Adoption Analytics (DASH-10) ─────────────────────────

test("DASH-10: /api/dashboard/adoption returns correct shape for wing_admin", async ({ page }) => {
  await loginWing(page, "ADMIN7WG");
  const base = LOCAL_API_BASE || "http://localhost:8000";
  const token = await page.evaluate(() => sessionStorage.getItem("aafc_token") ?? "");

  const resp = await page.request.get(`${base}/api/dashboard/adoption?period=30d`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(resp.ok()).toBe(true);
  const body = await resp.json();
  expect(Array.isArray(body.squadrons)).toBe(true);
  expect(typeof body.period).toBe("string");
  if (body.squadrons.length > 0) {
    const sq = body.squadrons[0];
    for (const field of ["squadron_id", "squadron_code", "last_activity"]) {
      expect(sq).toHaveProperty(field);
    }
  }
});

test("DASH-10: Section C appears in wing command dashboard", async ({ page }) => {
  await loginWing(page, "ADMIN7WG");
  const wingDash = page.locator("#wing-dash");
  // Section C — System Adoption heading should appear after the command dashboard loads
  const sectionC = wingDash.getByText(/system adoption/i);
  await expect(sectionC).toBeVisible({ timeout: 10000 });
});
