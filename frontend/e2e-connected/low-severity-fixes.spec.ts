import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// Low-severity UI/UX fixes from the ADDENDUM UI/UX audit (2026-08-06):
// REM-92 (Weekly Program empty state) and REM-91 (System Console build
// fingerprint fallback for the unresolved local-dev placeholder).

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

test.beforeAll(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

async function loginSquadron(page: Page, code: string, role: "sqn_admin" | "sqn_general" = "sqn_admin") {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => {
      (window as any).AAFC_API_BASE = base;
    }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("squadron");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-sqn-select").selectOption("703");
  await page.locator("#auth-role").selectOption(role);
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill(code);
  await page.locator("#auth-btn").click();
  await expect(page.locator("#app")).toBeVisible({ timeout: 10000 });
}

test("REM-92: Weekly Program shows guidance instead of a bare blank area before a parade night is chosen", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await page.evaluate(() => (window as any).nav("weekly-program"));
  // Squadron 703 has seeded parade nights, so this exercises the "choose one"
  // branch specifically (the "no parade nights exist yet" branch is a
  // simple, low-risk conditional on the same data already used elsewhere on
  // this page -- verified via code review, not separately seeded here).
  await expect(page.locator("#wp-content")).toContainText(/choose a parade night/i, { timeout: 8000 });
});

test("REM-91: System Console shows a friendly build label, not the literal unresolved placeholder", async ({ page }) => {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => {
      (window as any).AAFC_API_BASE = base;
    }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("national");
  await page.locator("#auth-role").selectOption("system_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill("SYSADMIN2026");
  await page.locator("#auth-btn").click();
  await expect(page.locator("#app")).toBeVisible({ timeout: 10000 });
  await page.evaluate(() => (window as any).nav("system-console"));
  const commitEl = page.locator("#sc-build-commit");
  await expect(commitEl).toBeVisible({ timeout: 8000 });
  await expect(commitEl).not.toContainText("__APP_BUILD__");
  await expect(commitEl).toContainText("(local build)");
});

test("WRITE-06: facilitator name fields use Defence Writing Manual's Given/Family name labelling", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await page.evaluate(() => (window as any).nav("facilitators"));
  await expect(page.locator("#fac-tbody tr").first()).toBeVisible();
  // Table header labels.
  await expect(page.locator("thead").getByRole("columnheader", { name: "Given Name" })).toBeVisible();
  await expect(page.locator("thead").getByRole("columnheader", { name: "Family Name" })).toBeVisible();
  // Add Facilitator modal labels.
  await page.locator("button.btn.btn-dk.admin-el").filter({ hasText: "+ Add Facilitator" }).click();
  await expect(page.locator("#m-add-fac")).toBeVisible();
  await expect(page.locator("#m-add-fac")).toContainText("Given Name");
  await expect(page.locator("#m-add-fac")).toContainText("Family Name");
  await expect(page.locator("#m-add-fac")).not.toContainText("First Name");
  await expect(page.locator("#m-add-fac")).not.toContainText("Last Name");
});

test("WRITE-03: 'Saved at' timestamps use 24-hour time, not 12-hour am/pm", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await page.evaluate(() => (window as any).nav("facilitators"));
  await expect(page.locator("#fac-tbody tr").first()).toBeVisible();
  await page.locator("button.btn.btn-dk.admin-el").filter({ hasText: "+ Add Facilitator" }).click();
  await expect(page.locator("#m-add-fac")).toBeVisible();
  const suffix = String(Date.now());
  await page.locator("#fac-first").fill(`WRITE03-${suffix}`);
  await page.locator("#fac-last").fill(`Time-${suffix}`);
  await page.locator("#fac-save-btn").click();
  await expect(page.locator("#m-add-fac")).toBeHidden({ timeout: 8000 });
  // #fac-save-state was set to "Saved at HH:MM" just before the modal closed --
  // read it from the toast instead, which carries the same "Facilitator added
  // at HH:MM." text and survives after the modal itself is gone.
  const toast = page.locator(".toast-region");
  await expect(toast).toContainText(/added at \d{2}:\d{2}\./i, { timeout: 5000 });
  await expect(toast).not.toContainText(/am\.|pm\./i);

  // Cleanup.
  const facs = await page.evaluate(async () => {
    const r = await (window as any).api("/api/facilitators");
    return r;
  });
  const created = facs.find((f: { last_name?: string }) => f.last_name === `Time-${suffix}`);
  if (created) {
    await page.request.delete(`${LOCAL_API_BASE || "http://localhost:8000"}/api/facilitators/${created.facilitator_id}`, {
      headers: { Authorization: `Bearer ${await page.evaluate(() => sessionStorage.getItem("aafc_token"))}` },
    });
  }
});

