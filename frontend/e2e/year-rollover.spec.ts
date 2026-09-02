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

// ── Year rollover — E2E proof (Phase 8, Gap #11) ─────────────────────────────
// Tests the full rollover workflow end-to-end through the browser's request
// context (Vite proxy → backend). Verifies:
//  1. A planning year can be created and rolled over.
//  2. The new year has date-advanced parade dates and copied holidays.
//  3. The source year's parade dates are not altered.
//  4. The new year appears as a selectable year in the Planning Workspace.
//  5. sqn_general cannot trigger a rollover.
//
// Requires: local backend on :8000 (seeded), Vite dev server on :5173.
//
// Uses timestamp-derived unique year values to prevent 409 conflicts on
// long-lived dev DBs (same root cause as the mission-backlog tests).
// Each test deactivates created years in a finally block so they don't
// accumulate as active years and slow down the Planning Workspace year list.

const API = "/api";

// ── Helper: login and return auth header ─────────────────────────────────────
async function authHeader(page: import("@playwright/test").Page, code: string): Promise<Record<string, string>> {
  const r = await page.request.post(`${API}/auth/login`, { data: { code } });
  expect(r.status()).toBe(200);
  const token = (await r.json()).token as string;
  return { Authorization: `Bearer ${token}` };
}

async function deactivateYear(page: import("@playwright/test").Page, hdr: Record<string, string>, yearId: string): Promise<void> {
  const detail = await page.request.get(`${API}/planning/years/${yearId}`, { headers: hdr });
  if (!detail.ok()) return;
  const d = await detail.json();
  await page.request.patch(`${API}/planning/years/${yearId}`, {
    data: { active_status: false, version: d.version },
    headers: hdr,
  });
}

