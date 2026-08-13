import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// WORK-14: Export Annual Program (exportAnnualProgram) button wired to py-action-btns.
// WORK-15: Export Schedule (exportSchedule) button wired to py-action-btns.
// Both functions were fully implemented (JS + backend endpoint) but had no UI
// entry point. Buttons are now rendered by _renderPyActionBtns() when a planning
// year is selected — visible to all roles with planning access (no plan-write-el guard).

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

test.beforeAll(async () => {
  await resetBackendRateLimits(
    process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000"
  );
});

async function loginSquadron(page: Page, code = "ADMIN703") {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => {
      (window as any).AAFC_API_BASE = base;
    }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("squadron");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-sqn-select").selectOption("703");
  await page.locator("#auth-role").selectOption("sqn_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill(code);
  await page.locator("#auth-btn").click();
  await expect(page.locator("#app")).toBeVisible({ timeout: 10000 });
}

async function selectPlanningYear(page: Page) {
  await page.evaluate(() => (window as any).nav("activities"));
  const yearSelect = page.locator("#py-select");
  await expect(yearSelect).toBeVisible({ timeout: 10000 });
  // Pick the first non-empty year option (seeded 2026 planning year for sqn 703).
  await yearSelect.evaluate((el: HTMLSelectElement) => {
    const opt = Array.from(el.options).find((o) => o.value !== "");
    if (opt) el.value = opt.value;
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  // Wait for py-action-btns to be populated — it renders after loadYearMap resolves.
  await expect(page.locator("#py-action-btns button")).toBeVisible({ timeout: 10000 });
}

test("WORK-14: 'Export Annual' button is visible in Planning Year actions when a year is selected", async ({
  page,
}) => {
  // exportAnnualProgram() was implemented but had no UI entry point.
  // After WORK-14 fix, _renderPyActionBtns() adds an "Export Annual" button
  // whenever P.currentYearId is set.
  await loginSquadron(page);
  await selectPlanningYear(page);
  const exportBtn = page.locator("#py-action-btns button", { hasText: "Export Annual" });
  await expect(exportBtn).toBeVisible({ timeout: 8000 });
  await expect(exportBtn).toHaveAttribute("title", "Export annual program to Excel");
});

test("WORK-15: 'Export Schedule' button is visible in Planning Year actions when a year is selected", async ({
  page,
}) => {
  // exportSchedule() was implemented but had no UI entry point.
  // After WORK-15 fix, _renderPyActionBtns() adds an "Export Schedule" button
  // alongside "Export Annual".
  await loginSquadron(page);
  await selectPlanningYear(page);
  const exportBtn = page.locator("#py-action-btns button", { hasText: "Export Schedule" });
  await expect(exportBtn).toBeVisible({ timeout: 8000 });
  await expect(exportBtn).toHaveAttribute("title", "Export schedule to Excel");
});