test("MBACK-06: Per-Class CSV export button is visible in Mission Backlog for sqn_admin", async ({ page }) => {
  // MBACK-06: exportPerClassDeliveryCSV() — sqn_admin must be able to download
  // a per-class delivery summary from the Mission Backlog filter bar.
  await loginSquadron(page, "ADMIN703");
  await page.evaluate(() => (window as any).nav("activities"));
  // Wait for the missions filters card to appear — this requires loadMissions()
  // to complete, which in turn requires _loadPlanningYears() to return a year ID.
  await expect(page.locator("#missions-filters-card")).toBeVisible({ timeout: 12000 });
  await expect(page.locator("button", { hasText: "Per-Class CSV" })).toBeVisible({ timeout: 5000 });
});

test("HELP-01: Contextual tooltip buttons are present with descriptive data-tip text", async ({ page }) => {
  // HELP-01: .ht buttons use data-tip for contextual help — present on the
  // Mission Backlog header and the Training Class add/edit forms.
  await loginSquadron(page, "ADMIN703");
  await page.evaluate(() => (window as any).nav("activities"));
  await expect(page.locator("#missions-filters-card")).toBeVisible({ timeout: 12000 });
  // The Mission Backlog section header has a .ht button with data-tip text.
  const htBtn = page.locator("#missions-filters-card .ht").first();
  await expect(htBtn).toBeVisible();
  const tip = await htBtn.getAttribute("data-tip");
  expect(tip).toBeTruthy();
  expect(tip!.length).toBeGreaterThan(20);
});

test("HELP-04: Readiness checklist section is visible on the dashboard when a parade night has sessions", async ({ page }) => {
  // HELP-04: _renderTonightReadiness() renders a "Readiness checklist" section
  // beneath the session list when sessions_total > 0.  With 0 sessions it
  // returns the "Not planned" early-exit card instead.  The test seeds a parade
  // night for today's date (earliest upcoming, so the dashboard picks it as
  // "Tonight") plus one session, then navigates to the dashboard and confirms
  // the checklist section is visible.
  await loginSquadron(page, "ADMIN703");
  const base = LOCAL_API_BASE || "http://localhost:8000";
  const token = await page.evaluate(() => sessionStorage.getItem("aafc_token") ?? "");
  const auth = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  // Seed a parade night for today so _tonight_readiness picks it as the nearest upcoming.
  const todayDate = new Date().toISOString().slice(0, 10);
  const pnRes = await page.request.post(`${base}/api/parade-nights`, {
    data: { date: todayDate, parade_type: "normal" },
    headers: auth,
  });
  // Accept both 200 (created) and 409 (already exists — use existing).
  const pnBody = await pnRes.json();
  const pnId: string = pnRes.ok() ? pnBody.parade_night_id : pnBody.existing_id ?? pnBody.parade_night_id;

  if (pnId) {
    // Add one session so planning_status is not "not_planned".
    await page.request.post(`${base}/api/sessions`, {
      data: { parade_night_id: pnId, period_number: 99 },
      headers: auth,
    });
  }

  await page.evaluate(() => (window as any).loadData?.());
  await page.evaluate(() => (window as any).nav?.("dashboard"));
  const tonight = page.locator("#dash-tonight-section");
  await expect(tonight).toBeVisible({ timeout: 10000 });
  await expect(tonight).toContainText("Readiness checklist", { timeout: 8000 });
});

test("HELP-05: 'What Changed?' activity feed card is present on the Needs Attention page", async ({ page }) => {
  // HELP-05: GET /api/recent-changes — the card with the day-range selector and
  // refresh button must be present and the rc-feed div must exist.
  await loginSquadron(page, "ADMIN703");
  await page.evaluate(() => (window as any).nav("action-items"));
  // The Needs Attention page header must be visible first.
  await expect(page.locator(".ph-title", { hasText: "Needs Attention" })).toBeVisible({ timeout: 8000 });
  // The What Changed? card must be present.
  await expect(page.locator(".ctitle", { hasText: "What Changed?" })).toBeVisible({ timeout: 5000 });
  // The activity feed div and day-range selector must both be in the DOM.
  await expect(page.locator("#rc-feed")).toBeVisible();
  await expect(page.locator("#rc-days")).toBeVisible();
});

test("MBACK-04: '↗ View PN' button is visible in Mission Backlog for a scheduled mission", async ({ page }) => {
  // MBACK-04: navToScheduledPN(date) is wired to an "↗ View PN" button rendered
  // in the Scheduled column of the Mission Backlog table for any mission that has
  // a scheduled session (parade_date is non-empty in the session summary).
  // The seeded data for squadron 703 includes sessions on parade nights linked to
  // the 2026 planning year, so at least one mission should have a schedDate and
  // show this button.
  await loginSquadron(page, "ADMIN703");
  await page.evaluate(() => (window as any).nav("activities"));
  // Wait for the missions filters card, then for the missions table body to have
  // content (not just "Loading…") with a scheduled mission's button.
  await expect(page.locator("#missions-filters-card")).toBeVisible({ timeout: 12000 });
  await expect(page.locator("button[title='Go to this parade night']").first()).toBeVisible({ timeout: 15000 });
});
