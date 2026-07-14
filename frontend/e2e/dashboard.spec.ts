import { test, expect } from "@playwright/test";

// ── Dashboard ─────────────────────────────────────────────────────────────────

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Access code").fill("ADMIN703");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
});

test("dashboard shows readiness stat", async ({ page }) => {
  await expect(page.getByText(/next-parade readiness/i)).toBeVisible();
});

test("dashboard shows parade nights count", async ({ page }) => {
  // Use exact match to avoid matching the nav link and card title simultaneously
  await expect(page.getByText("Parade nights", { exact: true })).toBeVisible();
});

test("dashboard shows training decision card", async ({ page }) => {
  await expect(page.getByText(/training decision/i)).toBeVisible();
});

test("dashboard shows curriculum coverage stat", async ({ page }) => {
  await expect(page.getByText(/curriculum coverage/i)).toBeVisible();
});
