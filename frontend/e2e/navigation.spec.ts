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

// ── Navigation and route coverage ────────────────────────────────────────────
// Tests that major nav routes load and render their page heading.
// Requires backend on :8000 seeded with 703 demo data.

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await loginPW(page, "ADMIN703");
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

test("Mission Backlog (Needs Attention) page loads", async ({ page }) => {
  await page.goto("/action-items");
  await expect(page.getByRole("heading", { name: /mission backlog|needs attention|action item/i })).toBeVisible({ timeout: 8000 });
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

test("Activities tab shows Getting Help section, Edit hidden for sqn_admin", async ({ page }) => {
  await page.goto("/planning");
  await expect(page.getByRole("main", { name: /planning workspace/i })).toBeVisible({ timeout: 10000 });

  await page.getByText("Activities ▲").click();
  const helpHeading = page.getByRole("heading", { name: "Getting Help" });
  await expect(helpHeading).toBeVisible({ timeout: 8000 });
  // sqn_admin is not system_admin -- the Edit control must not render.
  const helpCard = helpHeading.locator("..");
  await expect(helpCard.getByRole("button", { name: "Edit" })).toHaveCount(0);
});

test("Account Management shows Reference Data card, sqn_admin can create a Training Stage", async ({ page }) => {
  await page.goto("/accounts");
  await expect(page.getByText("Reference Data")).toBeVisible({ timeout: 8000 });
  await expect(page.getByText("your own scope (squadron)")).toBeVisible();
  const stageName = `E2E PW Stage ${Date.now()}`;
  const stageInput = page.getByPlaceholder("New Training Stage name…");
  await stageInput.fill(stageName);
  await stageInput.locator("..").getByRole("button", { name: "+ Add", exact: true }).click();
  await expect(page.getByText(stageName)).toBeVisible({ timeout: 8000 });
});

test("read-only role (sqn_general) cannot see admin controls", async ({ page }) => {
  // Log out and back in as general user
  await page.getByRole("button", { name: /log out|sign out/i }).click();
  await expect(page.getByRole("button", { name: "Log in" })).toBeVisible();
  await loginPW(page, "703SQN2026");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
  await page.goto("/parade-nights");
  // Admin create button should not exist for sqn_general
  await expect(page.getByRole("button", { name: /create.*parade|add.*night/i })).not.toBeVisible();
});
