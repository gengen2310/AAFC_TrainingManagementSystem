import { test, expect } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";
import { loginPW } from "../e2e-login-helper";

const BACKEND = process.env.E2E_BACKEND_BASE_URL || "http://localhost:8000";

test.beforeAll(async () => {
  await resetBackendRateLimits(BACKEND);
});

// Planning Workspace is module-only. These tests deliberately verify the
// deployed route contract instead of the retired full React TMS shell.
test("unauthenticated deep links hand the user back to Main TMS without a second login UI", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Session not found" })).toBeVisible({ timeout: 10000 });
  await expect(page.getByRole("link", { name: "Return to TMS" })).toBeVisible();
  await expect(page.getByRole("button", { name: /log in|sign in/i })).toHaveCount(0);
  await expect(page.getByRole("navigation")).toHaveCount(0);
});

test("authenticated entry resolves to the module-owned /planning route", async ({ page }) => {
  await loginPW(page, "ADMIN703");
  await expect(page).toHaveURL(/\/planning$/);
  await expect(page.locator('[role="main"][aria-label="Planning workspace"]')).toBeVisible();
});

test("authenticated retired full-app routes cannot resurrect the old React shell", async ({ page }) => {
  await loginPW(page, "ADMIN703");
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/planning$/);
  await expect(page.locator('[role="main"][aria-label="Planning workspace"]')).toBeVisible({ timeout: 10000 });
  await expect(page.getByRole("heading", { name: "Dashboard" })).toHaveCount(0);
  await expect(page.getByRole("navigation")).toHaveCount(0);
});

test("Mission Backlog recommended terms keep the canonical T1-T4 form", async ({ page }) => {
  await loginPW(page, "ADMIN703");
  await page.getByText("Planning Tools ▲").click();
  await page.getByRole("button", { name: "Mission Backlog" }).click();
  await expect(page.getByText("Rec. Term")).toBeVisible({ timeout: 8000 });

  // Scope to the specific Mission Backlog table (which owns the "Rec. Term"
  // header) to avoid false matches from other tables rendered in the canvas
  // simultaneously (YearView, TermView etc.).
  const backlogTable = page.locator("table", {
    has: page.locator("th", { hasText: "Rec. Term" }),
  });
  // Wait for at least one data row so we don't snapshot an empty table.
  await expect(backlogTable.locator("tbody tr").first()).toBeVisible({ timeout: 8000 });

  // Snapshot all matching cells at once via .all() so the loop iterates stable
  // references; a re-render between count() and nth(i) can otherwise yield
  // unexpected elements on slower browsers.
  const termCells = await backlogTable.locator("td").filter({ hasText: /^T\d$|^TT\d$/ }).all();
  for (const cell of termCells) {
    await expect(cell).toHaveText(/^T[1-4]$/);
  }
});
