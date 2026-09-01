import { test, expect, type Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// CLASS-09: the Cadets page (/cadets, full-app-mode route -- same
// deployment-topology limitation as WeeklyProgram.tsx's /weekly-program,
// §48: unreachable in the deployed module-mode Planning Workspace preview,
// only rendered in local dev) gains a "Manage" button per Cadet opening
// CadetClassMembershipModal, backed by the new
// GET/POST /api/cadets/{id}/class-memberships endpoints.

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

test("Cadets page: Manage opens the membership modal, adding a class shows it, ending it removes it", async ({ page }) => {
  const hdr = await authHeader(page, ADMIN_CODE);
  const suffix = String(Date.now());

  const me = await (await page.request.get(`${API_BASE}/api/auth/me`, { headers: hdr })).json();
  const sqnId = me.session.squadron_id as string;

  const years = await (await page.request.get(`${API_BASE}/api/planning/years`, { headers: hdr })).json();
  const yearId = years[0].planning_year_id as string;

  const stageName = `CLASS-09-E2E-${suffix}`;
  const stageRes = await page.request.post(`${API_BASE}/api/curriculum/phases`, {
    data: { name: stageName, display_name: stageName, scope_level: "squadron", squadron_id: sqnId },
    headers: hdr,
  });
  expect(stageRes.ok()).toBe(true);
  const stageId = (await stageRes.json()).phase_id as string;

  const className = `E2E Membership Class ${suffix}`;
  const classRes = await page.request.post(`${API_BASE}/api/training-classes`, {
    data: { training_year_id: yearId, training_stage_id: stageId, display_name: className },
    headers: hdr,
  });
  expect(classRes.ok()).toBe(true);
  const classId = (await classRes.json()).training_class_id as string;

  // authHeader()'s login call above already set the aafc_session fallback
  // cookie in this page's own browser context -- goto() auto-resumes the
  // session, matching the pattern established throughout CLASS-05/06/09.
  await page.goto("/cadets");
  await expect(page.getByRole("heading", { name: "Cadets" })).toBeVisible({ timeout: 10000 });

  const firstManageBtn = page.getByRole("button", { name: "Manage" }).first();
  await expect(firstManageBtn).toBeVisible({ timeout: 8000 });
  await firstManageBtn.click();

  const modal = page.getByRole("dialog");
  await expect(modal).toBeVisible({ timeout: 5000 });

  await modal.locator("#ccm-class-select").selectOption({ label: className });
  await modal.getByRole("button", { name: "Add" }).click();

  const row = modal.locator("li", { hasText: className });
  await expect(row).toBeVisible({ timeout: 8000 });

  await row.getByRole("button", { name: "End membership" }).click();
  await expect(row).toBeHidden({ timeout: 8000 });
  await expect(modal.getByText("Not currently a member of any Training Class.")).toBeVisible({ timeout: 5000 });

  // Cleanup.
  await page.request.delete(`${API_BASE}/api/training-classes/${classId}`, { headers: hdr });
  await page.request.post(`${API_BASE}/api/curriculum/phases/${stageId}/archive`, { headers: hdr });
});
