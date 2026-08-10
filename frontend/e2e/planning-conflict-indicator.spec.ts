import { test, expect, type Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// REM-39 residual: Year view and Term view (ParadeNightBlock.tsx, fed via
// fromNightSummary()) previously never received any conflict data at all --
// unlike 8-Week/2-Week/custom (which already show a per-cell dot, driven by
// a client-side heuristic) and unlike ParadeNightGridView (the single-night
// grid, which shows both a real-data header badge and a heuristic per-cell
// dot). A parade night with an unresolved backend PlanningConflict showed a
// "⚠ N" badge on the block header (night.conflict_count, already real), but
// no indicator on the specific session cell -- a user had to open the whole
// night and scan every cell to find which one. This test creates a real
// room_double_booked PlanningConflict (two sessions, same period, same
// location) and asserts the per-cell dot is visible in Year view (the
// default landing view) without opening the night.

const API_BASE = process.env.E2E_BACKEND_BASE_URL || "http://localhost:8000";
const ADMIN_CODE = "ADMIN703";

test.beforeAll(async () => {
  await resetBackendRateLimits(API_BASE);
});

async function authHeader(page: Page, code: string): Promise<Record<string, string>> {
  const r = await page.request.post(`${API_BASE}/api/auth/login`, { data: { code } });
  const token = (await r.json()).token as string;
  return { Authorization: `Bearer ${token}` };
}

async function seedRoomConflict(page: Page, hdr: Record<string, string>) {
  const suffix = String(Date.now());
  // Term 3's real WA date range for this test year (_WA_TERM_RANGES) --
  // matches the pattern already established in year-view-classes.spec.ts.
  const testYear = 2650 + (Date.now() % 50);
  const yearName = `REM-39 Conflict Test ${suffix}`;
  const yearRes = await page.request.post(`${API_BASE}/api/planning/years`, {
    data: { year: testYear, name: yearName }, headers: hdr,
  });
  expect(yearRes.ok()).toBe(true);
  const yearId = (await yearRes.json()).planning_year_id as string;

  const pnDate = `${testYear}-08-06`;
  const pdRes = await page.request.post(`${API_BASE}/api/planning/years/${yearId}/parade-dates`, {
    data: { parade_date: pnDate }, headers: hdr,
  });
  expect(pdRes.ok()).toBe(true);
  const dateId = (await pdRes.json()).parade_date_id as string;

  const locsRes = await page.request.get(`${API_BASE}/api/planning/locations`, { headers: hdr });
  const locs = await locsRes.json();
  expect(Array.isArray(locs) && locs.length > 0, "squadron 703 must have at least one seeded location").toBe(true);
  const locationId = locs[0].location_id as string;

  // Two sessions, same period, same room, different cadet groups -- the
  // second POST synchronously triggers _run_conflict_check() server-side
  // (backend/app/routers/planning.py's create_session()), which writes a
  // real room_double_booked PlanningConflict row. No separate
  // "recompute conflicts" call is needed.
  const s1 = await page.request.post(`${API_BASE}/api/planning/parade-dates/${dateId}/sessions`, {
    data: { cadet_group: "junior", session_number: 1, location_id: locationId }, headers: hdr,
  });
  expect(s1.ok()).toBe(true);
  const s2 = await page.request.post(`${API_BASE}/api/planning/parade-dates/${dateId}/sessions`, {
    data: { cadet_group: "initial", session_number: 1, location_id: locationId }, headers: hdr,
  });
  expect(s2.ok()).toBe(true);

  const conflictsRes = await page.request.get(`${API_BASE}/api/planning/years/${yearId}/conflicts`, { headers: hdr });
  const conflicts = await conflictsRes.json();
  const types = (conflicts.conflicts ?? conflicts).map((c: { conflict_type: string }) => c.conflict_type);
  expect(types, "seeding must actually produce a real room_double_booked conflict").toContain("room_double_booked");

  return { yearId, yearName };
}

async function deactivateYear(page: Page, hdr: Record<string, string>, yearId: string) {
  const curYearRes = await page.request.get(`${API_BASE}/api/planning/years/${yearId}`, { headers: hdr });
  const curYear = await curYearRes.json();
  await page.request.patch(`${API_BASE}/api/planning/years/${yearId}`, {
    data: { active_status: false, version: curYear.version }, headers: hdr,
  });
}

test("Year view shows a per-cell conflict dot for an unresolved room double-booking, without opening the night", async ({ page }) => {
  const hdr = await authHeader(page, ADMIN_CODE);
  const { yearId, yearName } = await seedRoomConflict(page, hdr);

  try {
    await page.goto("/planning");
    await expect(page.getByRole("main", { name: /planning workspace/i })).toBeVisible({ timeout: 10000 });
    await page.getByRole("button", { name: yearName }).click();

    // Year view is the default -- no click into the night should be required.
    const dot = page.locator(".pn-conflict-dot.room").first();
    await expect(dot).toBeVisible({ timeout: 10000 });
    // The same real conflict_count-driven header badge must still be present
    // (pre-existing behaviour, must not regress).
    await expect(page.locator(".pw-conflict-badge")).toBeVisible();
  } finally {
    await deactivateYear(page, hdr, yearId);
  }
});

test("Term view shows the same per-cell conflict dot", async ({ page }) => {
  const hdr = await authHeader(page, ADMIN_CODE);
  const { yearId, yearName } = await seedRoomConflict(page, hdr);

  try {
    await page.goto("/planning");
    await expect(page.getByRole("main", { name: /planning workspace/i })).toBeVisible({ timeout: 10000 });
    await page.getByRole("button", { name: yearName }).click();
    await page.getByRole("button", { name: "Term", exact: true }).click();
    // The seeded parade date (Aug 6) falls in WA Term 3 (_WA_TERM_RANGES) --
    // TermView defaults to term index 0 (T1), so the right tab must be
    // selected explicitly before the block for this date renders at all.
    await page.getByRole("button", { name: "T3", exact: true }).click();

    const dot = page.locator(".pn-conflict-dot.room").first();
    await expect(dot).toBeVisible({ timeout: 10000 });
  } finally {
    await deactivateYear(page, hdr, yearId);
  }
});
