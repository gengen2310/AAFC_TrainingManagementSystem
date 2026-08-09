import { test, expect, type Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// CLASS-05: Mission Backlog's new per-Training-Class "Classes" column
// (PlanningBottomDrawer.tsx's BacklogContent), driven by the backend's
// additive class_breakdown/unassigned_session_count fields on
// GET /api/planning/years/{id}/missions. Seeds real data via direct API
// calls (mirroring backend/tests/test_mission_backlog_class_awareness.py),
// then verifies the real rendered UI.
//
// Uses a Planning Year `year` value far above anything else in this suite
// (2600+, timestamp-varied) for the same reason the backend tests moved to
// 2401-2407: a plain POST /api/parade-nights auto-links to whichever active
// PlanningYear has the HIGHEST `year` for the squadron (REM-129) -- and this
// suite's backend is a long-lived, reused local dev DB (not a fresh
// throwaway DB per run), so a leftover active year from an earlier run
// could otherwise steal that link, or an exact `year` tie with one could
// resolve unpredictably. The created year is deactivated in a `finally`
// block so it can't linger and steal the link from a future run even if
// this test itself fails.

// The deployed preview service (module mode) serves the SPA only -- its own
// origin does not proxy /api/* to the backend the way the local Vite dev
// server does. Seeding calls must therefore target the backend's own
// absolute URL when running against staging (E2E_BACKEND_BASE_URL, set by
// playwright.planning.staging.native.config.ts), same as the API_BASE
// pattern already established in e2e-connected/*.spec.ts.
const API_BASE = process.env.E2E_BACKEND_BASE_URL || "http://localhost:8000";

test.beforeAll(async () => {
  await resetBackendRateLimits(API_BASE);
});

const ADMIN_CODE = "ADMIN703";

async function authHeader(page: Page, code: string): Promise<Record<string, string>> {
  const r = await page.request.post(`${API_BASE}/api/auth/login`, { data: { code } });
  const token = (await r.json()).token as string;
  return { Authorization: `Bearer ${token}` };
}

test("Mission Backlog shows a per-Training-Class chip for a session's real audience assignment", async ({ page }) => {
  const hdr = await authHeader(page, ADMIN_CODE);
  const suffix = String(Date.now());

  const meRes = await page.request.get(`${API_BASE}/api/auth/me`, { headers: hdr });
  const me = await meRes.json();
  const sqnId = me.session.squadron_id as string;
  const wingId = me.session.wing_id as string;

  // create_parade()'s plain-ParadeNight-create path (REM-129) auto-links to
  // whichever active PlanningYear has the HIGHEST `year` value for the
  // squadron -- a fixed year value here risks an exact tie with a leftover
  // active year from an earlier (e.g. failed) run of this same test against
  // this long-lived local dev backend, and ties resolve to an
  // indeterminate row, not necessarily this run's own year (confirmed: this
  // caused a real, reproducible failure during development of this test,
  // where the new Session silently linked to a stale leftover year instead
  // of this run's). A value derived from the current timestamp is unique
  // per run, not just per test file.
  const uniqueYear = 2600 + (Date.now() % 5000);
  const yearName = `CLASS-05 PW Test ${suffix}`;
  const yearRes = await page.request.post(`${API_BASE}/api/planning/years`, {
    data: { year: uniqueYear, name: yearName }, headers: hdr,
  });
  expect(yearRes.ok()).toBe(true);
  const year = await yearRes.json();
  const yearId = year.planning_year_id as string;

  const stageName = `CLASS-05-PW-${suffix}`;
  const stageRes = await page.request.post(`${API_BASE}/api/curriculum/phases`, {
    data: { name: stageName, display_name: stageName, scope_level: "squadron", squadron_id: sqnId },
    headers: hdr,
  });
  expect(stageRes.ok()).toBe(true);
  const stageId = (await stageRes.json()).phase_id as string;

  const className = `PW Chip Class ${suffix}`;
  const classRes = await page.request.post(`${API_BASE}/api/training-classes`, {
    data: { training_year_id: yearId, training_stage_id: stageId, display_name: className },
    headers: hdr,
  });
  expect(classRes.ok()).toBe(true);
  const classId = (await classRes.json()).training_class_id as string;

  const code = `PW05${suffix.slice(-6)}`;
  const ciRes = await page.request.post(`${API_BASE}/api/curriculum`, {
    data: {
      code, title: "PW Chip Test Item", phase: stageName,
      learning_hub_url: "https://example.invalid/pw-chip-test",
    },
    headers: hdr,
  });
  expect(ciRes.ok()).toBe(true);
  const ciId = (await ciRes.json()).curriculum_id as string;

  // A fixed date risks colliding with another squadron-703 parade night
  // already seeded/created by an earlier run against this long-lived local
  // dev backend -- derive one from the current time instead, matching the
  // date-uniqueness approach already used elsewhere in this program's own
  // test suites (e.g. e2e-connected/session-training-classes.spec.ts).
  const pnDate = new Date(2100, 3, 1 + (Date.now() % 300)).toISOString().slice(0, 10);
  const pnRes = await page.request.post(`${API_BASE}/api/parade-nights`, {
    data: { squadron_id: sqnId, wing_id: wingId, date: pnDate, parade_type: "normal" },
    headers: hdr,
  });
  expect(pnRes.ok()).toBe(true);
  const pnId = (await pnRes.json()).parade_night_id as string;

  const sessRes = await page.request.post(`${API_BASE}/api/sessions`, {
    data: { parade_night_id: pnId, period_number: 1, cadet_group: "senior", curriculum_item_id: ciId },
    headers: hdr,
  });
  expect(sessRes.ok()).toBe(true);
  const sid = (await sessRes.json()).session_id as string;

  const editRes = await page.request.put(`${API_BASE}/api/sessions/${sid}`, {
    data: {
      parade_night_id: pnId, period_number: 1, cadet_group: "senior",
      curriculum_item_id: ciId, status: "delivered",
    },
    headers: hdr,
  });
  expect(editRes.ok()).toBe(true);

  const audRes = await page.request.put(`${API_BASE}/api/sessions/${sid}/audience`, {
    data: { training_class_ids: [classId] }, headers: hdr,
  });
  expect(audRes.ok()).toBe(true);

  // try/finally so a failed assertion below still deactivates this year --
  // an active leftover year (from an earlier failed run) is what caused the
  // REM-129 tie-break bug documented above, so cleanup must run even on
  // failure, not only on the happy path.
  try {
    // ── Real UI verification ────────────────────────────────────────────
    // authHeader()'s page.request.post(...) call above already set the
    // aafc_session fallback cookie in this page's own browser context
    // (page.request shares the context's cookie jar with page) -- a plain
    // goto("/") auto-resumes that session via the cookie fallback and never
    // renders the login form at all (architecture.md's documented
    // sessionStorage-primary/cookie-fallback handoff), so there is no login
    // form left to fill in here. Go straight to the authenticated page.
    await page.goto("/planning");
    await expect(page.getByRole("main", { name: /planning workspace/i })).toBeVisible({ timeout: 10000 });

    await page.getByRole("button", { name: yearName }).click();

    await page.getByText("Activities ▲").click();
    await page.getByRole("button", { name: "Mission Backlog" }).click();
    await expect(page.getByText("Rec. Term")).toBeVisible({ timeout: 8000 });

    // Default status filter is "Unscheduled" -- this item is delivered, so
    // switch to "All statuses" to see it.
    await page.locator("select").first().selectOption("");
    await page.getByPlaceholder("Search code or title…").fill(code);

    const row = page.locator("table tr").filter({ hasText: code });
    await expect(row).toBeVisible({ timeout: 8000 });
    const chip = row.getByText(className, { exact: true });
    await expect(chip).toBeVisible({ timeout: 8000 });
    await expect(chip).toHaveAttribute("title", new RegExp(`${className}: Scheduled`));
  } finally {
    // Clean up -- archive the class and deactivate the year so nothing here
    // lingers as an active high-`year` PlanningYear for a future test run.
    await page.request.delete(`${API_BASE}/api/training-classes/${classId}`, { headers: hdr });
    const curYearRes = await page.request.get(`${API_BASE}/api/planning/years/${yearId}`, { headers: hdr });
    const curYear = await curYearRes.json();
    await page.request.patch(`${API_BASE}/api/planning/years/${yearId}`, {
      data: { active_status: false, version: curYear.version }, headers: hdr,
    });
  }
});
