import { test, expect } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";
import { loginPW } from "../e2e-login-helper";

test.beforeAll(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || "http://localhost:8000");
});

// Year rollover contract coverage retained here because the resulting year is
// consumed by the Planning Workspace. The UI assertion is intentionally only
// for the module-owned /planning surface; no retired full-app route is used.
const API = "/api";

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
  const RUN_ID = Date.now();

  test("sqn_admin can rollover a planning year with parade dates", async ({ page }) => {
    const hdr = await authHeader(page, "ADMIN703");
    const srcYear = 2000 + (RUN_ID % 7998);
    let yearId = "";
    let newYearId = "";

    try {
      const yr = await page.request.post(`${API}/planning/years`, {
        data: { year: srcYear, name: `${srcYear} E2E Rollover Source` },
        headers: hdr,
      });
      expect(yr.status()).toBe(200);
      yearId = (await yr.json()).planning_year_id as string;

      const gen = await page.request.post(`${API}/planning/years/${yearId}/generate-parade-dates`, {
        data: {
          weekday: 3,
          start_date: `${srcYear}-09-01`,
          end_date: `${srcYear}-11-30`,
          parade_type: "standard",
        },
        headers: hdr,
      });
      expect(gen.status()).toBe(200);
      const sourceDates = (await gen.json()).dates as string[];
      expect(sourceDates.length).toBeGreaterThan(0);

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

      const newDates = await page.request.get(`${API}/planning/years/${newYearId}/parade-dates`, { headers: hdr });
      expect(newDates.status()).toBe(200);
      const newDateList = (await newDates.json()) as { parade_date: string }[];
      const newDateStrings = newDateList.map((d) => d.parade_date);
      for (const sd of sourceDates.slice(0, 3)) {
        expect(newDateStrings).toContain(sd.replace(String(srcYear), String(srcYear + 1)));
      }

      const newHols = await page.request.get(`${API}/planning/years/${newYearId}/holidays`, { headers: hdr });
      expect(newHols.status()).toBe(200);
      const newHolList = (await newHols.json()) as { start_date: string }[];
      expect(newHolList.some((h) => h.start_date === `${srcYear + 1}-10-10`)).toBe(true);

      const srcDatesAfter = await page.request.get(`${API}/planning/years/${yearId}/parade-dates`, { headers: hdr });
      expect(srcDatesAfter.status()).toBe(200);
      const srcListAfter = (await srcDatesAfter.json()) as { parade_date: string }[];
      expect(srcListAfter.map((d) => d.parade_date)).not.toContain(`${srcYear + 1}-09-04`);
    } finally {
      if (yearId) await deactivateYear(page, hdr, yearId);
      if (newYearId) await deactivateYear(page, hdr, newYearId);
    }
  });

  test("duplicate rollover returns 409", async ({ page }) => {
    const hdr = await authHeader(page, "ADMIN703");
    const srcYear = 2100 + (RUN_ID % 7898);
    let yearId = "";
    let rolledYearId = "";

    try {
      const yr = await page.request.post(`${API}/planning/years`, {
        data: { year: srcYear, name: `${srcYear} Duplicate Rollover` }, headers: hdr,
      });
      expect(yr.status()).toBe(200);
      yearId = (await yr.json()).planning_year_id as string;

      const r1 = await page.request.post(`${API}/planning/years/${yearId}/rollover`, {
        data: { target_year: srcYear + 1 }, headers: hdr,
      });
      expect(r1.status()).toBe(200);
      rolledYearId = (await r1.json()).new_planning_year_id as string;

      const r2 = await page.request.post(`${API}/planning/years/${yearId}/rollover`, {
        data: { target_year: srcYear + 1 }, headers: hdr,
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
    const srcYear = 2200 + (RUN_ID % 7798);
    let yearId = "";

    try {
      const yr = await page.request.post(`${API}/planning/years`, {
        data: { year: srcYear, name: `${srcYear} RBAC Rollover` }, headers: adminHdr,
      });
      expect(yr.status()).toBe(200);
      yearId = (await yr.json()).planning_year_id as string;

      const r = await page.request.post(`${API}/planning/years/${yearId}/rollover`, {
        data: {}, headers: genHdr,
      });
      expect(r.status()).toBe(403);
    } finally {
      if (yearId) await deactivateYear(page, adminHdr, yearId);
    }
  });

  test("rolled-over year remains visible to the authenticated Planning Workspace", async ({ page }) => {
    await loginPW(page, "ADMIN703");
    await expect(page.locator('[role="main"][aria-label="Planning workspace"]')).toBeVisible({ timeout: 10000 });

    const hdr = await authHeader(page, "ADMIN703");
    const srcYear = 2300 + (RUN_ID % 7698);
    let yearId = "";
    let rolledYearId = "";

    try {
      const yr = await page.request.post(`${API}/planning/years`, {
        data: { year: srcYear, name: `${srcYear} PW Visibility Test` }, headers: hdr,
      });
      expect(yr.status()).toBe(200);
      yearId = (await yr.json()).planning_year_id as string;

      const rv = await page.request.post(`${API}/planning/years/${yearId}/rollover`, {
        data: { target_year: srcYear + 1 }, headers: hdr,
      });
      expect(rv.status()).toBe(200);
      rolledYearId = (await rv.json()).new_planning_year_id as string;

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
