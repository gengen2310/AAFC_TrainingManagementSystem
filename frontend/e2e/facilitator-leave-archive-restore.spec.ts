import { test, expect, type Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// REM-133 (6th instance): PlanningFacilitatorLeave removal existed with no
// restore counterpart, and archived leave periods were entirely invisible
// (no include_archived param, no way to even see one to restore it). Added
// a "Show archived" toggle plus a Restore button on the Facilitators tab's
// leave section (PlanningBottomDrawer.tsx's FacilitatorLeaveSection --
// the only reachable facilitator-leave UI in module mode, per GAP-14's
// own comment on this same file).

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

test("an archived leave period is hidden by default, visible via Show archived, and Restore brings it back", async ({ page }) => {
  const hdr = await authHeader(page, ADMIN_CODE);
  const suffix = String(Date.now());

  const facRes = await page.request.post(`${API_BASE}/api/facilitators`, {
    data: { last_name: `RestoreTest ${suffix}` }, headers: hdr,
  });
  expect(facRes.ok()).toBe(true);
  const facId = (await facRes.json()).facilitator_id as string;

  const leaveRes = await page.request.post(`${API_BASE}/api/planning/facilitators/${facId}/leave`, {
    data: { start_date: "2099-08-01", end_date: "2099-08-07", reason: `E2E REM-133 ${suffix}` },
    headers: hdr,
  });
  expect(leaveRes.ok()).toBe(true);
  const leaveId = (await leaveRes.json()).leave.id as string;

  const deleteRes = await page.request.delete(`${API_BASE}/api/planning/facilitator-leave/${leaveId}`, { headers: hdr });
  expect(deleteRes.ok()).toBe(true);

  try {
    await page.goto("/planning");
    await expect(page.getByRole("main", { name: /planning workspace/i })).toBeVisible({ timeout: 10000 });

    await page.getByText("Activities ▲").click();
    await page.getByRole("button", { name: "Facilitators" }).click();
    await expect(page.getByText(`RestoreTest ${suffix}`)).toBeVisible({ timeout: 8000 });

    // Expand this facilitator's profile panel.
    await page.getByText(`RestoreTest ${suffix}`).click();
    await expect(page.getByText("Leave / Unavailability")).toBeVisible({ timeout: 5000 });

    // Hidden by default.
    await expect(page.getByText(`E2E REM-133 ${suffix}`)).not.toBeVisible();

    // Visible with "Show archived" clicked, flagged as archived.
    await page.getByRole("button", { name: "Show archived" }).click();
    const row = page.locator("div", { hasText: `E2E REM-133 ${suffix}` }).filter({ hasText: "Archived" }).last();
    await expect(row).toBeVisible({ timeout: 5000 });

    // Restore brings it back into the active (non-archived) list.
    await row.getByRole("button", { name: "Restore" }).click();
    await expect(page.getByRole("button", { name: "Hide archived" })).toBeVisible({ timeout: 5000 });
    await page.getByRole("button", { name: "Hide archived" }).click();
    await expect(page.getByText(`E2E REM-133 ${suffix}`)).toBeVisible({ timeout: 5000 });
  } finally {
    await page.request.delete(`${API_BASE}/api/planning/facilitator-leave/${leaveId}`, { headers: hdr });
    await page.request.delete(`${API_BASE}/api/facilitators/${facId}`, { headers: hdr });
  }
});
