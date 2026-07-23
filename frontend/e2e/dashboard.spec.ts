import { test, expect } from "@playwright/test";

// ── Dashboard ─────────────────────────────────────────────────────────────────

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Access code").fill("ADMIN703");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
});

// Phase 4 (master transformation plan) rebuilt the Dashboard onto the same
// chart-ready backend endpoints (/api/dashboard/charts) already used by
// connected-frontend's Main TMS Dashboard, replacing several of the old
// stat-only tiles with the equivalent charts (e.g. "Next-parade readiness"
// stat → the "Tonight's readiness" chart card; "Curriculum coverage" stat →
// the "Curriculum progress by phase" chart).

test("dashboard shows tonight's readiness chart", async ({ page }) => {
  await expect(page.getByText(/tonight's readiness/i)).toBeVisible();
});

test("dashboard shows parade nights count", async ({ page }) => {
  // Use exact match to avoid matching the nav link and card title simultaneously
  await expect(page.getByText("Parade nights", { exact: true })).toBeVisible();
});

test("dashboard shows training decision card", async ({ page }) => {
  await expect(page.getByText(/training decision/i)).toBeVisible();
});

test("dashboard shows curriculum progress by phase chart", async ({ page }) => {
  await expect(page.getByText(/curriculum progress by phase/i)).toBeVisible();
});

test("dashboard shows all curriculum phases including zero-value ones", async ({ page }) => {
  // 704 squadron has no facilitators/sessions seeded, so every phase in this
  // chart is zero-value — confirms phases are never hidden for having no data.
  // beforeEach already logged in as ADMIN703; sign out before switching users.
  await page.getByRole("button", { name: /sign out/i }).click();
  await expect(page.getByLabel("Access code")).toBeVisible({ timeout: 10000 });
  await page.getByLabel("Access code").fill("ADMIN704");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
  for (const phase of ["A. Orientation", "B. Initial", "C. Junior", "D. Intermediate", "E. Senior", "I. Bronze", "J. Silver", "K. Gold"]) {
    await expect(page.getByText(phase, { exact: true })).toBeVisible();
  }
});

test("dashboard defers resilience charts behind a button", async ({ page }) => {
  const button = page.getByRole("button", { name: /load resilience charts/i });
  await expect(button).toBeVisible();
  await expect(page.getByText(/facilitator capability dependency/i)).toHaveCount(0);
  await button.click();
  await expect(page.getByText(/facilitator capability dependency/i)).toBeVisible();
});
