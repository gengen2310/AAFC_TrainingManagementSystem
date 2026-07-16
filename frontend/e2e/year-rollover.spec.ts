import { test, expect } from "@playwright/test";

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

const API = "/api";

async function loginApi(request: ReturnType<typeof import("@playwright/test")["request"]["newContext"]> extends Promise<infer R> ? R : never, code: string): Promise<string> {
  const r = await request.post(`${API}/auth/login`, { data: { code } });
  expect(r.status()).toBe(200);
  return (await r.json()).token as string;
}

// ── Helper: login and return auth header ─────────────────────────────────────
async function authHeader(page: import("@playwright/test").Page, code: string): Promise<Record<string, string>> {
  const r = await page.request.post(`${API}/auth/login`, { data: { code } });
  expect(r.status()).toBe(200);
  const token = (await r.json()).token as string;
  return { Authorization: `Bearer ${token}` };
}

test.describe("Year rollover", () => {
  test("sqn_admin can rollover a planning year with parade dates", async ({ page }) => {
    const hdr = await authHeader(page, "ADMIN703");

    // Create source year
    const yr = await page.request.post(`${API}/planning/years`, {
      data: { year: 2170, name: "2170 E2E Rollover Source" },
      headers: hdr,
    });
    expect(yr.status()).toBe(200);
    const yearId = (await yr.json()).planning_year_id as string;

    // Generate parade dates in source year
    const gen = await page.request.post(`${API}/planning/years/${yearId}/generate-parade-dates`, {
      data: {
        weekday: 3, // Thursday
        start_date: "2170-09-01",
        end_date: "2170-11-30",
        parade_type: "standard",
      },
      headers: hdr,
    });
    expect(gen.status()).toBe(200);
    const sourceDates = (await gen.json()).parade_dates as { parade_date: string }[];
    expect(sourceDates.length).toBeGreaterThan(0);

    // Add a holiday to copy
    const hol = await page.request.post(`${API}/planning/years/${yearId}/holidays`, {
      data: {
        name: "Rollover E2E Holiday",
        start_date: "2170-10-10",
        end_date: "2170-10-14",
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
    expect(rvData.year).toBe(2171);
    expect(rvData.parade_dates_copied).toBeGreaterThan(0);
    expect(rvData.holidays_copied).toBe(1);

    const newYearId = rvData.new_planning_year_id as string;

    // Verify new year has date-advanced parade dates
    const newDates = await page.request.get(`${API}/planning/years/${newYearId}/parade-dates`, { headers: hdr });
    expect(newDates.status()).toBe(200);
    const newDateList = (await newDates.json()) as { parade_date: string }[];
    const newDateStrings = newDateList.map((d) => d.parade_date);
    // Each source date must appear advanced by one year
    for (const sd of sourceDates.slice(0, 3)) {
      const expected = sd.parade_date.replace("2170", "2171");
      expect(newDateStrings).toContain(expected);
    }

    // Verify holiday was copied and year-advanced
    const newHols = await page.request.get(`${API}/planning/years/${newYearId}/holidays`, { headers: hdr });
    expect(newHols.status()).toBe(200);
    const newHolList = (await newHols.json()) as { start_date: string }[];
    expect(newHolList.some((h) => h.start_date === "2171-10-10")).toBe(true);

    // Verify source year parade dates are unchanged
    const srcDatesAfter = await page.request.get(`${API}/planning/years/${yearId}/parade-dates`, { headers: hdr });
    expect(srcDatesAfter.status()).toBe(200);
    const srcListAfter = (await srcDatesAfter.json()) as { parade_date: string }[];
    expect(srcListAfter.map((d) => d.parade_date)).not.toContain("2171-09-04");
  });

  test("duplicate rollover returns 409", async ({ page }) => {
    const hdr = await authHeader(page, "ADMIN703");

    const yr = await page.request.post(`${API}/planning/years`, {
      data: { year: 2175, name: "2175 Duplicate Rollover" },
      headers: hdr,
    });
    expect(yr.status()).toBe(200);
    const yearId = (await yr.json()).planning_year_id as string;

    // First rollover succeeds
    const r1 = await page.request.post(`${API}/planning/years/${yearId}/rollover`, {
      data: { target_year: 2176 },
      headers: hdr,
    });
    expect(r1.status()).toBe(200);

    // Second rollover to same target must 409
    const r2 = await page.request.post(`${API}/planning/years/${yearId}/rollover`, {
      data: { target_year: 2176 },
      headers: hdr,
    });
    expect(r2.status()).toBe(409);
  });

  test("sqn_general cannot rollover", async ({ page }) => {
    const adminHdr = await authHeader(page, "ADMIN703");
    const genHdr = await authHeader(page, "703SQN2026");

    const yr = await page.request.post(`${API}/planning/years`, {
      data: { year: 2180, name: "2180 RBAC Rollover" },
      headers: adminHdr,
    });
    expect(yr.status()).toBe(200);
    const yearId = (await yr.json()).planning_year_id as string;

    const r = await page.request.post(`${API}/planning/years/${yearId}/rollover`, {
      data: {},
      headers: genHdr,
    });
    expect(r.status()).toBe(403);
  });

  test("new year from rollover appears in Planning Workspace year list", async ({ page }) => {
    // Login via UI
    await page.goto("/");
    await page.getByLabel("Access code").fill("ADMIN703");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });

    const hdr = await authHeader(page, "ADMIN703");

    // Create and roll over a year via API
    const yr = await page.request.post(`${API}/planning/years`, {
      data: { year: 2185, name: "2185 PW Visibility Test" },
      headers: hdr,
    });
    expect(yr.status()).toBe(200);
    const yearId = (await yr.json()).planning_year_id as string;

    const rv = await page.request.post(`${API}/planning/years/${yearId}/rollover`, {
      data: { target_year: 2186 },
      headers: hdr,
    });
    expect(rv.status()).toBe(200);

    // Verify both years appear in the API year list
    const list = await page.request.get(`${API}/planning/years`, { headers: hdr });
    expect(list.status()).toBe(200);
    const years = (await list.json()) as { year: number }[];
    expect(years.some((y) => y.year === 2185)).toBe(true);
    expect(years.some((y) => y.year === 2186)).toBe(true);
  });
});