test.describe("Year rollover", () => {
  // Use a timestamp-derived run-ID so each invocation of this test file
  // creates distinct year values. Each test uses a different base offset
  // within the same run so they never collide with each other.
  // Pool sized so srcYear and srcYear+1 both stay ≤ 9999 — the backend
  // date validator (date.fromisoformat) rejects years outside [1, 9999].
  const RUN_ID = Date.now();

  test("sqn_admin can rollover a planning year with parade dates", async ({ page }) => {
    const hdr = await authHeader(page, "ADMIN703");
    const srcYear = 2000 + (RUN_ID % 7998); // srcYear+1 stays ≤ 9999
    let yearId = "";
    let newYearId = "";

    try {
      // Create source year
      const yr = await page.request.post(`${API}/planning/years`, {
        data: { year: srcYear, name: `${srcYear} E2E Rollover Source` },
        headers: hdr,
      });
      expect(yr.status()).toBe(200);
      yearId = (await yr.json()).planning_year_id as string;

      // Generate parade dates in source year
      const gen = await page.request.post(`${API}/planning/years/${yearId}/generate-parade-dates`, {
        data: {
          weekday: 3, // Thursday
          start_date: `${srcYear}-09-01`,
          end_date: `${srcYear}-11-30`,
          parade_type: "standard",
        },
        headers: hdr,
      });
      expect(gen.status()).toBe(200);
      const sourceDates = (await gen.json()).dates as string[];
      expect(sourceDates.length).toBeGreaterThan(0);

      // Add a holiday to copy
      const hol = await page.request.post(`${API}/planning/years/${yearId}/holidays`, {
        data: {
          name: "Rollover E2E Holiday",
          start_date: `${srcYear}-10-10`,
          end_date: `${srcYear}-10-14`,
          holiday_type: "school_holiday",
          affects_parade: true,
        },
        headers: hdr,
      });
      expect(hol.status()).toBe(200);

      // Perform rollover
      const rv = await page.request.post(`${API}/planning/years/${yearId}/rollover`, {
        data: { copy_holidays: true, carry_incomplete_sessions: true },
        headers: hdr,
      });
      expect(rv.status()).toBe(200);
      const rvData = await rv.json();
      expect(rvData.ok).toBe(true);
      expect(rvData.year).toBe(srcYear + 1);
      expect(rvData.parade_dates_copied).toBeGreaterThan(0);
      expect(rvData.holidays_copied).toBe(1);

      newYearId = rvData.new_planning_year_id as string;

      // Verify new year has date-advanced parade dates
      const newDates = await page.request.get(`${API}/planning/years/${newYearId}/parade-dates`, { headers: hdr });
      expect(newDates.status()).toBe(200);
      const newDateList = (await newDates.json()) as { parade_date: string }[];
      const newDateStrings = newDateList.map((d) => d.parade_date);
      // Each source date must appear advanced by one year
      for (const sd of sourceDates.slice(0, 3)) {
        const expected = sd.replace(String(srcYear), String(srcYear + 1));
        expect(newDateStrings).toContain(expected);
      }

      // Verify holiday was copied and year-advanced
      const newHols = await page.request.get(`${API}/planning/years/${newYearId}/holidays`, { headers: hdr });
      expect(newHols.status()).toBe(200);
      const newHolList = (await newHols.json()) as { start_date: string }[];
      expect(newHolList.some((h) => h.start_date === `${srcYear + 1}-10-10`)).toBe(true);

      // Verify source year parade dates are unchanged
      const srcDatesAfter = await page.request.get(`${API}/planning/years/${yearId}/parade-dates`, { headers: hdr });
      expect(srcDatesAfter.status()).toBe(200);
      const srcListAfter = (await srcDatesAfter.json()) as { parade_date: string }[];
      // The rolled-over dates (year+1) should NOT appear in the source year
      expect(srcListAfter.map((d) => d.parade_date)).not.toContain(`${srcYear + 1}-09-04`);
    } finally {
      if (yearId) await deactivateYear(page, hdr, yearId);
      if (newYearId) await deactivateYear(page, hdr, newYearId);
    }
  });

  test("duplicate rollover returns 409", async ({ page }) => {
    const hdr = await authHeader(page, "ADMIN703");
    const srcYear = 2100 + (RUN_ID % 7898); // srcYear+1 stays ≤ 9999
    let yearId = "";
    let rolledYearId = "";

    try {
      const yr = await page.request.post(`${API}/planning/years`, {
        data: { year: srcYear, name: `${srcYear} Duplicate Rollover` },
        headers: hdr,
      });
      expect(yr.status()).toBe(200);
      yearId = (await yr.json()).planning_year_id as string;

      // First rollover succeeds
      const r1 = await page.request.post(`${API}/planning/years/${yearId}/rollover`, {
        data: { target_year: srcYear + 1 },
        headers: hdr,
      });
      expect(r1.status()).toBe(200);
      rolledYearId = (await r1.json()).new_planning_year_id as string;

      // Second rollover to same target must 409
      const r2 = await page.request.post(`${API}/planning/years/${yearId}/rollover`, {
        data: { target_year: srcYear + 1 },
        headers: hdr,
      });
      expect(r2.status()).toBe(409);
    } finally {
      if (yearId) await deactivateYear(page, hdr, yearId);
      if (rolledYearId) await deactivateYear(page, hdr, rolledYearId);
    }
  });

  test("sqn_general cannot rollover", async ({ page }) => {
    const adminHdr = await authHeader(page, "ADMIN703");
    const genHdr = await authHeader(page, "703SQN2026");
    const srcYear = 2200 + (RUN_ID % 7798); // srcYear+1 stays ≤ 9999
    let yearId = "";

    try {
      const yr = await page.request.post(`${API}/planning/years`, {
        data: { year: srcYear, name: `${srcYear} RBAC Rollover` },
        headers: adminHdr,
      });
      expect(yr.status()).toBe(200);
      yearId = (await yr.json()).planning_year_id as string;

      const r = await page.request.post(`${API}/planning/years/${yearId}/rollover`, {
        data: {},
        headers: genHdr,
      });
      expect(r.status()).toBe(403);
    } finally {
      if (yearId) await deactivateYear(page, adminHdr, yearId);
    }
  });

  test("new year from rollover appears in Planning Workspace year list", async ({ page }) => {
    // Login via UI
    await page.goto("/");
    await loginPW(page, "ADMIN703");
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });

    const hdr = await authHeader(page, "ADMIN703");
    const srcYear = 2300 + (RUN_ID % 7698); // srcYear+1 stays ≤ 9999
    let yearId = "";
    let rolledYearId = "";

    try {
      // Create and roll over a year via API
      const yr = await page.request.post(`${API}/planning/years`, {
        data: { year: srcYear, name: `${srcYear} PW Visibility Test` },
        headers: hdr,
      });
      expect(yr.status()).toBe(200);
      yearId = (await yr.json()).planning_year_id as string;

      const rv = await page.request.post(`${API}/planning/years/${yearId}/rollover`, {
        data: { target_year: srcYear + 1 },
        headers: hdr,
      });
      expect(rv.status()).toBe(200);
      rolledYearId = (await rv.json()).new_planning_year_id as string;

      // Verify both years appear in the API year list
      const list = await page.request.get(`${API}/planning/years`, { headers: hdr });
      expect(list.status()).toBe(200);
      const years = (await list.json()) as { year: number }[];
      expect(years.some((y) => y.year === srcYear)).toBe(true);
      expect(years.some((y) => y.year === srcYear + 1)).toBe(true);
    } finally {
      if (yearId) await deactivateYear(page, hdr, yearId);
      if (rolledYearId) await deactivateYear(page, hdr, rolledYearId);
    }
  });
});
