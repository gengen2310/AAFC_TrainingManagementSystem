import { test, expect } from "@playwright/test";

// ── Navigation and route coverage ────────────────────────────────────────────
// Tests that major nav routes load and render their page heading.
// Requires backend on :8000 seeded with 703 demo data.

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Access code").fill("ADMIN703");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
});

test("Curriculum page loads", async ({ page }) => {
  await page.goto("/curriculum");
  await expect(page.getByRole("heading", { name: /curriculum/i })).toBeVisible({ timeout: 8000 });
});

test("Parade Nights page loads", async ({ page }) => {
  await page.goto("/parade-nights");
  await expect(page.getByRole("heading", { name: /parade night/i })).toBeVisible({ timeout: 8000 });
});

test("Mission Backlog (Action Items) page loads", async ({ page }) => {
  await page.goto("/action-items");
  await expect(page.getByRole("heading", { name: /mission backlog|action item/i })).toBeVisible({ timeout: 8000 });
});

test("Imports page loads", async ({ page }) => {
  await page.goto("/imports");
  await expect(page.getByRole("heading", { name: /import|activities/i })).toBeVisible({ timeout: 8000 });
});

test("Facilitators page loads", async ({ page }) => {
  await page.goto("/facilitators");
  await expect(page.getByRole("heading", { name: /facilitator/i })).toBeVisible({ timeout: 8000 });
});

test("Resources page loads", async ({ page }) => {
  await page.goto("/resources");
  await expect(page.getByRole("heading", { name: /resource|training area|equipment/i })).toBeVisible({ timeout: 8000 });
});

test("Weekly Program page loads", async ({ page }) => {
  await page.goto("/weekly-program");
  await expect(page.getByRole("heading", { name: /weekly program/i })).toBeVisible({ timeout: 8000 });
});

test("Calendar page loads", async ({ page }) => {
  await page.goto("/calendar");
  await expect(page.getByRole("heading", { name: /calendar/i })).toBeVisible({ timeout: 8000 });
});

// DEFECT-002 (general-release qualification, AL-03): recommended_term is already
// "T1".."T4" from the backend (see backend/app/models/training.py's CurriculumItem.
// recommended_term, String(10)); the Planning Workspace's Mission Backlog table used
// to re-prefix it with `T${m.recommended_term}`, rendering "TT1" instead of "T1".
// Any populated Rec. Term cell must match ^T[1-4]$ exactly, never double-prefixed.
test("Mission Backlog Rec. Term column is not double-prefixed", async ({ page }) => {
  await page.goto("/planning");
  await expect(page.getByRole("main", { name: /planning workspace/i })).toBeVisible({ timeout: 10000 });

  await page.getByText("Activities ▲").click();
  await page.getByRole("button", { name: "Mission Backlog" }).click();
  await expect(page.getByText("Rec. Term")).toBeVisible({ timeout: 8000 });

  const cells = page.locator("table").locator("tr").locator("td").filter({ hasText: /^T\d$|^TT\d$/ });
  const count = await cells.count();
  for (let i = 0; i < count; i++) {
    await expect(cells.nth(i)).toHaveText(/^T[1-4]$/);
  }
});

test("read-only role (sqn_general) cannot see admin controls", async ({ page }) => {
  // Log out and back in as general user
  await page.getByRole("button", { name: /log out|sign out/i }).click();
  await expect(page.getByRole("button", { name: "Log in" })).toBeVisible();
  await page.getByLabel("Access code").fill("703SQN2026");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
  await page.goto("/parade-nights");
  // Admin create button should not exist for sqn_general
  await expect(page.getByRole("button", { name: /create.*parade|add.*night/i })).not.toBeVisible();
});
